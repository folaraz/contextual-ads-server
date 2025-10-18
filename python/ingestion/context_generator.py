import hashlib
import json
import urllib
from datetime import datetime
from typing import List, Dict, Any, Tuple

import numpy as np
import spacy
import torch
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

from python.ingestion.crawler import Crawler


def load_iab_taxonomy():
    with open("../data/iab_taxonomy.json", "r") as f:
        iab_taxonomy = json.load(f)
    return iab_taxonomy


def _device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class ContextGenerator:
    def __init__(self):
        self.keybert = KeyBERT()
        self.spacy_core_web_sm = spacy.load("en_core_web_sm")
        self.iab_taxonomy = load_iab_taxonomy()
        self.DEVICE = _device()
        self.DTYPE = torch.float16 if self.DEVICE.type in ["cuda", "mps"] else torch.float32
        self.ZEROSHOT_MODEL_ID = "MoritzLaurer/deberta-v3-large-zeroshot-v2.0"
        self.ZEROSHOT_MODEL = AutoModelForSequenceClassification.from_pretrained(self.ZEROSHOT_MODEL_ID,
                                                                                 dtype=self.DTYPE)
        self.ZEROSHOT_TOK = AutoTokenizer.from_pretrained(self.ZEROSHOT_MODEL_ID, use_fast=True)
        self.ZEROSHOT_MODEL.to(self.DEVICE).eval()
        self.ZEROSHOT_CLASSIFIER = pipeline("zero-shot-classification",
                                            model=self.ZEROSHOT_MODEL,
                                            tokenizer=self.ZEROSHOT_TOK,
                                            device=0 if self.DEVICE.type == "cuda" else (
                                                -1 if self.DEVICE.type == "cpu" else self.DEVICE),
                                            batch_size=8
                                            )
        self.tokenizer = self.ZEROSHOT_CLASSIFIER.tokenizer
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2", device=str(self.DEVICE))
        self.crawler = Crawler()

    def generate_ad_context(self) -> Any:
        ads = self.crawler.get_ads_inventory()
        if not ads:
            return None
        for ad in tqdm(ads):
            context_targeting = ad["targeting"]
            creative = ad["creative"]
            if not context_targeting or not creative:
                return None
            keywords = [k.lower() for k in context_targeting["keywords"]]
            entities = [e.lower() for e in context_targeting["entities"]]
            topics = [t.lower() for t in context_targeting["topics"]]

            embedding_text = f"""
            Ad Headline: {creative.get("headline", "")}
            Description: {creative.get("description", "")}
            Keywords: {', '.join(keywords)}
            Topics: {', '.join(topics)}
            Entities: {', '.join(entities)}
            """
            embeddings = self.embedder.encode(embedding_text, convert_to_numpy=True)
            ad["keywords"] = keywords
            ad["topics"] = topics
            ad["entities"] = entities
            ad["embedding"] = embeddings.tolist()
        return ads

    def generate_page_context(self):
        if not self.crawler:
            return None

        crawled_results = self.crawler.crawl()
        if not crawled_results:
            return None

        processed_results = []
        for cd in tqdm(crawled_results):
            page_id, url = self.generate_hash_and_url(cd["url"])
            meta_data = {
                "url": url,
                "title": cd["title"],
                "description": cd["description"],
                "tags": cd["tags"],
                "text": cd["content"]
            }
            context = dict()
            context["page_id"] = page_id
            context["meta_data"] = meta_data
            context["last_analyzed"] = datetime.now().isoformat()
            context["keywords"] = self.get_keywords(cd["content"])
            context["entities"] = self.get_ner(cd["content"])
            context["topics_iab"] = self.get_iab_topic_categories(cd["content"])
            chunks, embeddings = self.get_embedding(cd["content"])
            combined_embedding = np.mean(embeddings, axis=0)
            context["page_embedding"] = combined_embedding.tolist()
            context["chunk_embeddings"] = embeddings.tolist()
            context["chunk_texts"] = chunks
            processed_results.append(context)
        return processed_results

    def get_ner(self, text):
        doc = self.spacy_core_web_sm(text)
        entities = dict()
        for ent in doc.ents:
            key = ent.text.lower()
            if key not in entities:
                entities[key] = {"entity": ent.text, "type": ent.label_}
        return list(entities.values())

    def get_keywords(self, text, top_n=10):
        keywords = self.keybert.extract_keywords(text, top_n=top_n)
        return [kw for kw, score in keywords]

    def get_iab_topic_categories(self, text):
        topic_cats = self._hierarchical_zero_shot(
            text=text,
            hierarchy=self.iab_taxonomy,
            multi_label_per_tier=True,
            tier_threshold=0.5,
            tier_top_k=2,
            hypothesis_template="The topic of this text is {}.",
            score_aggregate="mean",
            max_tokens=300,
            overlap=96,
            batch_size=8,
            return_top_paths=1
        )
        ans = []
        for t in topic_cats:
            for cat in t["category"]:
                c_lower = cat.lower()
                if c_lower not in ans:
                    ans.append(c_lower)
        return ans

    def get_embedding(self, text):
        chunks = self.semantic_chunker(text)
        if not chunks:
            return None
        embeddings = self.embedder.encode(chunks, convert_to_numpy=True)
        return chunks, embeddings

    @staticmethod
    def generate_hash_and_url(url: str) -> tuple[str, str]:
        parsed = urllib.parse.urlparse(url)
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=parsed.path.rstrip('/')
        )
        n = urllib.parse.urlunparse(normalized)
        return hashlib.sha256(n.encode('utf-8')).hexdigest(), normalized

    def semantic_chunker(self, content: str, breakpoint_percentile_threshold: float = 70.0) -> list[str]:
        texts: list[str] = self._sent_tokenize(content)
        if not texts:
            return []
        if len(texts) == 1:
            return texts

        embeddings = self.embedder.encode(texts, convert_to_tensor=True)
        similarities = util.cos_sim(embeddings[:-1], embeddings[1:]).diagonal().cpu().numpy()
        threshold = np.percentile(similarities, breakpoint_percentile_threshold)
        split_indices = [i for i, sim in enumerate(similarities) if sim < threshold]

        chunks = []
        start = 0
        for idx in split_indices:
            chunks.append(" ".join(texts[start:idx + 1]))
            start = idx + 1

        if start < len(texts):
            chunks.append(" ".join(texts[start:]))

        return chunks

    def _sent_tokenize(self, text):
        doc = self.spacy_core_web_sm(text)
        return [sent.text.strip() for sent in doc.sents]

    def _hierarchical_zero_shot(self,
                                text: str,
                                hierarchy: List[Dict[str, Any]],
                                multi_label_per_tier: bool = True,
                                tier_threshold: float = 0.5,
                                tier_top_k: int = 2,
                                hypothesis_template: str = "This text is about {}.",
                                score_aggregate: str = "mean",
                                max_tokens: int | None = None,
                                overlap: int = 32,
                                batch_size: int = 8,
                                shortlist_top_k: int = 8,
                                return_top_paths: int = 5
                                ) -> List[Dict[str, Any]]:
        branches: List[Tuple[List[Dict[str, Any]], List[str], List[str], float]] = [(hierarchy, [], [], 1.0)]
        completed: List[Tuple[List[str], str, float]] = []

        while branches:
            next_branches: List[Tuple[List[Dict[str, Any]], List[str], List[str], float]] = []
            for nodes, path, ids, cum_score in branches:
                if not nodes:
                    last_id = ids[-1] if ids else ""
                    completed.append((path, last_id, cum_score))
                    continue

                labels = [n.get("name", "") for n in nodes if n.get("name")]
                if not labels:
                    last_id = ids[-1] if ids else ""
                    completed.append((path, last_id, cum_score))
                    continue

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

                ranked = sorted(((lab, scores.get(lab, 0.0)) for lab in labels), key=lambda x: x[1], reverse=True)
                if multi_label_per_tier:
                    chosen = [(lab, s) for lab, s in ranked if s >= tier_threshold][:tier_top_k]
                else:
                    lab, s = ranked[0]
                    chosen = [(lab, s)] if s >= tier_threshold else []

                if not chosen:
                    last_id = ids[-1] if ids else ""
                    completed.append((path, last_id, cum_score))
                    continue

                for lab, s in chosen:
                    node = next((n for n in nodes if n.get("name") == lab), None)
                    if node:
                        node_id = node.get("id", "")
                        child_nodes = node.get("children", [])
                        next_branches.append((child_nodes, path + [lab], ids + [node_id], cum_score * s))

            if not next_branches:
                break
            branches = next_branches

        for _, path, ids, cum_score in branches:
            last_id = ids[-1] if ids else ""
            completed.append((path, last_id, cum_score))

        completed = sorted(completed, key=lambda x: x[2], reverse=True)
        ans = []
        seen_iab_ids = set()
        for p, iab_id, s in completed:
            if iab_id in seen_iab_ids:
                continue
            ans.append({"category": p, "iab_id": iab_id, "score": s})
            seen_iab_ids.add(iab_id)
        # todo limit to only top path and don't join them.
        return ans[:return_top_paths]

    def _chunk_text_by_tokens(self, text: str, max_tokens: int | None = None, overlap: int = 32) -> List[str]:
        limit = self.tokenizer.model_max_length if max_tokens is None else min(max_tokens,
                                                                               self.tokenizer.model_max_length)
        usable = max(64, limit - 16)
        ids = self.tokenizer.encode(text, add_special_tokens=False)
        if len(ids) <= usable:
            return [text]
        stride = max(1, usable - overlap)
        chunks = []
        for start in range(0, len(ids), stride):
            chunk_ids = ids[start:start + usable]
            if not chunk_ids:
                break
            chunks.append(self.tokenizer.decode(chunk_ids, skip_special_tokens=True))
            if start + usable >= len(ids):
                break
        return chunks

    def _shortlist_labels(self, text_chunks: List[str], labels: List[str], top_k: int = 8) -> List[str]:
        if len(labels) <= top_k:
            return labels
        chunk_vecs = self.embedder.encode(text_chunks, batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
        label_vecs = self.embedder.encode(labels, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
        sims = label_vecs @ chunk_vecs.T
        per_label = sims.max(axis=1)
        idx = np.argsort(-per_label)[:top_k]
        return [labels[i] for i in idx]

    def _score_tier(self,
                    text: str,
                    candidate_labels: List[str],
                    multi_label: bool,
                    hypothesis_template: str,
                    aggregate: str = "mean",
                    batch_size: int = 8,
                    max_tokens: int | None = None,
                    overlap: int = 32,
                    shortlist_top_k: int = 8
                    ) -> Dict[str, float]:
        chunks = self._chunk_text_by_tokens(text, max_tokens=max_tokens, overlap=overlap)
        labels = self._shortlist_labels(chunks, candidate_labels, top_k=min(shortlist_top_k, len(candidate_labels)))
        results = self.ZEROSHOT_CLASSIFIER(
            sequences=chunks if len(chunks) > 1 else chunks[0],
            candidate_labels=labels,
            multi_label=multi_label,
            hypothesis_template=hypothesis_template,
            batch_size=batch_size
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
