"""
Context Processor Consumer

Unified consumer that processes both ad and page analysis messages from Kafka.
Extracts keywords, entities, topics, and embeddings, then stores results
in PostgreSQL and Redis.

Topics consumed:
- ad_analyze: Ad content analysis requests
- page_analyze: Page content analysis requests
"""

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import psycopg2.errors
import redis
import redis.asyncio as aioredis
from psycopg2.extras import execute_batch
from psycopg2.pool import SimpleConnectionPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import KafkaConfig, PostgresConfig, RedisConfig, CrawlerConfig, Topics
from consumer.async_base import AsyncKafkaConsumerBase
from processors import AdProcessor, PageProcessor
from services import EmbeddingStorage

logger = logging.getLogger(__name__)


class AdContextProcessor:
    """Processes ads to extract keywords, entities, topics, and embeddings"""

    def __init__(self, crawler_config: CrawlerConfig):
        self.crawler_config = crawler_config
        self.processor = AdProcessor(
            enable_crawler=crawler_config.enable_crawler,
            crawler_config={
                'user_agent': crawler_config.user_agent,
                'headless': crawler_config.headless,
                'timeout': crawler_config.timeout
            }
        )
        logger.info(f"AdContextProcessor initialized (crawler: {crawler_config.enable_crawler})")

    def process(self, ad_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single ad"""
        should_crawl = self.crawler_config.auto_crawl and self.crawler_config.enable_crawler
        return self.processor.process(ad_data, crawl_landing_page=should_crawl)


class AdDatabaseWriter:
    """Writes processed ad context to PostgreSQL and Redis"""

    def __init__(self, pg_pool: SimpleConnectionPool, redis_config: RedisConfig):
        self.pool = pg_pool
        self.redis_client = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            decode_responses=False
        )
        self.embedding_storage = EmbeddingStorage(self.redis_client, self.pool)
        logger.info("AdDatabaseWriter initialized")

    def write(self, context: Dict[str, Any]) -> bool:
        conn = None
        cursor = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()

            ad_id = context['ad_id']

            # Verify the ad exists before inserting targeting data
            cursor.execute("SELECT id FROM ads WHERE id = %s", (ad_id,))
            if cursor.fetchone() is None:
                logger.warning(f"Ad {ad_id} not found in database, skipping context write")
                return False

            if context.get('keywords'):
                self._insert_keywords(cursor, ad_id, context['keywords'])

            if context.get('entities'):
                self._insert_entities(cursor, ad_id, context['entities'])

            if context.get('topics'):
                self._insert_topics(cursor, ad_id, context['topics'])

            cursor.execute(
                "UPDATE ads SET status = 'ACTIVE', updated_at = NOW() WHERE id = %s AND status = 'PENDING_ANALYSIS'",
                (ad_id,)
            )
            conn.commit()

            if context.get('embedding'):
                self.embedding_storage.store_ad_embedding(ad_id=ad_id, embedding=context['embedding'], cache_only=False)

            logger.info(f"Wrote context for ad {ad_id}")
            return True

        except psycopg2.errors.ForeignKeyViolation as e:
            if conn:
                conn.rollback()
            logger.warning(f"Ad {context.get('ad_id')} was deleted before context could be written: {e}")
            return False
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error writing ad context: {e}", exc_info=True)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.pool.putconn(conn)

    def _insert_keywords(self, cursor, ad_id: int, keywords: Dict[str, float]):
        if not keywords:
            return
        data = [(ad_id, kw, max(0.0, min(score, 1.0))) for kw, score in keywords.items()]
        execute_batch(cursor, """
            INSERT INTO ad_targeting_keyword (ad_id, keyword, relevance_score)
            VALUES (%s, %s, %s)
            ON CONFLICT (ad_id, keyword) DO NOTHING
        """, data)

    def _insert_entities(self, cursor, ad_id: int, entities: List[Dict[str, str]]):
        if not entities:
            return
        for e in entities:
            entity_id = e.get('text', '').lower()
            if entity_id:
                cursor.execute("INSERT INTO entities (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                               (entity_id, e.get('text', '')))
        data = [(ad_id, e.get('text', '').lower(), e.get('type', 'UNKNOWN').lower()) for e in entities if e.get('text')]
        if data:
            execute_batch(cursor, """
                INSERT INTO ad_targeting_entity (ad_id, entity_id, entity_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (ad_id, entity_id, entity_type) DO NOTHING
            """, data)

    def _insert_topics(self, cursor, ad_id: int, topics: Dict[str, Dict[str, Any]]):
        if not topics:
            return
        data = []
        for iab_id, info in topics.items():
            try:
                topic_id_str = info.get('iab_id', iab_id)
                topic_id = int(topic_id_str) if topic_id_str else 0
                if topic_id <= 0:
                    continue
                data.append((ad_id, topic_id, min(float(info.get('score', 0.8)), 1.0)))
            except (ValueError, TypeError):
                continue
        if data:
            execute_batch(cursor, """
                INSERT INTO ad_targeting_topic (ad_id, topic_id, relevance_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (ad_id, topic_id) DO NOTHING
            """, data)



class PageContextProcessor:
    """Processes pages to extract keywords, entities, topics, and embeddings"""

    def __init__(self, crawler_config: CrawlerConfig):
        self.crawler_config = crawler_config
        self.processor = PageProcessor(
            enable_crawler=crawler_config.enable_crawler,
            crawler_config={
                'user_agent': crawler_config.user_agent,
                'headless': crawler_config.headless,
                'timeout': crawler_config.timeout
            }
        )
        logger.info(f"PageContextProcessor initialized (crawler: {crawler_config.enable_crawler})")

    def process(self, page_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single page"""
        should_crawl = self.crawler_config.auto_crawl and self.crawler_config.enable_crawler
        return self.processor.process(page_data, auto_crawl=should_crawl)


class PageDatabaseWriter:
    """Writes processed page context to Redis and PostgreSQL"""

    def __init__(self, redis_config: RedisConfig, pg_pool: SimpleConnectionPool):
        self.redis_client = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            decode_responses=False
        )
        self.async_redis = aioredis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            decode_responses=False
        )
        self.pg_pool = pg_pool
        self.embedding_storage = EmbeddingStorage(self.redis_client, pg_pool)
        self._page_cache_ttl = int(os.getenv('REDIS_PAGE_CACHE_TTL', '2592000'))
        logger.info("PageDatabaseWriter initialized")

    async def write_redis_async(self, context: Dict[str, Any]) -> bool:
        """Write page context to Redis cache only (async, non-blocking I/O)"""
        try:
            page_url_hash = context['page_url_hash']
            redis_key = f"page:{page_url_hash}"

            page_data = {
                "keywords": json.dumps(context.get('keywords', {})),
                "entities": json.dumps(context.get('entities', [])),
                "topics": json.dumps(context.get('topics', {})),
                "meta_data": json.dumps(context.get('meta_data', {})),
                "processed_at": context.get('processed_at', '')
            }
            pipe = self.async_redis.pipeline()
            pipe.hset(redis_key, mapping=page_data)
            pipe.expire(redis_key, self._page_cache_ttl)
            await pipe.execute()
            return True

        except Exception as e:
            logger.error(f"Error writing page context to Redis: {e}", exc_info=True)
            return False

    def write(self, context: Dict[str, Any]) -> bool:
        """Sync write fallback, uses sync Redis pipeline"""
        try:
            page_url_hash = context['page_url_hash']
            publisher_id = context.get('publisher_id')
            redis_key = f"page:{page_url_hash}"

            page_data = {
                "keywords": json.dumps(context.get('keywords', {})),
                "entities": json.dumps(context.get('entities', [])),
                "topics": json.dumps(context.get('topics', {})),
                "meta_data": json.dumps(context.get('meta_data', {})),
                "processed_at": context.get('processed_at', '')
            }
            pipe = self.redis_client.pipeline()
            pipe.hset(redis_key, mapping=page_data)
            pipe.expire(redis_key, self._page_cache_ttl)
            pipe.execute()

            self._store_page_context(context, publisher_id)

            if context.get('page_embedding'):
                url = context.get('meta_data', {}).get('url', '')
                self.embedding_storage.store_page_embedding(
                    page_id=page_url_hash, url=url,
                    embedding=context['page_embedding'],
                    chunks=context.get('chunk_context'), cache_only=False
                )

            logger.info(f"Wrote context for page {page_url_hash}")
            return True

        except Exception as e:
            logger.error(f"Error writing page context: {e}", exc_info=True)
            return False

    def _store_page_context(self, context: Dict[str, Any], publisher_id: Optional[str]) -> bool:
        """Store page context data in PostgreSQL"""
        conn = None
        cursor = None
        try:
            conn = self.pg_pool.getconn()
            cursor = conn.cursor()

            page_url_hash = context['page_url_hash']
            meta_data = context.get('meta_data', {})
            pub_id = int(publisher_id) if publisher_id else None

            # Upsert page_contexts
            cursor.execute("""
                INSERT INTO page_contexts (page_url_hash, url, title, description, publisher_id, crawled, processed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (page_url_hash)
                    DO UPDATE SET url = EXCLUDED.url, title = EXCLUDED.title, description = EXCLUDED.description,
                                  publisher_id = COALESCE(EXCLUDED.publisher_id, page_contexts.publisher_id),
                                  crawled = EXCLUDED.crawled, processed_at = EXCLUDED.processed_at, updated_at = NOW()
            """, (page_url_hash, meta_data.get('url', ''), meta_data.get('title', ''),
                  meta_data.get('description', ''), pub_id, context.get('crawled', False),
                  context.get('processed_at')))

            # Store keywords
            keywords = context.get('keywords', {})
            if keywords:
                cursor.execute("DELETE FROM page_keywords WHERE page_url_hash = %s", (page_url_hash,))
                keyword_data = [(page_url_hash, kw, score) for kw, score in keywords.items()]
                execute_batch(cursor, """
                    INSERT INTO page_keywords (page_url_hash, keyword, relevance_score)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (page_url_hash, keyword) DO UPDATE SET relevance_score = EXCLUDED.relevance_score
                """, keyword_data)

            # Store entities
            entities = context.get('entities', [])
            if entities:
                cursor.execute("DELETE FROM page_entities WHERE page_url_hash = %s", (page_url_hash,))
                entity_data = [(page_url_hash, e['text'], e['type']) for e in entities]
                execute_batch(cursor, """
                    INSERT INTO page_entities (page_url_hash, entity_text, entity_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (page_url_hash, entity_text, entity_type) DO NOTHING
                """, entity_data)

            # Store topics
            topics = context.get('topics', {})
            if topics:
                cursor.execute("DELETE FROM page_topics WHERE page_url_hash = %s", (page_url_hash,))
                topic_data = []
                for iab_id, topic in topics.items():
                    try:
                        topic_id = int(topic.get('iab_id', iab_id))
                        if topic_id <= 0:
                            continue
                        topic_data.append((page_url_hash, topic_id, str(iab_id), topic.get('name', ''),
                                           topic.get('tier', 0), topic.get('score', 1.0)))
                    except (ValueError, TypeError):
                        continue
                if topic_data:
                    execute_batch(cursor, """
                        INSERT INTO page_topics (page_url_hash, topic_id, iab_id, name, tier, relevance_score)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (page_url_hash, topic_id) DO UPDATE SET
                            relevance_score = EXCLUDED.relevance_score, name = EXCLUDED.name, tier = EXCLUDED.tier
                    """, topic_data)

            conn.commit()
            return True

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to store page context: {e}", exc_info=True)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.pg_pool.putconn(conn)


class ContextProcessorConsumer(AsyncKafkaConsumerBase):
    """
    Async Kafka consumer for both ad and page analysis messages.

    Processes multiple messages concurrently using asyncio:
    - Redis writes use async redis (non-blocking I/O)
    - PostgreSQL writes

    Routes messages to appropriate processors based on the topic:
    - ad_analyze → AdContextProcessor → AdDatabaseWriter
    - page_analyze → PageContextProcessor → PageDatabaseWriter
    """

    def __init__(self, kafka_config: KafkaConfig, pg_config: PostgresConfig,
                 redis_config: RedisConfig, crawler_config: CrawlerConfig):
        super().__init__(kafka_config, consumer_name="context_processor")
        self.pg_config = pg_config
        self.redis_config = redis_config
        self.crawler_config = crawler_config

        self.pg_pool: Optional[SimpleConnectionPool] = None
        self.ad_processor: Optional[AdContextProcessor] = None
        self.ad_writer: Optional[AdDatabaseWriter] = None
        self.page_processor: Optional[PageContextProcessor] = None
        self.page_writer: Optional[PageDatabaseWriter] = None

    def _init_components(self):
        """Initialize all processing components"""
        self.pg_pool = SimpleConnectionPool(
            self.pg_config.min_conn, self.pg_config.max_conn,
            host=self.pg_config.host, port=self.pg_config.port,
            database=self.pg_config.database, user=self.pg_config.user,
            password=self.pg_config.password
        )

        # Initialize ad processing components
        self.ad_processor = AdContextProcessor(self.crawler_config)
        self.ad_writer = AdDatabaseWriter(self.pg_pool, self.redis_config)

        # Initialize page processing components
        self.page_processor = PageContextProcessor(self.crawler_config)
        self.page_writer = PageDatabaseWriter(self.redis_config, self.pg_pool)

        self.log.info("Context processor components initialized", topics=self.kafka_config.topics)

    async def process_message_async(self, topic: str, key: Optional[str],
                                     value: Dict[str, Any]) -> bool:
        """Route message to the appropriate processor based on topic"""
        if topic == Topics.AD_ANALYZE or 'ad' in topic.lower():
            return await self._process_ad_message(topic, key, value)
        elif topic == Topics.PAGE_ANALYZE or 'page' in topic.lower():
            return await self._process_page_message(topic, key, value)
        else:
            self.log.warning("Unknown topic received", topic=topic)
            return True

    async def _process_ad_message(self, topic: str, key: Optional[str],
                                   value: Dict[str, Any]) -> bool:
        """Process an ad analysis message (async)"""
        from observability import start_span, add_span_attributes

        ad_id = int(value.get('ad_id', 0))
        if ad_id <= 0:
            self.log.warning("Invalid ad_id received", ad_id=ad_id)
            return True

        with start_span("fetch_ad_details", {"ad_id": ad_id}):
            ad_details = await self.run_in_thread(self._fetch_ad_details, ad_id)
        if not ad_details:
            self.log.warning("Could not fetch ad details", ad_id=ad_id)
            return True

        with start_span("process_ad_context", {"ad_id": ad_id}):
            context = await self.run_in_thread(self.ad_processor.process, ad_details)

        if context:
            with start_span("write_ad_context", {"ad_id": ad_id}):
                success = await self.run_in_thread(self.ad_writer.write, context)
            if success:
                self.log.info("Ad processed successfully", ad_id=ad_id)
                add_span_attributes({"ad.keywords_count": len(context.get('keywords', {}))})
            else:
                self.log.warning("Failed to write ad context, acknowledging message", ad_id=ad_id)
            return True

        self.log.error("Failed to process ad", ad_id=ad_id)
        return False

    async def _process_page_message(self, topic: str, key: Optional[str],
                                     value: Dict[str, Any]) -> bool:
        """Process a page analysis message"""
        from observability import start_span, add_span_attributes

        page_url_hash = value.get('page_url_hash', '')
        page_url = value.get('page_url', '')
        publisher_id = value.get('publisher_id', '')

        if not page_url_hash or not page_url:
            self.log.warning("Invalid page data received", page_url_hash=page_url_hash)
            return True

        page_data = {'page_url_hash': page_url_hash, 'page_url': page_url}

        with start_span("process_page_context", {"page_url_hash": page_url_hash}):
            context = await self.run_in_thread(self.page_processor.process, page_data)

        if context:
            context['publisher_id'] = publisher_id
            with start_span("write_page_context", {"page_url_hash": page_url_hash}):
                await self.page_writer.write_redis_async(context)

                await self.run_in_thread(
                    self.page_writer._store_page_context, context, publisher_id
                )
                if context.get('page_embedding'):
                    url = context.get('meta_data', {}).get('url', '')
                    await self.run_in_thread(
                        self.page_writer.embedding_storage.store_page_embedding,
                        page_url_hash, url, context['page_embedding'],
                        context.get('chunk_context'), False
                    )
            add_span_attributes({
                "page.keywords_count": len(context.get('keywords', {})),
                "page.topics_count": len(context.get('topics', {})),
            })
            return True

        self.log.error("Failed to process page", page_url_hash=page_url_hash)
        return False

    def _fetch_ad_details(self, ad_id: int) -> Optional[Dict[str, Any]]:
        """Fetch ad details from PostgreSQL"""
        conn = None
        cursor = None
        try:
            conn = self.pg_pool.getconn()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, headline, description, media_url, destination_url, creative_type FROM ads WHERE id = %s",
                (ad_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'ad_id': row[0],
                'headline': row[1] or '',
                'description': row[2] or '',
                'media_url': row[3] or '',
                'destination_url': row[4] or '',
                'creative_type': row[5] or ''
            }
        except Exception as e:
            self.log.error("Error fetching ad details", error=str(e), ad_id=ad_id)
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.pg_pool.putconn(conn)

    def _cleanup(self):
        """Clean up resources"""
        super()._cleanup()
        if self.pg_pool:
            self.pg_pool.closeall()


def main():
    from observability import init_observability, get_structured_logger

    # Initialize observability first
    init_observability("context_processor", version="1.0.0")
    log = get_structured_logger("context_processor")

    log.info("Starting Context Processor Consumer...")

    from config import ContextProcessorConfig

    kafka_config, pg_config, redis_config, crawler_config = ContextProcessorConfig.all_configs()

    log.info("Consumer configuration loaded",
             topics=kafka_config.topics,
             group_id=kafka_config.group_id)

    consumer = ContextProcessorConsumer(kafka_config, pg_config, redis_config, crawler_config)

    try:
        consumer.start()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    except Exception as e:
        log.error("Consumer failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
