"""
Core NLP/ML services for extracting context from text

This module provides reusable services for:
- Keyword extraction
- Named entity recognition
- IAB topic classification
- Text embedding generation
"""

import hashlib
import logging
import os
import threading
import urllib.parse
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

import ftfy
import numpy as np
import regex as re
import spacy
import torch

from keybert import KeyBERT
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

try:
    from optimum.onnxruntime import ORTModelForSequenceClassification
    _HAS_ONNX = True
except ImportError:
    _HAS_ONNX = False


def generate_url_hash(url: str) -> tuple[str, str]:
    """Generate a hash for a URL and return normalized URL.

    Normalization matches Go's canonicalURL() in internal/utils/url_util.go:
    - Strip duplicated scheme prefixes (e.g. https://https://example.com)
    - Lowercase scheme and host
    - Remove trailing slashes from path
    """
    # Strip duplicated scheme prefixes (match Go canonicalURL behavior)
    for scheme in ("https://", "http://"):
        while url.startswith(scheme + scheme):
            url = url[len(scheme):]

    parsed = urllib.parse.urlparse(url)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.rstrip('/')
    )
    normalized_url = urllib.parse.urlunparse(normalized)
    url_hash = hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()
    return url_hash, normalized_url


def load_iab_taxonomy(taxonomy: str = "content") -> List[Dict[str, Any]]:
    """Load IAB taxonomy from JSON file"""
    import json

    key = taxonomy.lower()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "..", "..", "data")

    mapping = {
        "content": os.path.join(data_dir, "iab_content_taxonomy.json"),
        "product": os.path.join(data_dir, "iab_product_taxonomy.json")
    }
    path = mapping.get(key)
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Taxonomy file not found for '{key}': {path}")

    with open(path, "r") as f:
        return json.load(f)


_shared_embedder = None
_embedder_lock = threading.Lock()

def get_shared_embedder() -> SentenceTransformer:
    global _shared_embedder
    if _shared_embedder is None:
        with _embedder_lock:
            # Double-check after acquiring a lock
            if _shared_embedder is None:
                device = _device()
                _shared_embedder = SentenceTransformer("all-MiniLM-L6-v2", device=str(device))
    return _shared_embedder


def _device():
    """Determine the best available device"""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class KeywordExtractor:
    """Extract keywords from text using KeyBERT"""

    def __init__(self):
        self.keybert = KeyBERT()

    def extract(self, text: str, top_n: int = 15) -> Dict[str, float]:
        """
        Extract keywords from text

        Args:
            text: Input text
            top_n: Number of keywords to extract

        Returns:
            Dictionary of keywords and their relevance scores
        """
        all_keywords = self.keybert.extract_keywords(
            text, top_n=top_n,
            keyphrase_ngram_range=(1, 2),
            stop_words="english"
        )

        return {kw: score for kw, score in all_keywords}


class EntityExtractor:
    """Extract named entities from text using spaCy"""

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.allowed_types = {"ORG", "PRODUCT", "PERSON", "EVENT", "GPE"}

    def extract(self, text: str) -> List[Dict[str, str]]:
        """
        Extract named entities from text

        Args:
            text: Input text

        Returns:
            List of entities with text and type
        """
        doc = self.nlp(text)
        unique_entities = {}

        for ent in doc.ents:
            if ent.label_ in self.allowed_types and len(ent.text) >= 3:
                cleaned = self._clean_entity_text(ent.text)
                if not cleaned:
                    continue

                key = (cleaned, ent.label_)
                if key not in unique_entities:
                    unique_entities[key] = {
                        "text": cleaned,
                        "type": ent.label_
                    }

        return list(unique_entities.values())

    @staticmethod
    def _clean_entity_text(text: str) -> str:
        """Clean and normalize entity text"""
        cleaned = ftfy.fix_text(text)
        cleaned = cleaned.lower()
        cleaned = re.sub(r"'s\b|'s\b", "", cleaned)
        cleaned = cleaned.strip(" ,.;:!?-()[]{}\"'")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned


class TopicClassifier:
    """Classify text into IAB taxonomy topics using zero-shot classification"""

    def __init__(self):
        self.content_taxonomy = load_iab_taxonomy("content")
        self.product_taxonomy = load_iab_taxonomy("product")

        self.device = _device()
        self.dtype = torch.float32

        model_id = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


        if _HAS_ONNX and self.device.type == "cpu":
            logger.info(f"Loading {model_id} with ONNX Runtime (optimized CPU inference)")
            self.model = ORTModelForSequenceClassification.from_pretrained(
                model_id, export=True
            )
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
            self.tokenizer.model_max_length = 512
            self.classifier = pipeline(
                "zero-shot-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                batch_size=8,
                truncation=True
            )
        else:
            logger.info(f"Loading {model_id} with PyTorch (device={self.device})")
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_id,
                torch_dtype=self.dtype,
                low_cpu_mem_usage=True
            )
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
            self.tokenizer.model_max_length = 512
            self.model.to(self.device).eval()
            self.classifier = pipeline(
                "zero-shot-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device.type == "cuda" else (
                    -1 if self.device.type == "cpu" else self.device
                ),
                batch_size=8,
                truncation=True
            )

        self.embedder = get_shared_embedder()
        self._tokenizer_lock = threading.Lock()
        self._classifier_lock = threading.Lock()

        # Pre-compute taxonomy embeddings for fast classification
        self._taxonomy_embeddings = {}
        self._taxonomy_node_map = {}
        self._label_embedding_cache: Dict[str, np.ndarray] = {}
        all_label_names: list[str] = []
        for tax_name, taxonomy in [("content", self.content_taxonomy), ("product", self.product_taxonomy)]:
            nodes = self._flatten_taxonomy_nodes(taxonomy)
            self._taxonomy_node_map[tax_name] = nodes
            if nodes:
                names = [n["name"] for n in nodes]
                self._taxonomy_embeddings[tax_name] = self.embedder.encode(
                    names, batch_size=64, normalize_embeddings=True,
                    convert_to_numpy=True, show_progress_bar=False
                )
                for name in names:
                    if name not in self._label_embedding_cache:
                        all_label_names.append(name)
            else:
                self._taxonomy_embeddings[tax_name] = np.array([])

        # Batch-encode all unique label names for _shortlist_labels cache
        if all_label_names:
            all_vecs = self.embedder.encode(
                all_label_names, batch_size=64, normalize_embeddings=True,
                convert_to_numpy=True, show_progress_bar=False
            )
            for name, vec in zip(all_label_names, all_vecs):
                self._label_embedding_cache[name] = vec

        logger.info("Pre-computed taxonomy embeddings for fast classification")

    @staticmethod
    def _flatten_taxonomy_nodes(hierarchy: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flatten the taxonomy hierarchy into a list of nodes with parent info"""
        nodes = []
        stack = [(node, None) for node in hierarchy]
        while stack:
            node, parent_id = stack.pop()
            entry = {
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "tier": node.get("tier", 1),
                "parent_id": parent_id,
            }
            nodes.append(entry)
            for child in node.get("children", []):
                stack.append((child, node.get("id", "")))
        return nodes

    def classify_fast(
            self,
            text: str,
            taxonomy: str = "content",
            threshold: float = 0.3,
            top_k: int = 2,
            return_top_paths: int = 5
    ) -> List[List[Dict[str, Any]]]:
        """
        Fast topic classification using pre-computed taxonomy embeddings + cosine similarity
        """
        nodes = self._taxonomy_node_map.get(taxonomy, [])
        tax_embeddings = self._taxonomy_embeddings.get(taxonomy)
        if not nodes or tax_embeddings is None or len(tax_embeddings) == 0:
            return []

        # Encode input text once
        text_vec = self.embedder.encode(
            text, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False
        ).reshape(1, -1)

        # Compute cosine similarity against all taxonomy nodes
        similarities = (tax_embeddings @ text_vec.T).flatten()

        # Build a lookup: node_id -> (node, score)
        node_scores = {}
        for i, node in enumerate(nodes):
            node_scores[node["id"]] = (node, float(similarities[i]))

        # Walk the hierarchy: collect scored paths tier by tier
        # Group nodes by tier
        tier_nodes = {}
        for node_id, (node, score) in node_scores.items():
            tier = node["tier"]
            tier_nodes.setdefault(tier, []).append((node, score))

        max_tier = max(tier_nodes.keys()) if tier_nodes else 0

        # Start from tier 1: pick top_k above threshold
        branches = []
        tier1 = sorted(tier_nodes.get(1, []), key=lambda x: x[1], reverse=True)
        for node, score in tier1[:top_k]:
            if score >= threshold:
                entry = {"name": node["name"], "iab_id": node["id"], "tier": 1, "score": score}
                branches.append(([entry], node["id"], score))

        # Extend paths through child tiers
        for tier in range(2, max_tier + 1):
            next_branches = []
            tier_items = tier_nodes.get(tier, [])
            # Group by parent
            children_by_parent = {}
            for node, score in tier_items:
                pid = node["parent_id"]
                children_by_parent.setdefault(pid, []).append((node, score))

            for path, leaf_id, cum_score in branches:
                children = children_by_parent.get(leaf_id, [])
                if not children:
                    next_branches.append((path, leaf_id, cum_score))
                    continue

                ranked = sorted(children, key=lambda x: x[1], reverse=True)
                extended = False
                for node, score in ranked[:top_k]:
                    if score >= threshold:
                        entry = {"name": node["name"], "iab_id": node["id"], "tier": tier, "score": score}
                        next_branches.append((path + [entry], node["id"], cum_score * score))
                        extended = True

                if not extended:
                    next_branches.append((path, leaf_id, cum_score))

            branches = next_branches

        # Sort by cumulative score and deduplicate by leaf
        branches.sort(key=lambda x: x[2], reverse=True)
        result = []
        seen_leaves = set()
        for path, leaf_id, _ in branches:
            if leaf_id not in seen_leaves:
                result.append(path)
                seen_leaves.add(leaf_id)
                if len(result) >= return_top_paths:
                    break

        return result

    def classify_fast_batch(
            self,
            texts: List[str],
            taxonomy: str = "content",
            threshold: float = 0.3,
            top_k: int = 2,
            return_top_paths: int = 5,
    ) -> List[List[List[Dict[str, Any]]]]:
        """Batch version of classify_fast — encode all texts at once."""
        nodes = self._taxonomy_node_map.get(taxonomy, [])
        tax_embeddings = self._taxonomy_embeddings.get(taxonomy)
        if not nodes or tax_embeddings is None or len(tax_embeddings) == 0:
            return [[] for _ in texts]

        # Batch-encode all texts in one call
        text_vecs = self.embedder.encode(
            texts, batch_size=128, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False
        )

        # Cosine similarity: (N_texts, N_nodes)
        all_sims = text_vecs @ tax_embeddings.T

        results = []
        for idx in range(len(texts)):
            similarities = all_sims[idx]

            node_scores = {}
            for i, node in enumerate(nodes):
                node_scores[node["id"]] = (node, float(similarities[i]))

            tier_nodes = {}
            for node_id, (node, score) in node_scores.items():
                tier = node["tier"]
                tier_nodes.setdefault(tier, []).append((node, score))

            max_tier = max(tier_nodes.keys()) if tier_nodes else 0

            branches = []
            tier1 = sorted(tier_nodes.get(1, []), key=lambda x: x[1], reverse=True)
            for node, score in tier1[:top_k]:
                if score >= threshold:
                    entry = {"name": node["name"], "iab_id": node["id"], "tier": 1, "score": score}
                    branches.append(([entry], node["id"], score))

            for tier in range(2, max_tier + 1):
                next_branches = []
                tier_items = tier_nodes.get(tier, [])
                children_by_parent = {}
                for node, score in tier_items:
                    pid = node["parent_id"]
                    children_by_parent.setdefault(pid, []).append((node, score))

                for path, leaf_id, cum_score in branches:
                    children = children_by_parent.get(leaf_id, [])
                    if not children:
                        next_branches.append((path, leaf_id, cum_score))
                        continue
                    ranked = sorted(children, key=lambda x: x[1], reverse=True)
                    extended = False
                    for node, score in ranked[:top_k]:
                        if score >= threshold:
                            entry = {"name": node["name"], "iab_id": node["id"], "tier": tier, "score": score}
                            next_branches.append((path + [entry], node["id"], cum_score * score))
                            extended = True
                    if not extended:
                        next_branches.append((path, leaf_id, cum_score))
                branches = next_branches

            branches.sort(key=lambda x: x[2], reverse=True)
            result = []
            seen_leaves = set()
            for path, leaf_id, _ in branches:
                if leaf_id not in seen_leaves:
                    result.append(path)
                    seen_leaves.add(leaf_id)
                    if len(result) >= return_top_paths:
                        break
            results.append(result)

        return results

    def classify(
            self,
            text: str,
            taxonomy: str = "content",
            threshold: float = 0.5,
            top_k: int = 2,
            return_top_paths: int = 5
    ) -> List[List[Dict[str, Any]]]:
        """
        Classify text into IAB taxonomy topics

        Args:
            text: Input text
            taxonomy: "content" or "product"
            threshold: Minimum score threshold
            top_k: Number of topics per tier
            return_top_paths: Number of complete paths to return

        Returns:
            List of paths through taxonomy hierarchy
        """
        hierarchy = self.product_taxonomy if taxonomy == "product" else self.content_taxonomy

        return self._hierarchical_zero_shot(
            text=text,
            hierarchy=hierarchy,
            multi_label_per_tier=True,
            tier_threshold=threshold,
            tier_top_k=top_k,
            hypothesis_template="The topic of this text is {}.",
            score_aggregate="mean",
            max_tokens=300,
            overlap=96,
            batch_size=8,
            return_top_paths=return_top_paths
        )

    def classify_batch(
            self,
            texts: List[str],
            taxonomy: str = "content",
            threshold: float = 0.5,
            top_k: int = 2,
            return_top_paths: int = 5,
    ) -> List[List[List[Dict[str, Any]]]]:
        """Batch zero-shot classification: processes multiple texts together.

        At each tier, all texts that share the same candidate label set are
        scored in a single batched classifier call, dramatically reducing
        per-item overhead.
        """
        hierarchy = self.product_taxonomy if taxonomy == "product" else self.content_taxonomy
        hypothesis_template = "The topic of this text is {}."
        max_tokens = 300
        overlap = 96
        shortlist_top_k = 8

        n = len(texts)
        # Pre-chunk all texts
        all_chunks: List[List[str]] = [
            self._chunk_text_by_tokens(t, max_tokens=max_tokens, overlap=overlap)
            for t in texts
        ]

        # Per-text state: list of (nodes, path_details, cum_score) branches
        text_branches: List[List[tuple]] = [
            [(hierarchy, [], 1.0)] for _ in range(n)
        ]
        text_completed: List[List[tuple]] = [[] for _ in range(n)]

        max_depth = 4  # safety limit
        for _depth in range(max_depth):
            # Group (text_idx, branch_idx) by their label set for batching
            label_groups: Dict[tuple, List[tuple]] = {}
            any_active = False

            for text_idx in range(n):
                new_branches = []
                for br_idx, (nodes, path_details, cum_score) in enumerate(text_branches[text_idx]):
                    labels = tuple(n_item.get("name", "") for n_item in nodes if n_item.get("name"))
                    if not labels:
                        text_completed[text_idx].append((path_details, cum_score))
                        continue
                    any_active = True
                    key = labels  # group by identical label set
                    label_groups.setdefault(key, []).append((text_idx, br_idx, nodes, path_details, cum_score))

                # Keep branches for this iteration
                # (they'll be replaced below)

            if not any_active:
                break

            # For each label group, batch-score all texts' chunks at once
            next_text_branches: List[List[tuple]] = [[] for _ in range(n)]

            for labels_key, group_items in label_groups.items():
                labels_list = list(labels_key)

                # Collect all chunks from all texts in this group
                batch_chunks = []
                chunk_boundaries = []  # (start, end) per group item
                for text_idx, br_idx, nodes, path_details, cum_score in group_items:
                    chunks = all_chunks[text_idx]
                    start = len(batch_chunks)
                    batch_chunks.extend(chunks)
                    chunk_boundaries.append((start, len(batch_chunks)))

                # Shortlist labels using first text's chunks (they share the same labels)
                shortlisted = self._shortlist_labels(
                    batch_chunks[:chunk_boundaries[0][1] - chunk_boundaries[0][0]] if chunk_boundaries else batch_chunks[:1],
                    labels_list,
                    top_k=min(shortlist_top_k, len(labels_list)),
                )

                # Batch classifier call: pass ALL chunks at once
                with self._classifier_lock:
                    results = self.classifier(
                        sequences=batch_chunks if len(batch_chunks) > 1 else batch_chunks[0],
                        candidate_labels=shortlisted,
                        multi_label=True,
                        hypothesis_template=hypothesis_template,
                        batch_size=16,
                        truncation=True,
                    )

                if isinstance(results, dict):
                    results = [results]

                # De-interleave results per text
                for item_idx, (text_idx, br_idx, nodes, path_details, cum_score) in enumerate(group_items):
                    start, end = chunk_boundaries[item_idx]
                    text_results = results[start:end]

                    per_label_scores: Dict[str, List[float]] = {lab: [] for lab in shortlisted}
                    for out in text_results:
                        for lab, s in zip(out["labels"], out["scores"]):
                            per_label_scores[lab].append(float(s))

                    scores = {lab: (sum(v) / len(v)) if v else 0.0 for lab, v in per_label_scores.items()}
                    for lab in labels_list:
                        scores.setdefault(lab, 0.0)

                    ranked = sorted(
                        ((lab, scores.get(lab, 0.0)) for lab in labels_list),
                        key=lambda x: x[1], reverse=True,
                    )
                    chosen = [(lab, s) for lab, s in ranked if s >= threshold][:top_k]

                    if not chosen:
                        text_completed[text_idx].append((path_details, cum_score))
                        continue

                    current_tier = len(path_details) + 1
                    for lab, s in chosen:
                        node = next((nd for nd in nodes if nd.get("name") == lab), None)
                        if node:
                            tier_entry = {
                                "name": lab,
                                "iab_id": node.get("id", ""),
                                "tier": current_tier,
                                "score": s,
                            }
                            child_nodes = node.get("children", [])
                            next_text_branches[text_idx].append(
                                (child_nodes, path_details + [tier_entry], cum_score * s)
                            )

            # Check if any text still has active branches
            has_active = False
            for text_idx in range(n):
                if next_text_branches[text_idx]:
                    has_active = True
                text_branches[text_idx] = next_text_branches[text_idx]

            if not has_active:
                break

        # Collect remaining branches as completed
        for text_idx in range(n):
            for nodes, path_details, cum_score in text_branches[text_idx]:
                text_completed[text_idx].append((path_details, cum_score))

        # Build final results per text
        all_results = []
        for text_idx in range(n):
            completed = sorted(text_completed[text_idx], key=lambda x: x[1], reverse=True)
            result = []
            seen_leaf_ids = set()
            for path_details, cum_score in completed:
                if not path_details:
                    continue
                leaf_id = path_details[-1]["iab_id"]
                if leaf_id in seen_leaf_ids:
                    continue
                result.append(path_details)
                seen_leaf_ids.add(leaf_id)
                if len(result) >= return_top_paths:
                    break
            all_results.append(result)

        return all_results

    def _hierarchical_zero_shot(
            self,
            text: str,
            hierarchy: List[Dict[str, Any]],
            multi_label_per_tier: bool = True,
            tier_threshold: float = 0.5,
            tier_top_k: int = 2,
            hypothesis_template: str = "This text is about {}.",
            score_aggregate: str = "mean",
            max_tokens: Optional[int] = None,
            overlap: int = 32,
            batch_size: int = 8,
            shortlist_top_k: int = 8,
            return_top_paths: int = 5
    ) -> List[List[Dict[str, Any]]]:
        """Perform hierarchical zero-shot classification"""
        from typing import Tuple

        branches: List[Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]] = [
            (hierarchy, [], 1.0)
        ]
        completed: List[Tuple[List[Dict[str, Any]], float]] = []

        while branches:
            next_branches: List[Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]] = []

            for nodes, path_details, cum_score in branches:
                if not nodes:
                    completed.append((path_details, cum_score))
                    continue

                labels = [n.get("name", "") for n in nodes if n.get("name")]
                if not labels:
                    completed.append((path_details, cum_score))
                    continue

                current_tier = len(path_details) + 1

                scores = self._score_tier(
                    text=text,
                    candidate_labels=labels,
                    multi_label=multi_label_per_tier,
                    hypothesis_template=hypothesis_template,
                    aggregate=score_aggregate,
                    batch_size=batch_size,
                    max_tokens=max_tokens,
                    overlap=overlap,
                    shortlist_top_k=shortlist_top_k
                )

                ranked = sorted(
                    ((lab, scores.get(lab, 0.0)) for lab in labels),
                    key=lambda x: x[1],
                    reverse=True
                )

                if multi_label_per_tier:
                    chosen = [(lab, s) for lab, s in ranked if s >= tier_threshold][:tier_top_k]
                else:
                    lab, s = ranked[0]
                    chosen = [(lab, s)] if s >= tier_threshold else []

                if not chosen:
                    completed.append((path_details, cum_score))
                    continue

                for lab, s in chosen:
                    node = next((n for n in nodes if n.get("name") == lab), None)
                    if node:
                        tier_entry = {
                            "name": lab,
                            "iab_id": node.get("id", ""),
                            "tier": current_tier,
                            "score": s
                        }
                        new_path_details = path_details + [tier_entry]
                        child_nodes = node.get("children", [])
                        next_branches.append((child_nodes, new_path_details, cum_score * s))

            if not next_branches:
                break
            branches = next_branches

        for nodes, path_details, cum_score in branches:
            completed.append((path_details, cum_score))

        completed = sorted(completed, key=lambda x: x[1], reverse=True)

        result = []
        seen_leaf_ids = set()

        for path_details, cum_score in completed:
            if not path_details:
                continue

            leaf_id = path_details[-1]["iab_id"]
            if leaf_id in seen_leaf_ids:
                continue

            result.append(path_details)
            seen_leaf_ids.add(leaf_id)

            if len(result) >= return_top_paths:
                break

        return result

    def _chunk_text_by_tokens(self,
                              text: str,
                              max_tokens: Optional[int] = None,
                              overlap: int = 32
                              ) -> List[str]:
        """Chunk text by token count"""
        limit = self.tokenizer.model_max_length if max_tokens is None else min(
            max_tokens, self.tokenizer.model_max_length
        )
        usable = max(64, limit - 16)

        with self._tokenizer_lock:
            ids = self.tokenizer.encode(text, add_special_tokens=False)

        if len(ids) <= usable:
            return [text]

        stride = max(1, usable - overlap)
        chunks = []

        for start in range(0, len(ids), stride):
            chunk_ids = ids[start:start + usable]
            if not chunk_ids:
                break

            with self._tokenizer_lock:
                chunks.append(self.tokenizer.decode(chunk_ids, skip_special_tokens=True))

            if start + usable >= len(ids):
                break

        return chunks

    def _shortlist_labels(
            self,
            text_chunks: List[str],
            labels: List[str],
            top_k: int = 8
    ) -> List[str]:
        """Shortlist labels using embedding similarity"""
        if len(labels) <= top_k:
            return labels

        chunk_vecs = self.embedder.encode(
            text_chunks, batch_size=32,
            normalize_embeddings=True,
            convert_to_numpy=True,
            truncate_dim=None,
            show_progress_bar=False
        )

        # Use cached label embeddings when available, fall back to encoding
        cached = [self._label_embedding_cache.get(lab) for lab in labels]
        if all(v is not None for v in cached):
            label_vecs = np.stack(cached)
        else:
            label_vecs = self.embedder.encode(
                labels, batch_size=64,
                normalize_embeddings=True,
                convert_to_numpy=True,
                truncate_dim=None,
                show_progress_bar=False
            )

        sims = label_vecs @ chunk_vecs.T
        per_label = sims.max(axis=1)
        idx = np.argsort(-per_label)[:top_k]

        return [labels[i] for i in idx]

    def _score_tier(
            self,
            text: str,
            candidate_labels: List[str],
            multi_label: bool,
            hypothesis_template: str,
            aggregate: str = "mean",
            batch_size: int = 8,
            max_tokens: Optional[int] = None,
            overlap: int = 32,
            shortlist_top_k: int = 8
    ) -> Dict[str, float]:
        """Score labels for a single tier"""
        chunks = self._chunk_text_by_tokens(text, max_tokens=max_tokens, overlap=overlap)
        labels = self._shortlist_labels(
            chunks, candidate_labels,
            top_k=min(shortlist_top_k, len(candidate_labels))
        )

        with self._classifier_lock:
            results = self.classifier(
                sequences=chunks if len(chunks) > 1 else chunks[0],
                candidate_labels=labels,
                multi_label=multi_label,
                hypothesis_template=hypothesis_template,
                batch_size=batch_size,
                truncation=True
            )

        if isinstance(results, dict):
            results = [results]

        per_label_scores: Dict[str, List[float]] = {lab: [] for lab in labels}
        for out in results:
            for lab, s in zip(out["labels"], out["scores"]):
                per_label_scores[lab].append(float(s))

        def reduce(vals: List[float]) -> float:
            if not vals:
                return 0.0
            return max(vals) if aggregate == "max" else (sum(vals) / len(vals))

        scores = {lab: reduce(v) for lab, v in per_label_scores.items()}
        for lab in candidate_labels:
            scores.setdefault(lab, 0.0)

        return scores


class EmbeddingGenerator:
    """Generate text embeddings using sentence transformers"""

    def __init__(self):
        self.device = _device()
        self.embedder = get_shared_embedder()
        self.nlp = spacy.load("en_core_web_sm")

    def generate(self, text: str, chunk: bool = False) -> Any:
        """
        Generate embeddings for text

        Args:
            text: Input text
            chunk: Whether to chunk text and return chunk embeddings

        Returns:
            Single embedding array if chunk=False, else (chunks, mean_embedding)
        """
        if not chunk:
            return self.embedder.encode(text, convert_to_numpy=True, show_progress_bar=False)

        # Chunk text semantically using the correct strategy
        chunks = self._semantic_chunker(text)
        merged_chunks = self._merge_short_chunks(chunks, min_chunk_words=20)
        refined_chunks = self._split_large_chunks_by_embedding_size(merged_chunks, max_tokens=256)

        all_embeddings = self.embedder.encode(refined_chunks, batch_size=32, convert_to_numpy=True, show_progress_bar=False)

        chunk_results = [
            {"content": chunk_text, "embedding": all_embeddings[i].tolist(), "chunk_index": i}
            for i, chunk_text in enumerate(refined_chunks)
        ]

        mean_embedding = np.mean(all_embeddings, axis=0)
        return chunk_results, mean_embedding

    def _semantic_chunker(self, content: str, std_dev_knob: float = 0.5) -> List[str]:
        """Chunk text based on semantic similarity"""
        sentences = self._sent_tokenize(content)
        if len(sentences) <= 1:
            return sentences

        embeddings = self.embedder.encode(sentences, show_progress_bar=False)
        similarities = []

        for index in range(len(embeddings) - 1):
            current_embedding = embeddings[index].reshape(1, -1)
            next_embedding = embeddings[index + 1].reshape(1, -1)
            sim = util.cos_sim(current_embedding, next_embedding)[0][0]
            similarities.append(sim)

        if len(similarities) <= 1:
            return sentences

        mean_similarity = np.mean(similarities)
        standard_deviation = np.std(similarities)
        threshold = mean_similarity - std_dev_knob * standard_deviation

        chunks = []
        current_chunk = [sentences[0]]

        for index in range(len(similarities)):
            if similarities[index] < threshold:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[index + 1]]
            else:
                current_chunk.append(sentences[index + 1])

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _merge_short_chunks(
            self,
            chunks: List[str],
            min_chunk_words: int = 20
    ) -> List[str]:
        """Merge chunks that are too short"""
        if len(chunks) <= 1:
            return chunks

        merged_chunks = []
        index = 0
        chunk_size = len(chunks)

        while index < chunk_size:
            current_chunk = chunks[index]
            word_count = len(current_chunk.split())

            if word_count < min_chunk_words and (index < chunk_size - 1):
                combined_chunks = current_chunk + " " + chunks[index + 1]
                merged_chunks.append(combined_chunks)
                index += 2
            else:
                merged_chunks.append(current_chunk)
                index += 1

        if len(merged_chunks) > 1 and len(merged_chunks[-1].split()) < min_chunk_words:
            merged_chunks[-2] = merged_chunks[-2] + " " + merged_chunks[-1]
            merged_chunks.pop()

        return merged_chunks

    def _sent_tokenize(self, text: str) -> List[str]:
        """Tokenize text into sentences using spaCy"""
        doc = self.nlp(text)
        return [sent.text.strip() for sent in doc.sents]

    def _split_large_chunks_by_embedding_size(
            self,
            chunks: List[str],
            max_tokens: int = 256
    ) -> List[str]:
        """Split chunks that exceed max token size"""
        final_chunks = []

        # We need a tokenizer - use a simple approach or initialize one
        # For now, use spacy tokenizer as approximation
        for chunk in chunks:
            # Rough estimate: ~0.75 tokens per word
            words = chunk.split()
            estimated_tokens = int(len(words) * 0.75)

            if estimated_tokens <= max_tokens:
                final_chunks.append(chunk)
            else:
                # Split by sentences if chunk is too large
                sentences = self._sent_tokenize(chunk)
                current_sub_chunk = []
                current_tokens = 0

                for sentence in sentences:
                    sentence_words = sentence.split()
                    sentence_tokens = int(len(sentence_words) * 0.75)

                    if sentence_tokens > max_tokens:
                        # Sentence itself is too long, add as-is
                        if current_sub_chunk:
                            final_chunks.append(" ".join(current_sub_chunk))
                        final_chunks.append(sentence)
                        current_sub_chunk = []
                        current_tokens = 0
                        continue

                    if current_tokens + sentence_tokens <= max_tokens:
                        current_sub_chunk.append(sentence)
                        current_tokens += sentence_tokens
                    else:
                        final_chunks.append(" ".join(current_sub_chunk))
                        current_sub_chunk = [sentence]
                        current_tokens = sentence_tokens

                if current_sub_chunk:
                    final_chunks.append(" ".join(current_sub_chunk))

        return final_chunks
