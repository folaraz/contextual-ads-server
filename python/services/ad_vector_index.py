import logging
from typing import List

import redis
from redis.commands.search.field import VectorField, NumericField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

logger = logging.getLogger(__name__)

INDEX_NAME = "idx:ads"
AD_KEY_PREFIX = "ad:"
EMBEDDING_DIM = 384
DISTANCE_METRIC = "COSINE"


class AdVectorIndex:
    def __init__(self, redis_client: redis.Redis):
        self.client = redis_client

    def create_index(self) -> bool:
        try:
            self.client.ft(INDEX_NAME).info()
            logger.info(f"Index {INDEX_NAME} already exists")
            return True
        except redis.ResponseError:
            pass

        try:
            schema = (
                NumericField("$.ad_id", as_name="ad_id"),
                VectorField(
                    "$.embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": EMBEDDING_DIM,
                        "DISTANCE_METRIC": DISTANCE_METRIC,
                    },
                    as_name="embedding",
                ),
            )

            definition = IndexDefinition(prefix=[AD_KEY_PREFIX], index_type=IndexType.JSON)
            self.client.ft(INDEX_NAME).create_index(schema, definition=definition)
            logger.info(f"Created vector index: {INDEX_NAME}")
            return True

        except Exception as e:
            logger.error(f"Failed to create index: {e}", exc_info=True)
            return False

    def index_ad(self, ad_id: int, embedding: List[float]) -> bool:
        try:
            if len(embedding) != EMBEDDING_DIM:
                logger.error(f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(embedding)}")
                return False

            key = f"{AD_KEY_PREFIX}{ad_id}"

            doc = {
                "ad_id": ad_id,
                "embedding": embedding,
            }

            self.client.json().set(key, "$", doc)
            logger.debug(f"Indexed ad {ad_id} in vector index")
            return True

        except Exception as e:
            logger.error(f"Failed to index ad: {e}", exc_info=True)
            return False

    def remove_ad(self, ad_id: int) -> bool:
        try:
            key = f"{AD_KEY_PREFIX}{ad_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to remove ad: {e}", exc_info=True)
            return False

    def drop_index(self) -> bool:
        try:
            self.client.ft(INDEX_NAME).dropindex(delete_documents=True)
            logger.info(f"Dropped index: {INDEX_NAME}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop index: {e}", exc_info=True)
            return False
