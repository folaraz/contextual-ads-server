#!/usr/bin/env python3
"""
Pre-process all crawled pages and ad creatives for simulation.

Runs NLP extraction (keywords, entities, topics, embeddings) on all pages
from crawled_pages.json and all PENDING_ANALYSIS ads from the database,
then stores results in Redis and PostgreSQL — the same storage destinations
used by the live Kafka consumer pipeline.

Prerequisites:
    - Infrastructure running (Redis, PostgreSQL)
    - Database migrated and seeded (ads exist in the ads table)

Usage:
    python scripts/preprocess_all.py [--fast] [--workers N] [--pages-only] [--ads-only] [--verify-only]

Makefile:
    make preprocess
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from psycopg2.pool import SimpleConnectionPool

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))

import redis as redis_lib

from config import PostgresConfig, RedisConfig
from consumer.context_processor import PageDatabaseWriter, AdDatabaseWriter

from scripts.generate_eval_fixtures import (
    _worker_init,
    worker_process_ad_batch,
    worker_process_page_batch,
)
from services.nlp_service import generate_url_hash
from services.ad_vector_index import AdVectorIndex, AD_KEY_PREFIX

BATCH_SIZE = 32

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("preprocess_all")

PROJECT_ROOT = PYTHON_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
CRAWLED_PAGES_PATH = DATA_DIR / "crawled_pages.json"
CRAWLED_ADVERTISERS_PATH = DATA_DIR / "crawled_advertisers.json"
ADS_INVENTORY_PATH = DATA_DIR / "ads_inventory.json"
PREPROCESSED_URLS_PATH = DATA_DIR / "preprocessed_urls.txt"


def create_pg_pool(pg_config: PostgresConfig) -> SimpleConnectionPool:
    return SimpleConnectionPool(
        pg_config.min_conn, pg_config.max_conn,
        host=pg_config.host, port=pg_config.port,
        database=pg_config.database, user=pg_config.user,
        password=pg_config.password,
    )


def fetch_pending_ads(pg_pool: SimpleConnectionPool) -> list[dict]:
    """Fetch ads that need NLP processing from PostgreSQL.

    JOINs through ad_sets → campaigns to retrieve the advertiser_id,
    which is used to look up crawled advertiser content for NLP enrichment.
    """
    conn = None
    try:
        conn = pg_pool.getconn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT a.id, a.headline, a.description, a.media_url, "
            "       a.destination_url, a.creative_type, c.advertiser_id "
            "FROM ads a "
            "JOIN ad_sets s ON a.ad_set_id = s.id "
            "JOIN campaigns c ON s.campaign_id = c.id "
            "WHERE a.status = 'PENDING_ANALYSIS'"
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            {
                "ad_id": row[0],
                "headline": row[1] or "",
                "description": row[2] or "",
                "media_url": row[3] or "",
                "destination_url": row[4] or "",
                "creative_type": row[5] or "",
                "advertiser_id": row[6],
            }
            for row in rows
        ]
    finally:
        if conn:
            pg_pool.putconn(conn)


def ad_row_to_eval_format(ad: dict) -> dict:
    """Convert a DB ad row to the format expected by process_ad() from generate_eval_fixtures.

    process_ad() expects the ads_inventory.json format with nested 'creative' dict.
    """
    return {
        "id": ad["ad_id"],
        "creative": {
            "headline": ad["headline"],
            "description": ad["description"],
        },
    }


def fetch_processed_page_hashes(pg_pool: SimpleConnectionPool) -> set[str]:
    """Return the set of page_url_hash values already stored in page_contexts."""
    conn = None
    try:
        conn = pg_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("SELECT page_url_hash FROM page_contexts")
        hashes = {row[0] for row in cursor.fetchall()}
        cursor.close()
        return hashes
    finally:
        if conn:
            pg_pool.putconn(conn)


def fetch_processed_ad_ids(pg_pool: SimpleConnectionPool) -> set[int]:
    """Return the set of ad IDs that already have embeddings stored.

    This acts as a belt-and-suspenders check alongside the PENDING_ANALYSIS
    status filter — catching ads whose status update succeeded but might be
    re-queued, or where a partial re-run is happening.
    """
    conn = None
    try:
        conn = pg_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("SELECT ad_id FROM ad_embeddings")
        ids = {row[0] for row in cursor.fetchall()}
        cursor.close()
        return ids
    finally:
        if conn:
            pg_pool.putconn(conn)



def fetch_redis_cached_page_hashes(redis_config: RedisConfig) -> set[str]:
    """Return the set of page_url_hash values currently cached in Redis."""
    client = redis_lib.Redis(
        host=redis_config.host, port=redis_config.port,
        db=redis_config.db, decode_responses=True,
    )
    hashes = set()
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor=cursor, match="page:*", count=500)
        for key in keys:
            parts = key.split(":")
            # Only count base page keys (page:{hash}), not page:embedding:{hash} or page:chunks:{hash}
            if len(parts) == 2:
                hashes.add(parts[1])
        if cursor == 0:
            break
    client.close()
    return hashes


def fetch_redis_indexed_ad_ids(redis_config: RedisConfig) -> set[int]:
    """Return the set of ad IDs currently in the Redis Search vector index."""
    client = redis_lib.Redis(
        host=redis_config.host, port=redis_config.port,
        db=redis_config.db, decode_responses=True,
    )
    ad_ids = set()
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor=cursor, match=f"{AD_KEY_PREFIX}*", count=500)
        for key in keys:
            # ad:{id} keys — skip ad:embedding:{id}
            parts = key.split(":")
            if len(parts) == 2:
                try:
                    ad_ids.add(int(parts[1]))
                except ValueError:
                    pass
        if cursor == 0:
            break
    client.close()
    return ad_ids


def repopulate_pages_redis(pg_pool: SimpleConnectionPool, redis_config: RedisConfig,
                           hashes: set[str]) -> int:
    """Re-cache page contexts from PostgreSQL into Redis for the given hashes.

    This avoids expensive NLP reprocessing — it reads already-computed data
    from PostgreSQL and writes it back into Redis.
    """
    if not hashes:
        return 0

    client = redis_lib.Redis(
        host=redis_config.host, port=redis_config.port,
        db=redis_config.db, decode_responses=False,
    )
    page_cache_ttl = int(os.getenv('REDIS_PAGE_CACHE_TTL', '2592000'))

    conn = None
    ok = 0
    try:
        conn = pg_pool.getconn()
        cursor = conn.cursor()
        hash_list = list(hashes)

        # Fetch page contexts
        cursor.execute(
            "SELECT page_url_hash, url, title, description, processed_at "
            "FROM page_contexts WHERE page_url_hash = ANY(%s)",
            (hash_list,)
        )
        contexts = {}
        for row in cursor.fetchall():
            contexts[row[0]] = {
                "url": row[1] or "",
                "title": row[2] or "",
                "description": row[3] or "",
                "processed_at": row[4].isoformat() if row[4] else "",
            }

        # Fetch keywords grouped by hash
        cursor.execute(
            "SELECT page_url_hash, keyword, relevance_score "
            "FROM page_keywords WHERE page_url_hash = ANY(%s)",
            (hash_list,)
        )
        keywords_by_hash: dict[str, dict] = {}
        for row in cursor.fetchall():
            keywords_by_hash.setdefault(row[0], {})[row[1]] = float(row[2])

        # Fetch entities grouped by hash
        cursor.execute(
            "SELECT page_url_hash, entity_text, entity_type "
            "FROM page_entities WHERE page_url_hash = ANY(%s)",
            (hash_list,)
        )
        entities_by_hash: dict[str, list] = {}
        for row in cursor.fetchall():
            entities_by_hash.setdefault(row[0], []).append({"text": row[1], "type": row[2]})

        # Fetch topics grouped by hash
        cursor.execute(
            "SELECT page_url_hash, topic_id, iab_id, name, tier, relevance_score "
            "FROM page_topics WHERE page_url_hash = ANY(%s)",
            (hash_list,)
        )
        topics_by_hash: dict[str, dict] = {}
        for row in cursor.fetchall():
            topics_by_hash.setdefault(row[0], {})[str(row[2])] = {
                "iab_id": str(row[2]),
                "name": row[3] or "",
                "tier": row[4] or 0,
                "score": float(row[5]),
            }

        # Fetch page embeddings
        cursor.execute(
            "SELECT page_url_hash, embedding "
            "FROM page_embeddings WHERE page_url_hash = ANY(%s)",
            (hash_list,)
        )
        embeddings_by_hash: dict[str, str] = {}
        for row in cursor.fetchall():
            # pgvector returns string like '[0.1,0.2,...]'
            vec_str = row[1].strip('[]')
            embeddings_by_hash[row[0]] = json.dumps([float(x) for x in vec_str.split(',')])

        # Fetch chunk embeddings
        cursor.execute(
            "SELECT page_url_hash, chunk_index, content, embedding "
            "FROM page_chunk_embeddings WHERE page_url_hash = ANY(%s) "
            "ORDER BY page_url_hash, chunk_index",
            (hash_list,)
        )
        chunks_by_hash: dict[str, list] = {}
        for row in cursor.fetchall():
            vec_str = row[3].strip('[]')
            chunks_by_hash.setdefault(row[0], []).append({
                "chunk_index": row[1],
                "content": row[2] or "",
                "embedding": [float(x) for x in vec_str.split(',')],
            })

        cursor.close()

        # Write to Redis
        for h in hashes:
            ctx = contexts.get(h)
            if not ctx:
                continue
            try:
                redis_key = f"page:{h}"
                page_data = {
                    "keywords": json.dumps(keywords_by_hash.get(h, {})),
                    "entities": json.dumps(entities_by_hash.get(h, [])),
                    "topics": json.dumps(topics_by_hash.get(h, {})),
                    "meta_data": json.dumps({
                        "url": ctx["url"],
                        "title": ctx["title"],
                        "description": ctx["description"],
                    }),
                    "processed_at": ctx["processed_at"],
                }
                pipe = client.pipeline()
                pipe.hset(redis_key, mapping=page_data)
                pipe.expire(redis_key, page_cache_ttl)

                if h in embeddings_by_hash:
                    emb_key = f"page:embedding:{h}"
                    pipe.set(emb_key, embeddings_by_hash[h])
                    pipe.expire(emb_key, page_cache_ttl)

                if h in chunks_by_hash:
                    chunk_key = f"page:chunks:{h}"
                    pipe.set(chunk_key, json.dumps(chunks_by_hash[h]))
                    pipe.expire(chunk_key, page_cache_ttl)

                pipe.execute()
                ok += 1
            except Exception as e:
                logger.warning(f"Failed to re-cache page {h[:16]}...: {e}")

    except Exception as e:
        logger.error(f"Error during page Redis repopulation: {e}", exc_info=True)
    finally:
        if conn:
            pg_pool.putconn(conn)
        client.close()

    return ok


def repopulate_ads_redis(pg_pool: SimpleConnectionPool, redis_config: RedisConfig,
                         ad_ids: set[int]) -> int:
    """Re-index ad embeddings from PostgreSQL into the Redis Search vector index."""
    if not ad_ids:
        return 0

    client = redis_lib.Redis(
        host=redis_config.host, port=redis_config.port,
        db=redis_config.db, decode_responses=False,
    )
    ad_index = AdVectorIndex(client)
    ad_index.create_index()

    conn = None
    ok = 0
    try:
        conn = pg_pool.getconn()
        cursor = conn.cursor()
        id_list = list(ad_ids)

        cursor.execute(
            "SELECT ad_id, embedding FROM ad_embeddings WHERE ad_id = ANY(%s)",
            (id_list,)
        )
        for row in cursor.fetchall():
            ad_id = row[0]
            vec_str = row[1].strip('[]')
            embedding = [float(x) for x in vec_str.split(',')]
            if ad_index.index_ad(ad_id, embedding):
                ok += 1
            else:
                logger.warning(f"Failed to re-index ad {ad_id}")

        cursor.close()
    except Exception as e:
        logger.error(f"Error during ad Redis repopulation: {e}", exc_info=True)
    finally:
        if conn:
            pg_pool.putconn(conn)
        client.close()

    return ok


def verify(pg_pool: SimpleConnectionPool, redis_config: RedisConfig,
           expected_pages: int, expected_ads: int):
    """Verify that all pages and ads have been processed."""

    conn = pg_pool.getconn()
    cursor = conn.cursor()

    checks = []

    redis_page_count = len(fetch_redis_cached_page_hashes(redis_config))
    cursor.execute("SELECT COUNT(*) FROM page_contexts")
    pg_pages = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM page_embeddings")
    pg_page_embeds = cursor.fetchone()[0]
    checks.append(("Pages in Redis", redis_page_count, expected_pages))
    checks.append(("Pages in PostgreSQL", pg_pages, expected_pages))
    checks.append(("Page embeddings in PostgreSQL", pg_page_embeds, expected_pages))

    # Ad checks
    cursor.execute("SELECT COUNT(*) FROM ads WHERE status = 'ACTIVE'")
    active_ads = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ad_embeddings")
    pg_ad_embeds = cursor.fetchone()[0]
    redis_ad_count = len(fetch_redis_indexed_ad_ids(redis_config))
    checks.append(("Active ads in PostgreSQL", active_ads, expected_ads))
    checks.append(("Ad embeddings in PostgreSQL", pg_ad_embeds, expected_ads))
    checks.append(("Ads in Redis Search index", redis_ad_count, expected_ads))

    cursor.close()
    pg_pool.putconn(conn)

    # Print results
    all_ok = True
    logger.info("\n=== Verification Results ===")
    for label, actual, expected in checks:
        status = "OK" if actual == expected else "MISMATCH"
        if status == "MISMATCH":
            all_ok = False
        logger.info(f"  {label}: {actual} / {expected} [{status}]")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Pre-process pages and ads for simulation")
    parser.add_argument("--fast", action="store_true",
                        help="Use embedding-based topic classification (faster)")
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 4, 4),
                        help="Number of worker processes (default: min(cpu_count, 4))")
    parser.add_argument("--pages-only", action="store_true",
                        help="Only process pages")
    parser.add_argument("--ads-only", action="store_true",
                        help="Only process ads")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only run verification checks")
    parser.add_argument("--force-recache", action="store_true",
                        help="Force re-populate Redis cache from PostgreSQL for all processed pages and ads")
    args = parser.parse_args()

    pg_config = PostgresConfig.from_env()
    redis_config = RedisConfig.from_env()
    pg_pool = create_pg_pool(pg_config)

    # Load crawled pages for counts / processing
    with open(CRAWLED_PAGES_PATH) as f:
        crawled_pages = json.load(f)
    total_pages = len(crawled_pages)

    # Load crawled advertiser content for enriching ad NLP processing
    crawled_advertiser_content: dict[int, str] = {}
    if CRAWLED_ADVERTISERS_PATH.exists():
        with open(CRAWLED_ADVERTISERS_PATH) as f:
            crawled_advertisers = json.load(f)
        for _url, entry in crawled_advertisers.items():
            adv_id = entry.get("advertiser_id")
            content = entry.get("content", "")
            if adv_id and content:
                if adv_id in crawled_advertiser_content:
                    crawled_advertiser_content[adv_id] += ". " + content
                else:
                    crawled_advertiser_content[adv_id] = content
        logger.info(f"Loaded crawled content for {len(crawled_advertiser_content)} advertisers")
    else:
        logger.info("No crawled_advertisers.json found — ads will use headline/description only")

    if args.verify_only:
        # Count expected ads from DB
        conn = pg_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ads")
        total_ads = cursor.fetchone()[0]
        cursor.close()
        pg_pool.putconn(conn)

        ok = verify(pg_pool, redis_config, total_pages, total_ads)
        pg_pool.closeall()
        sys.exit(0 if ok else 1)

    page_writer = PageDatabaseWriter(redis_config, pg_pool)
    ad_writer = AdDatabaseWriter(pg_pool, redis_config)

    processed_urls = []

    if not args.ads_only:
        already_in_pg = fetch_processed_page_hashes(pg_pool)
        already_in_redis = set() if args.force_recache else fetch_redis_cached_page_hashes(redis_config)

        pages_to_process = {}
        pages_to_recache: list[str] = []  # hashes in PG but missing from Redis
        page_skipped = 0

        for url, page_data in crawled_pages.items():
            url_hash, _ = generate_url_hash(url)
            if url_hash in already_in_pg:
                if url_hash in already_in_redis:
                    page_skipped += 1
                else:
                    pages_to_recache.append(url_hash)
                processed_urls.append(url)
            else:
                pages_to_process[url] = page_data

        # Re-cache pages from PostgreSQL → Redis (no NLP reprocessing needed)
        if pages_to_recache:
            logger.info(f"Phase 1: Re-caching {len(pages_to_recache)} pages from PostgreSQL to Redis...")
            t0_recache = time.time()
            recached = repopulate_pages_redis(pg_pool, redis_config, set(pages_to_recache))
            logger.info(
                f"Phase 1: Re-cached {recached}/{len(pages_to_recache)} pages in "
                f"{time.time() - t0_recache:.1f}s"
            )

        pages_remaining = len(pages_to_process)
        if page_skipped > 0:
            logger.info(f"Phase 1: Skipping {page_skipped} already-processed pages (in PG + Redis)")

        if pages_remaining == 0:
            logger.info("Phase 1: All pages already processed — nothing to do")
        else:
            num_batches = (pages_remaining + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(
                f"Phase 1: Processing {pages_remaining}/{total_pages} pages in {num_batches} batches "
                f"(batch_size={BATCH_SIZE}) with {args.workers} worker processes..."
            )
            t0 = time.time()

            page_ok = 0
            page_fail = 0
            pages_done = 0

            # Build batches of (url, page_data) pairs
            page_items = list(pages_to_process.items())
            batches = []
            batch_urls = []
            for batch_start in range(0, pages_remaining, BATCH_SIZE):
                batch_slice = page_items[batch_start:batch_start + BATCH_SIZE]
                batches.append((batch_slice, args.fast))
                batch_urls.append([url for url, _ in batch_slice])

            with ProcessPoolExecutor(
                max_workers=args.workers,
                initializer=_worker_init,
            ) as pool:
                future_to_batch_idx = {
                    pool.submit(worker_process_page_batch, batch): batch_idx
                    for batch_idx, batch in enumerate(batches)
                }
                for future in as_completed(future_to_batch_idx):
                    batch_idx = future_to_batch_idx[future]
                    urls_in_batch = batch_urls[batch_idx]
                    try:
                        results = future.result()
                        for j, context in enumerate(results):
                            url = urls_in_batch[j]
                            pages_done += 1
                            if context is None:
                                page_fail += 1
                                continue
                            success = page_writer.write(context)
                            if success:
                                page_ok += 1
                                processed_urls.append(url)
                            else:
                                page_fail += 1
                                logger.warning(f"  Write failed: {url[:80]}")
                    except Exception:
                        page_fail += len(urls_in_batch)
                        pages_done += len(urls_in_batch)
                        logger.exception(f"  Page batch {batch_idx} FAILED")

                    elapsed = time.time() - t0
                    rate = pages_done / elapsed if elapsed > 0 else 0
                    eta = (pages_remaining - pages_done) / rate if rate > 0 else 0
                    logger.info(
                        f"  [{pages_done}/{pages_remaining}] {page_ok} OK, {page_fail} failed "
                        f"({rate:.1f} pages/s, ETA {eta:.0f}s)"
                    )

            logger.info(f"Phase 1 complete: {page_ok} OK, {page_fail} failed, {page_skipped} skipped in {time.time() - t0:.1f}s")

    if not args.pages_only:
        # Re-index ad embeddings missing from Redis (same pattern as pages)
        already_processed_ads = fetch_processed_ad_ids(pg_pool)
        already_in_redis_ads = set() if args.force_recache else fetch_redis_indexed_ad_ids(redis_config)

        ads_to_reindex = already_processed_ads - already_in_redis_ads
        if ads_to_reindex:
            logger.info(f"Phase 2: Re-indexing {len(ads_to_reindex)} ads from PostgreSQL to Redis...")
            t0_reindex = time.time()
            reindexed = repopulate_ads_redis(pg_pool, redis_config, ads_to_reindex)
            logger.info(
                f"Phase 2: Re-indexed {reindexed}/{len(ads_to_reindex)} ads in "
                f"{time.time() - t0_reindex:.1f}s"
            )

        logger.info("Phase 2: Fetching PENDING_ANALYSIS ads from database...")
        pending_ads = fetch_pending_ads(pg_pool)

        # Skip ads that already have embeddings (already fully processed)
        ad_skipped = 0
        ads_to_process = []
        for ad in pending_ads:
            if ad["ad_id"] in already_processed_ads:
                ad_skipped += 1
            else:
                ads_to_process.append(ad)

        if ad_skipped > 0:
            logger.info(f"Phase 2: Skipping {ad_skipped} already-processed ads")

        total_ads = len(ads_to_process)

        if total_ads == 0:
            if ad_skipped == 0 and not ads_to_reindex:
                logger.warning("No PENDING_ANALYSIS ads found. Have you run 'make seed'?")
            else:
                logger.info("Phase 2: All ads already processed — nothing to do")
        else:
            num_batches = (total_ads + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(
                f"Phase 2: Processing {total_ads} ads in {num_batches} batches "
                f"(batch_size={BATCH_SIZE}) with {args.workers} worker processes..."
            )
            t0 = time.time()

            ad_ok = 0
            ad_fail = 0
            ads_done = 0

            # Build batches: each batch is (ad_list, crawled_list, fast_topics)
            batches = []
            batch_ad_rows = []  # parallel list: original ad rows per batch
            for batch_start in range(0, total_ads, BATCH_SIZE):
                batch_slice = ads_to_process[batch_start:batch_start + BATCH_SIZE]
                ad_dicts = [ad_row_to_eval_format(ad) for ad in batch_slice]
                crawled_list = [
                    crawled_advertiser_content.get(ad.get("advertiser_id"), "")
                    for ad in batch_slice
                ]
                batches.append((ad_dicts, crawled_list, args.fast))
                batch_ad_rows.append(batch_slice)

            with ProcessPoolExecutor(
                max_workers=args.workers,
                initializer=_worker_init,
            ) as pool:
                future_to_batch_idx = {
                    pool.submit(worker_process_ad_batch, batch): batch_idx
                    for batch_idx, batch in enumerate(batches)
                }
                for future in as_completed(future_to_batch_idx):
                    batch_idx = future_to_batch_idx[future]
                    original_rows = batch_ad_rows[batch_idx]
                    try:
                        results = future.result()
                        for j, context in enumerate(results):
                            ad = original_rows[j]
                            ad_id = ad["ad_id"]
                            ads_done += 1
                            if context is None:
                                ad_fail += 1
                                continue

                            # worker returns ad_id as string; writer needs integer PK
                            context["ad_id"] = ad_id

                            success = ad_writer.write(context)
                            if success:
                                ad_ok += 1
                            else:
                                ad_fail += 1
                                logger.warning(f"  Write failed: ad_id={ad_id}")
                    except Exception:
                        ad_fail += len(original_rows)
                        ads_done += len(original_rows)
                        logger.exception(f"  Batch {batch_idx} FAILED")

                    # Progress every batch
                    elapsed = time.time() - t0
                    rate = ads_done / elapsed if elapsed > 0 else 0
                    eta = (total_ads - ads_done) / rate if rate > 0 else 0
                    logger.info(
                        f"  [{ads_done}/{total_ads}] {ad_ok} OK, {ad_fail} failed "
                        f"({rate:.1f} ads/s, ETA {eta:.0f}s)"
                    )

            logger.info(f"Phase 2 complete: {ad_ok} OK, {ad_fail} failed, {ad_skipped} skipped in {time.time() - t0:.1f}s")


    if processed_urls:
        with open(PREPROCESSED_URLS_PATH, "w") as f:
            for url in sorted(processed_urls):
                f.write(url + "\n")
        logger.info(f"Phase 3: Wrote {len(processed_urls)} URLs to {PREPROCESSED_URLS_PATH}")


    logger.info("Phase 4: Verifying...")
    conn = pg_pool.getconn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ads")
    expected_ads = cursor.fetchone()[0]
    cursor.close()
    pg_pool.putconn(conn)

    ok = verify(pg_pool, redis_config, total_pages, expected_ads)

    pg_pool.closeall()

    if ok:
        logger.info("All checks passed!")
    else:
        logger.warning("Some checks failed — see above for details")
        sys.exit(1)


if __name__ == "__main__":
    main()
