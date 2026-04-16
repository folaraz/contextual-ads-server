#!/usr/bin/env python3
from __future__ import annotations

"""
Pre-compute NLP evaluation fixtures.

Runs KeywordExtractor, EntityExtractor, TopicClassifier, and EmbeddingGenerator
from nlp_service.py on crawled_pages.json content and ads_inventory.json creative
text. Outputs two JSON fixture files that Go evaluation tests can load without
requiring Python or NLP models at test time.

Usage:
    python scripts/generate_eval_fixtures.py [--fast] [--output-dir DIR] [--workers N]

Flags:
    --fast          Use classify_fast (embedding-based) instead of zero-shot
                    for topic classification. 5x faster, slightly less accurate.
    --output-dir    Output directory (default: data/eval/)
    --workers       Number of concurrent workers for processing pages/ads
                    (default: 4)
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))

from services.nlp_service import (
    KeywordExtractor,
    EntityExtractor,
    TopicClassifier,
    EmbeddingGenerator,
    generate_url_hash,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("generate_eval_fixtures")

PROJECT_ROOT = PYTHON_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_DIR = DATA_DIR / "eval"

CRAWLED_PAGES_PATH = DATA_DIR / "crawled_pages.json"
ADS_INVENTORY_PATH = DATA_DIR / "ads_inventory.json"


def init_nlp_services():
    logger.info("Initializing NLP services (this may take a minute on first run)...")
    t0 = time.time()
    kw = KeywordExtractor()
    ent = EntityExtractor()
    topic = TopicClassifier()
    emb = EmbeddingGenerator()
    logger.info(f"NLP services ready in {time.time() - t0:.1f}s")


    kw_lock = threading.Lock()
    ent_lock = threading.Lock()
    topic_lock = threading.Lock()
    emb_lock = threading.Lock()

    return kw, ent, topic, emb, kw_lock, ent_lock, topic_lock, emb_lock



def _classify_page_topics(
        topic_classifier: TopicClassifier,
        topic_lock: threading.Lock | None,
        content: str,
        url: str,
        fast_topics: bool,
) -> dict:
    """Run topic classification for a page (content taxonomy)."""
    def _do():
        if fast_topics:
            topic_paths = topic_classifier.classify_fast(
                text=content, taxonomy="content",
                threshold=0.3, top_k=2, return_top_paths=5,
            )
            if not topic_paths or len(topic_paths) == 0 or len(topic_paths[0]) == 0:
                logger.warning(f"No topics found for page {url} with classify_fast, falling back to full classification")
                topic_paths = topic_classifier.classify(
                    text=content, taxonomy="content",
                    threshold=0.3, top_k=2, return_top_paths=5,
                )
            return topic_paths
        else:
            return topic_classifier.classify(
                text=content, taxonomy="content",
                threshold=0.3, top_k=2, return_top_paths=5,
            )

    if topic_lock is not None:
        with topic_lock:
            topic_paths = _do()
    else:
        topic_paths = _do()
    return _flatten_topics(topic_paths)


def process_page(
        url: str,
        page: dict,
        kw_extractor: KeywordExtractor,
        ent_extractor: EntityExtractor,
        topic_classifier: TopicClassifier,
        emb_generator: EmbeddingGenerator,
        kw_lock: threading.Lock | None = None,
        ent_lock: threading.Lock | None = None,
        topic_lock: threading.Lock | None = None,
        emb_lock: threading.Lock | None = None,
        fast_topics: bool = True,
) -> dict | None:
    content = page.get("content", "")
    title = page.get("title", "")
    if not content:
        logger.warning(f"Skipping page with no content: {url}")
        return None

    url_hash, _ = generate_url_hash(url)

    use_threads = kw_lock is not None

    def _kw():
        if kw_lock:
            with kw_lock:
                return kw_extractor.extract(content, top_n=30)
        return kw_extractor.extract(content, top_n=30)

    def _ent():
        if ent_lock:
            with ent_lock:
                return ent_extractor.extract(content)
        return ent_extractor.extract(content)

    def _emb():
        if emb_lock:
            with emb_lock:
                return emb_generator.generate(content, chunk=True)
        return emb_generator.generate(content, chunk=True)

    if use_threads:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="page-nlp") as pool:
            kw_future = pool.submit(_kw)
            ent_future = pool.submit(_ent)
            topic_future = pool.submit(
                _classify_page_topics, topic_classifier, topic_lock, content, url, fast_topics,
            )
            emb_future = pool.submit(_emb)

            keywords = kw_future.result()
            entities = ent_future.result()
            topics = topic_future.result()
            chunks, page_embedding = emb_future.result()
    else:
        keywords = _kw()
        entities = _ent()
        topics = _classify_page_topics(topic_classifier, None, content, url, fast_topics)
        chunks, page_embedding = _emb()

    description = content[:200] + "..." if len(content) > 200 else content

    return {
        "page_url_hash": url_hash,
        "keywords": keywords,
        "entities": entities,
        "topics": topics,
        "page_embedding": page_embedding.tolist(),
        "chunk_context": chunks,
        "meta_data": {
            "url": url,
            "title": title,
            "description": description,
        },
        "theme": page.get("theme", ""),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


def _classify_ad_topics(
        topic_classifier: TopicClassifier,
        topic_lock: threading.Lock | None,
        combined_text: str,
        ad_id: str,
        fast_topics: bool,
) -> dict:
    """Run topic classification for an ad (product taxonomy)."""
    def _do():
        if fast_topics:
            topic_paths = topic_classifier.classify_fast(
                text=combined_text, taxonomy="product",
                threshold=0.1, top_k=2, return_top_paths=5,
            )
            if not topic_paths or len(topic_paths) == 0 or len(topic_paths[0]) == 0:
                logger.warning(f"No topics found for ad {ad_id} with classify_fast, falling back to full classification")
                topic_paths = topic_classifier.classify(
                    text=combined_text, taxonomy="product",
                    threshold=0.3, top_k=2, return_top_paths=5,
                )
            return topic_paths
        else:
            return topic_classifier.classify(
                text=combined_text, taxonomy="product",
                threshold=0.3, top_k=2, return_top_paths=5,
            )

    if topic_lock is not None:
        with topic_lock:
            topic_paths = _do()
    else:
        topic_paths = _do()
    return _flatten_topics(topic_paths)


def process_ad(
        ad: dict,
        kw_extractor: KeywordExtractor,
        ent_extractor: EntityExtractor,
        topic_classifier: TopicClassifier,
        emb_generator: EmbeddingGenerator,
        kw_lock: threading.Lock | None = None,
        ent_lock: threading.Lock | None = None,
        topic_lock: threading.Lock | None = None,
        emb_lock: threading.Lock | None = None,
        fast_topics: bool = True,
        crawled_content: str = "",
) -> dict | None:

    ad_id = ad.get("id", "")
    headline = ad.get("creative", {}).get("headline", "")
    description = ad.get("creative", {}).get("description", "")

    combined_text = ". ".join(filter(None, [headline, description, crawled_content])).strip()
    if not combined_text:
        logger.warning(f"Skipping ad {ad_id} with no text")
        return None

    use_threads = kw_lock is not None

    def _kw():
        if kw_lock:
            with kw_lock:
                return kw_extractor.extract(combined_text, top_n=20)
        return kw_extractor.extract(combined_text, top_n=20)

    def _ent():
        if ent_lock:
            with ent_lock:
                return ent_extractor.extract(combined_text)
        return ent_extractor.extract(combined_text)

    def _emb():
        if emb_lock:
            with emb_lock:
                return emb_generator.generate(combined_text, chunk=False)
        return emb_generator.generate(combined_text, chunk=False)

    if use_threads:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="ad-nlp") as pool:
            kw_future = pool.submit(_kw)
            ent_future = pool.submit(_ent)
            topic_future = pool.submit(
                _classify_ad_topics, topic_classifier, topic_lock, combined_text, ad_id, fast_topics,
            )
            emb_future = pool.submit(_emb)

            keywords = kw_future.result()
            entities = ent_future.result()
            topics = topic_future.result()
            embedding = emb_future.result()
    else:
        # Sequential execution in a dedicated worker process
        keywords = _kw()
        entities = _ent()
        topics = _classify_ad_topics(topic_classifier, None, combined_text, ad_id, fast_topics)
        embedding = _emb()

    return {
        "ad_id": ad_id,
        "keywords": keywords,
        "entities": entities,
        "topics": topics,
        "embedding": embedding.tolist(),
        "content_category": ad.get("content_category", ""),
        "headline": headline,
        "description": description,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


def _flatten_topics(
        topic_paths: list[list[dict]],
) -> dict[str, dict]:
    """Flatten topic paths into a dict keyed by iab_id."""
    topics = {}
    for path in topic_paths:
        for topic in path:
            if topic and "iab_id" in topic:
                iab_id = topic["iab_id"]
                if iab_id not in topics:
                    topics[iab_id] = {
                        "name": topic.get("name", ""),
                        "iab_id": iab_id,
                        "tier": topic.get("tier", 1),
                        "score": topic.get("score", 0.0),
                    }
    return topics



_worker_kw = None
_worker_ent = None
_worker_topic = None
_worker_emb = None


def _worker_init():
    """Initialise NLP models inside a worker process."""
    global _worker_kw, _worker_ent, _worker_topic, _worker_emb
    logger.info(f"Worker {os.getpid()}: loading NLP models...")
    _worker_kw = KeywordExtractor()
    _worker_ent = EntityExtractor()
    _worker_topic = TopicClassifier()
    _worker_emb = EmbeddingGenerator()
    logger.info(f"Worker {os.getpid()}: NLP models ready")


def worker_process_page(args: tuple) -> dict | None:
    """Process a single page in a worker process (no locks needed)."""
    url, page_data, fast_topics = args
    return process_page(
        url, page_data,
        kw_extractor=_worker_kw, ent_extractor=_worker_ent,
        topic_classifier=_worker_topic, emb_generator=_worker_emb,
        fast_topics=fast_topics,
    )


def worker_process_ad(args: tuple) -> dict | None:
    """Process a single ad in a worker process (no locks needed)."""
    ad, crawled_content, fast_topics = args
    return process_ad(
        ad,
        kw_extractor=_worker_kw, ent_extractor=_worker_ent,
        topic_classifier=_worker_topic, emb_generator=_worker_emb,
        fast_topics=fast_topics,
        crawled_content=crawled_content,
    )


def worker_process_ad_batch(args: tuple) -> list[dict | None]:
    """Process a batch of ads in a single worker — batch model inference.

    Each NLP operation is batched across all ads in the batch, dramatically
    reducing per-item Python/model overhead.
    """
    ad_batch, crawled_contents, fast_topics = args

    texts = []
    valid_indices = []
    for i, (ad, crawled) in enumerate(zip(ad_batch, crawled_contents)):
        headline = ad.get("creative", {}).get("headline", "")
        description = ad.get("creative", {}).get("description", "")
        combined = ". ".join(filter(None, [headline, description, crawled])).strip()
        if combined:
            texts.append(combined)
            valid_indices.append(i)

    if not texts:
        return [None] * len(ad_batch)


    all_embeddings = _worker_emb.embedder.encode(
        texts, batch_size=128, convert_to_numpy=True, show_progress_bar=False
    )

    if fast_topics:
        topic_results = _worker_topic.classify_fast_batch(
            texts, taxonomy="product", threshold=0.1, top_k=2, return_top_paths=5,
        )
        if not topic_results or len(topic_results) == 0 or len(topic_results[0]) == 0:
            topic_results = _worker_topic.classify_batch(
                texts, taxonomy="product", threshold=0.3, top_k=2, return_top_paths=5,
            )
    else:
        topic_results = _worker_topic.classify_batch(
            texts, taxonomy="product", threshold=0.3, top_k=2, return_top_paths=5,
        )

    kw_results = [_worker_kw.extract(t, top_n=20) for t in texts]
    ent_results = [_worker_ent.extract(t) for t in texts]

    # 5. Assemble results
    results = [None] * len(ad_batch)
    for batch_idx, orig_idx in enumerate(valid_indices):
        ad = ad_batch[orig_idx]
        results[orig_idx] = {
            "ad_id": ad.get("id", ""),
            "keywords": kw_results[batch_idx],
            "entities": ent_results[batch_idx],
            "topics": _flatten_topics(topic_results[batch_idx]),
            "embedding": all_embeddings[batch_idx].tolist(),
            "content_category": ad.get("content_category", ""),
            "headline": ad.get("creative", {}).get("headline", ""),
            "description": ad.get("creative", {}).get("description", ""),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    return results


def worker_process_page_batch(args: tuple) -> list[dict | None]:
    """Process a batch of pages in a single worker, batch model inference."""
    page_batch, fast_topics = args

    texts = []
    valid_indices = []
    urls = []
    titles = []
    contents = []
    for i, (url, page_data) in enumerate(page_batch):
        content = page_data.get("content", "")
        title = page_data.get("title", "")
        if content:
            texts.append(content)
            valid_indices.append(i)
            urls.append(url)
            titles.append(title)
            contents.append(content)

    if not texts:
        return [None] * len(page_batch)

    if fast_topics:
        topic_results = _worker_topic.classify_fast_batch(
            texts, taxonomy="content", threshold=0.3, top_k=2, return_top_paths=5,
        )
        if not topic_results or len(topic_results) == 0 or len(topic_results[0]) == 0:
            topic_results = _worker_topic.classify_batch(
                texts, taxonomy="content", threshold=0.3, top_k=2, return_top_paths=5,
            )
    else:
        topic_results = _worker_topic.classify_batch(
            texts, taxonomy="content", threshold=0.3, top_k=2, return_top_paths=5,
        )

    kw_results = [_worker_kw.extract(t, top_n=30) for t in texts]
    ent_results = [_worker_ent.extract(t) for t in texts]

    emb_results = [_worker_emb.generate(t, chunk=True) for t in texts]

    results = [None] * len(page_batch)
    for batch_idx, orig_idx in enumerate(valid_indices):
        url = urls[batch_idx]
        title = titles[batch_idx]
        content = contents[batch_idx]
        url_hash, _ = generate_url_hash(url)
        chunks, page_embedding = emb_results[batch_idx]
        description = content[:200] + "..." if len(content) > 200 else content

        results[orig_idx] = {
            "page_url_hash": url_hash,
            "keywords": kw_results[batch_idx],
            "entities": ent_results[batch_idx],
            "topics": _flatten_topics(topic_results[batch_idx]),
            "page_embedding": page_embedding.tolist(),
            "chunk_context": chunks,
            "meta_data": {
                "url": url,
                "title": title,
                "description": description,
            },
            "theme": page_batch[orig_idx][1].get("theme", ""),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    return results

def main():
    parser = argparse.ArgumentParser(description="Generate NLP evaluation fixtures")
    parser.add_argument(
        "--fast", action="store_true",
        help="Use embedding-based topic classification (faster, 5x speedup)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--workers", type=int, default=min(os.cpu_count() or 4, 4),
        help="Number of worker processes (default: min(cpu_count, 4))",
    )
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="Batch size for batched processing (default: 32)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fast = args.fast
    workers = args.workers
    batch_size = args.batch_size
    logger.info(f"Topic classification mode: {'fast (embedding)' if fast else 'full (zero-shot)'}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Workers: {workers} (processes)")

    logger.info(f"Loading crawled pages from {CRAWLED_PAGES_PATH}")
    with open(CRAWLED_PAGES_PATH) as f:
        crawled_pages = json.load(f)
    logger.info(f"Loaded {len(crawled_pages)} pages")

    logger.info(f"Loading ads inventory from {ADS_INVENTORY_PATH}")
    with open(ADS_INVENTORY_PATH) as f:
        ads_inventory = json.load(f)
    logger.info(f"Loaded {len(ads_inventory)} ads")

    logger.info(f"Processing {len(crawled_pages)} pages with {workers} worker processes (batch_size={batch_size})...")
    t0 = time.time()
    page_contexts: list[dict] = []

    page_items = list(crawled_pages.items())
    page_batches = []
    for i in range(0, len(page_items), batch_size):
        batch_slice = page_items[i:i + batch_size]
        page_batches.append((batch_slice, fast))

    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_worker_init,
    ) as pool:
        future_to_idx = {
            pool.submit(worker_process_page_batch, batch): idx
            for idx, batch in enumerate(page_batches)
        }
        pages_done = 0
        total_pages = len(page_items)
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results = future.result()
                for result in results:
                    pages_done += 1
                    if result:
                        page_contexts.append(result)
            except Exception:
                pages_done += len(page_batches[idx][0])
                logger.exception(f"  Page batch {idx} FAILED")

            elapsed = time.time() - t0
            rate = pages_done / elapsed if elapsed > 0 else 0
            logger.info(f"  Pages [{pages_done}/{total_pages}] ({rate:.1f} pages/s)")

    logger.info(
        f"Processed {len(page_contexts)}/{len(crawled_pages)} pages in {time.time() - t0:.1f}s"
    )

    logger.info(f"Processing {len(ads_inventory)} ads with {workers} worker processes (batch_size={batch_size})...")
    t0 = time.time()
    ad_contexts: list[dict] = []

    ad_batches = []
    for i in range(0, len(ads_inventory), batch_size):
        batch_slice = ads_inventory[i:i + batch_size]
        crawled_list = [""] * len(batch_slice)
        ad_batches.append((batch_slice, crawled_list, fast))

    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_worker_init,
    ) as pool:
        future_to_idx = {
            pool.submit(worker_process_ad_batch, batch): idx
            for idx, batch in enumerate(ad_batches)
        }
        ads_done = 0
        total_ads = len(ads_inventory)
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results = future.result()
                for result in results:
                    ads_done += 1
                    if result:
                        ad_contexts.append(result)
            except Exception:
                ads_done += len(ad_batches[idx][0])
                logger.exception(f"  Ad batch {idx} FAILED")

            elapsed = time.time() - t0
            rate = ads_done / elapsed if elapsed > 0 else 0
            logger.info(f"  Ads [{ads_done}/{total_ads}] ({rate:.1f} ads/s)")

    logger.info(
        f"Processed {len(ad_contexts)}/{len(ads_inventory)} ads in {time.time() - t0:.1f}s"
    )

    # Write output
    pages_path = output_dir / "nlp_page_contexts.json"
    ads_path = output_dir / "nlp_ad_contexts.json"

    with open(pages_path, "w") as f:
        json.dump(page_contexts, f, indent=2)
    logger.info(f"Wrote {len(page_contexts)} page contexts to {pages_path}")

    with open(ads_path, "w") as f:
        json.dump(ad_contexts, f, indent=2)
    logger.info(f"Wrote {len(ad_contexts)} ad contexts to {ads_path}")

    # Summary
    page_sizes = [len(json.dumps(p)) for p in page_contexts]
    ad_sizes = [len(json.dumps(a)) for a in ad_contexts]
    logger.info(
        f"\nSummary:\n"
        f"  Pages: {len(page_contexts)} contexts, "
        f"avg {sum(page_sizes) // max(len(page_sizes), 1) // 1024}KB each, "
        f"total {sum(page_sizes) // 1024}KB\n"
        f"  Ads:   {len(ad_contexts)} contexts, "
        f"avg {sum(ad_sizes) // max(len(ad_sizes), 1) // 1024}KB each, "
        f"total {sum(ad_sizes) // 1024}KB\n"
        f"  Output: {output_dir}"
    )


if __name__ == "__main__":
    main()
