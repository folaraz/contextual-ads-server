import hashlib
import json
import urllib
from datetime import datetime
from itertools import chain
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
            {creative.get("headline", "")}.
            {creative.get("description", "")}.
            Keywords: {', '.join(keywords)}.
            Entities: {', '.join(entities)}.
            Topics: {', '.join(topics)}.
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
            context["topics"] = self.get_iab_topic_categories(cd["content"])
            chunks, page_embedding = self.get_embedding(cd["content"])
            context["page_embedding"] = page_embedding.tolist()
            context["chunks"] = chunks
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

    def get_keywords(self, text, top_n=15):
        unigram_keywords = self.keybert.extract_keywords(text, top_n=top_n, keyphrase_ngram_range=(1, 1),
                                                         stop_words="english")
        bigram_keywords = self.keybert.extract_keywords(text, top_n=top_n, keyphrase_ngram_range=(2, 2),
                                                        stop_words="english")
        keywords = dict()
        for keyword, score in chain(unigram_keywords, bigram_keywords):
            keywords[keyword] = max(score, keywords.get(keyword, 0))
        return keywords

    def get_iab_topic_categories(self, text):
        return self._hierarchical_zero_shot(
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

    def get_embedding(self, text):
        chunks = self.semantic_chunker(content=text)
        merged_chunks = self.merge_short_chunks(chunks=chunks, min_chunk_words=20)
        refined_chunks = self.split_large_chunks_by_embedding_size(chunks=merged_chunks, max_tokens=256)
        result = []
        embeddings = []
        for index, chunk in enumerate(refined_chunks):
            embedding = self.embedder.encode(chunk, convert_to_numpy=True)
            chunk_result = {"content": chunk, "embedding": embedding.tolist(), "chunk_index": index}
            embeddings.append(embedding)
            result.append(chunk_result)
        mean_embeddings = np.mean(embeddings, axis=0)
        return result, mean_embeddings

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

    def semantic_chunker(self, content: str, std_dev_knob: float = 0.5) -> list[str]:
        sentences = self._sent_tokenize(content)
        if len(sentences) <= 1:
            return sentences

        embeddings = self.embedder.encode(sentences)

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

    def merge_short_chunks(self, chunks: list[str], min_chunk_words: int = 20) -> list[str]:

        if len(chunks) <= 1:
            return chunks

        index = 0
        merged_chunks = []
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

    def split_large_chunks_by_embedding_size(self, chunks: list[str], max_tokens: int = 256) -> list[str]:
        final_chunks = []

        for chunk in chunks:
            token_ids = self.tokenizer.encode(chunk, add_special_tokens=False)

            if len(token_ids) <= max_tokens:
                final_chunks.append(chunk)
            else:
                sub_sentences = self._sent_tokenize(chunk)
                current_sub_chunk_sentences = []
                current_sub_chunk_tokens = 0

                for sentence in sub_sentences:
                    sentence_token_ids = self.tokenizer.encode(sentence, add_special_tokens=False)
                    sentence_tokens = len(sentence_token_ids)

                    if sentence_tokens > max_tokens:
                        if current_sub_chunk_sentences:
                            final_chunks.append(" ".join(current_sub_chunk_sentences))
                        final_chunks.append(sentence)  # Add the long sentence
                        current_sub_chunk_sentences = []
                        current_sub_chunk_tokens = 0
                        continue

                    if current_sub_chunk_tokens + sentence_tokens <= max_tokens:
                        current_sub_chunk_sentences.append(sentence)
                        current_sub_chunk_tokens += sentence_tokens
                    else:
                        final_chunks.append(" ".join(current_sub_chunk_sentences))
                        current_sub_chunk_sentences = [sentence]
                        current_sub_chunk_tokens = sentence_tokens

                if current_sub_chunk_sentences:
                    final_chunks.append(" ".join(current_sub_chunk_sentences))

        return final_chunks

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
        """
        Hierarchical zero-shot classification that returns complete paths through the taxonomy.

        Returns:
            List of paths, where each path is a list of dictionaries containing:
            - category: The category name
            - iab_id: The IAB taxonomy ID
            - tier: The tier level (1, 2, 3, etc.)
            - score: The classification score for this tier
        """
        # Store branches with full tier information: (nodes, path_with_details, cum_score)
        branches: List[Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]] = [(hierarchy, [], 1.0)]
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

                # Determine current tier level
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

                ranked = sorted(((lab, scores.get(lab, 0.0)) for lab in labels), key=lambda x: x[1], reverse=True)
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
                        node_id = node.get("id", "")
                        child_nodes = node.get("children", [])

                        # Create a tier entry with all required information
                        tier_entry = {
                            "category": lab,
                            "iab_id": node_id,
                            "tier": current_tier,
                            "score": s
                        }

                        # Create a new path with this tier added
                        new_path_details = path_details + [tier_entry]
                        next_branches.append((child_nodes, new_path_details, cum_score * s))

            if not next_branches:
                break
            branches = next_branches

        # Add any remaining branches to completed
        for nodes, path_details, cum_score in branches:
            completed.append((path_details, cum_score))

        # Sort by cumulative score (descending)
        completed = sorted(completed, key=lambda x: x[1], reverse=True)

        # Return top paths, each path is a list of tier dictionaries
        result = []
        seen_leaf_ids = set()

        for path_details, cum_score in completed:
            if not path_details:
                continue

            # Use the last tier's iab_id as the leaf identifier to avoid duplicates
            leaf_id = path_details[-1]["iab_id"]
            if leaf_id in seen_leaf_ids:
                continue

            result.append(path_details)
            seen_leaf_ids.add(leaf_id)

            if len(result) >= return_top_paths:
                break

        return result

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
