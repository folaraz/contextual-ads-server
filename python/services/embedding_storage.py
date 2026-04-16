"""
Embedding storage service for caching in Redis and backing up to PostgreSQL
"""

import json
import logging
from typing import List, Optional, Dict, Any

import numpy as np
import redis
from psycopg2.extras import execute_batch
from psycopg2.pool import SimpleConnectionPool

from .ad_vector_index import AdVectorIndex

logger = logging.getLogger(__name__)


class EmbeddingStorage:

    def __init__(self, redis_client: redis.Redis, pg_pool: SimpleConnectionPool):
        self.redis_client = redis_client
        self.pg_pool = pg_pool
        self.ad_vector_index = AdVectorIndex(redis_client)
        self.ad_vector_index.create_index()
        logger.info("EmbeddingStorage initialized")

    def store_ad_embedding(
            self,
            ad_id: int,
            embedding: List[float],
            cache_only: bool = False
    ) -> bool:
        try:
            # Store in vector index for KNN search
            self.ad_vector_index.index_ad(ad_id, embedding)

            # Store in PostgreSQL backup
            if not cache_only:
                conn = None
                try:
                    conn = self.pg_pool.getconn()
                    cursor = conn.cursor()

                    embedding_str = self._to_pgvector(embedding)

                    cursor.execute(
                        """
                        INSERT INTO ad_embeddings (ad_id, embedding)
                        VALUES (%s, %s::vector)
                        ON CONFLICT (ad_id)
                            DO UPDATE SET embedding  = EXCLUDED.embedding,
                                          updated_at = NOW()
                        """,
                        (ad_id, embedding_str)
                    )

                    conn.commit()
                    logger.debug(f"Backed up ad embedding for ad_id={ad_id} in PostgreSQL")

                except Exception as e:
                    if conn:
                        conn.rollback()
                    logger.error(f"Failed to backup ad embedding to PostgreSQL: {e}")
                    return False
                finally:
                    if conn:
                        cursor.close()
                        self.pg_pool.putconn(conn)

            return True

        except Exception as e:
            logger.error(f"Failed to store ad embedding: {e}", exc_info=True)
            return False

    def store_page_embedding(
            self,
            page_id: str,
            url: str,
            embedding: List[float],
            chunks: Optional[List[Dict[str, Any]]] = None,
            cache_only: bool = False
    ) -> bool:
        """
        Store page embedding and chunks in Redis cache and PostgreSQL

        Args:
            page_id: Page ID (page_url_hash)
            url: Page URL
            embedding: Page-level embedding vector
            chunks: List of chunks with embeddings
            cache_only: If True, only store in Redis cache

        Returns:
            True if successful, False otherwise
        """
        try:
            # Store page embedding and chunks in Redis via pipeline
            import os
            page_cache_ttl = int(os.getenv('REDIS_PAGE_CACHE_TTL', '2592000'))
            redis_key = f"page:embedding:{page_id}"
            pipe = self.redis_client.pipeline()
            pipe.set(redis_key, json.dumps(embedding))
            pipe.expire(redis_key, page_cache_ttl)

            if chunks:
                chunk_key = f"page:chunks:{page_id}"
                pipe.set(chunk_key, json.dumps(chunks))
                pipe.expire(chunk_key, page_cache_ttl)

            pipe.execute()
            logger.debug(f"Cached page embedding{f' and {len(chunks)} chunks' if chunks else ''} for page_url_hash={page_id} in Redis")

            # Store in PostgreSQL backup
            if not cache_only:
                conn = None
                try:
                    conn = self.pg_pool.getconn()
                    cursor = conn.cursor()

                    # Store page embedding
                    embedding_str = self._to_pgvector(embedding)
                    chunk_count = len(chunks) if chunks else 0

                    cursor.execute(
                        """
                        INSERT INTO page_embeddings (page_url_hash, url, embedding, chunk_count)
                        VALUES (%s, %s, %s::vector, %s)
                        ON CONFLICT (page_url_hash)
                            DO UPDATE SET embedding   = EXCLUDED.embedding,
                                          chunk_count = EXCLUDED.chunk_count,
                                          updated_at  = NOW()
                        RETURNING id
                        """,
                        (page_id, url, embedding_str, chunk_count)
                    )

                    # Store chunk embeddings
                    if chunks:
                        # Delete existing chunks
                        cursor.execute(
                            "DELETE FROM page_chunk_embeddings WHERE page_url_hash = %s",
                            (page_id,)
                        )

                        # Insert new chunks
                        chunk_data = []
                        for chunk in chunks:
                            chunk_embedding_str = self._to_pgvector(chunk['embedding'])
                            chunk_data.append((
                                page_id,
                                chunk['chunk_index'],
                                chunk.get('content', ''),
                                chunk_embedding_str
                            ))

                        execute_batch(cursor,
                            """
                            INSERT INTO page_chunk_embeddings (page_url_hash, chunk_index, content, embedding)
                            VALUES (%s, %s, %s, %s::vector)
                            """,
                            chunk_data
                        )

                    conn.commit()
                    logger.debug(f"Backed up page embedding and chunks for page_url_hash={page_id} in PostgreSQL")

                except Exception as e:
                    if conn:
                        conn.rollback()
                    logger.error(f"Failed to backup page embedding to PostgreSQL: {e}")
                    return False
                finally:
                    if conn:
                        cursor.close()
                        self.pg_pool.putconn(conn)

            return True

        except Exception as e:
            logger.error(f"Failed to store page embedding: {e}", exc_info=True)
            return False

    def get_ad_embedding(self, ad_id: int) -> Optional[np.ndarray]:
        """
        Get ad embedding from Redis cache, fallback to PostgreSQL

        Args:
            ad_id: Ad ID

        Returns:
            Embedding vector or None if not found
        """
        try:
            # Try Redis cache first
            redis_key = f"ad:embedding:{ad_id}"
            cached = self.redis_client.get(redis_key)

            if cached:
                logger.debug(f"Retrieved ad embedding from Redis cache for ad_id={ad_id}")
                return np.array(json.loads(cached))

            # Fallback to PostgreSQL
            conn = None
            try:
                conn = self.pg_pool.getconn()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT embedding FROM ad_embeddings WHERE ad_id = %s",
                    (ad_id,)
                )

                row = cursor.fetchone()
                if row:
                    embedding = self._from_pgvector(row[0])

                    # Cache in Redis as JSON for next time
                    self.redis_client.set(redis_key, json.dumps(embedding.tolist()))

                    logger.debug(f"Retrieved ad embedding from PostgreSQL and cached for ad_id={ad_id}")
                    return embedding

            finally:
                if conn:
                    cursor.close()
                    self.pg_pool.putconn(conn)

            logger.warning(f"Ad embedding not found for ad_id={ad_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get ad embedding: {e}", exc_info=True)
            return None

    def get_page_embedding(self, page_id: str) -> Optional[np.ndarray]:
        """
        Get page embedding from Redis cache, fallback to PostgreSQL

        Args:
            page_id: Page URL hash

        Returns:
            Embedding vector or None if not found
        """
        try:
            # Try Redis cache first
            redis_key = f"page:embedding:{page_id}"
            cached = self.redis_client.get(redis_key)

            if cached:
                logger.debug(f"Retrieved page embedding from Redis cache for page_url_hash={page_id}")
                return np.array(json.loads(cached))

            # Fallback to PostgreSQL
            conn = None
            try:
                conn = self.pg_pool.getconn()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT embedding FROM page_embeddings WHERE page_url_hash = %s",
                    (page_id,)
                )

                row = cursor.fetchone()
                if row:
                    embedding = self._from_pgvector(row[0])

                    # Cache in Redis as JSON for next time
                    self.redis_client.set(redis_key, json.dumps(embedding.tolist()))

                    logger.debug(f"Retrieved page embedding from PostgreSQL and cached for page_url_hash={page_id}")
                    return embedding

            finally:
                if conn:
                    cursor.close()
                    self.pg_pool.putconn(conn)

            logger.warning(f"Page embedding not found for page_url_hash={page_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get page embedding: {e}", exc_info=True)
            return None

    def search_similar_ads(
            self,
            embedding: List[float],
            limit: int = 10,
            threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar ads using cosine similarity

        Args:
            embedding: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of similar ads with scores
        """
        conn = None
        try:
            conn = self.pg_pool.getconn()
            cursor = conn.cursor()

            embedding_str = self._to_pgvector(embedding)

            cursor.execute(
                """
                SELECT ad_id, 1 - (embedding <=> %s::vector) as similarity
                FROM ad_embeddings
                WHERE 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_str, embedding_str, threshold, embedding_str, limit)
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'ad_id': row[0],
                    'similarity': float(row[1])
                })

            logger.info(f"Found {len(results)} similar ads")
            return results

        except Exception as e:
            logger.error(f"Failed to search similar ads: {e}", exc_info=True)
            return []
        finally:
            if conn:
                cursor.close()
                self.pg_pool.putconn(conn)

    def search_similar_pages(
            self,
            embedding: List[float],
            limit: int = 10,
            threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar pages using cosine similarity

        Args:
            embedding: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of similar pages with scores
        """
        conn = None
        try:
            conn = self.pg_pool.getconn()
            cursor = conn.cursor()

            embedding_str = self._to_pgvector(embedding)

            cursor.execute(
                """
                SELECT page_url_hash, url, 1 - (embedding <=> %s::vector) as similarity
                FROM page_embeddings
                WHERE 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_str, embedding_str, threshold, embedding_str, limit)
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'page_url_hash': row[0],
                    'url': row[1],
                    'similarity': float(row[2])
                })

            logger.info(f"Found {len(results)} similar pages")
            return results

        except Exception as e:
            logger.error(f"Failed to search similar pages: {e}", exc_info=True)
            return []
        finally:
            if conn:
                cursor.close()
                self.pg_pool.putconn(conn)


    @staticmethod
    def _to_pgvector(embedding: List[float]) -> str:
        """Convert embedding list to pgvector string format"""
        return '[' + ','.join(str(x) for x in embedding) + ']'

    @staticmethod
    def _from_pgvector(pgvector_str: str) -> np.ndarray:
        """Convert pgvector string to numpy array"""
        # Remove brackets and split by comma
        values = pgvector_str.strip('[]').split(',')
        return np.array([float(x) for x in values])
