import asyncio
import json

import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField, VectorField,
)
from redis.commands.search.index_definition import IndexDefinition, IndexType

from python.ingestion.context_generator import ContextGenerator


class Index:
    def __init__(self):
        self.client = redis.Redis(host='localhost', port=6379, decode_responses=True)

        try:
            self.client.ft("idx:ads").dropindex(delete_documents=True)
        except:
            pass
        self.client.delete("page:*")

        schema = (
            TextField("$.id", no_stem=True, as_name="id"),
            TextField("$.advertiser.name", no_stem=True, as_name="advertiser_name"),
            NumericField("$.advertiser.budget", as_name="advertiser_budget"),
            TextField("$.advertiser.currency", no_stem=True, as_name="advertiser_currency"),
            TextField("$.campaign.name", no_stem=True, as_name="campaign_name"),
            TextField("$.creative.headline", as_name="headline"),
            TextField("$.creative.description", as_name="description"),
            TextField("$.creative.image_url", no_stem=True, as_name="image_url"),
            TextField("$.creative.call_to_action", no_stem=True, as_name="call_to_action"),

            # Targeting fields
            TagField("$.targeting.countries[*]", as_name="countries"),
            TagField("$.targeting.entities[*]", as_name="targeting_entities"),
            TagField("$.targeting.languages[*]", as_name="languages"),
            TagField("$.targeting.topics[*].name", as_name="targeting_topics"),

            # Budget and status fields
            NumericField("$.daily_budget", as_name="daily_budget"),
            NumericField("$.remaining_budget", as_name="remaining_budget"),
            TextField("$.status", no_stem=True, as_name="status"),
            TextField("$.start_date", no_stem=True, as_name="start_date"),
            TextField("$.end_date", no_stem=True, as_name="end_date"),
            TextField("$.created_at", no_stem=True, as_name="created_at"),

            # Metrics
            NumericField("$.impressions", as_name="impressions"),
            NumericField("$.clicks", as_name="clicks"),
            NumericField("$.spend", as_name="spend"),

            TagField("$.ad_context.entities[*]", as_name="entities"),

            # Topics (array of objects with lab_id and name)
            TagField("$.ad_context.topics[*].name", as_name="topics"),
            NumericField("$.ad_context.topics[*].lab_id", as_name="topic_ids"),

            # Vector embedding
            VectorField("$.ad_context.embedding", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"},
                        as_name="embedding")
        )
        definition = IndexDefinition(prefix=["ad:"], index_type=IndexType.JSON)
        self.client.ft("idx:ads").create_index(fields=schema, definition=definition)

    # the one with more overlap with have more relevancy, also think of negated keywords
    def add_page_context(self, documents):
        with self.client.pipeline() as pipe:
            for document in documents:
                redis_key = "page:" + document["page_id"]
                page_context = {
                    "keywords": json.dumps(document["keywords"]),
                    "entities": json.dumps(document["entities"]),
                    "embedding": json.dumps(document["page_embedding"]),
                    "topics": json.dumps(document["topics"]),
                    "meta_data": json.dumps(document["meta_data"]),
                }
                chunks = document["chunks"]
                page_chunk_context = []
                for chunk in chunks:
                    embedding = chunk["embedding"]
                    content = chunk["content"]
                    page_chunk_context.append({
                        "embedding": embedding,
                        "content": content
                    })
                page_context["chunk_context"] = json.dumps(page_chunk_context)
                pipe.hset(redis_key, mapping=page_context)
            pipe.execute()

    def add_ad_context(self, documents):
        with self.client.pipeline() as pipe:
            for document in documents:
                ad_id = document["id"]
                computed_targeting = document.get("ad_context", {})
                keywords = computed_targeting.get("keywords", {}).keys()
                entities = computed_targeting.get("entities", [])
                topics = computed_targeting.get("topics", [])
                for kw in keywords:
                    pipe.sadd("kw:" + kw.lower(), ad_id)
                for ent in entities:
                    entity = ent.get("text", "").lower()
                    if entity:
                        pipe.sadd("ent:" + entity, ad_id)
                for topic in topics:
                    pipe.sadd("topic:" + topic.lower(), ad_id)
                pipe.json().set("ad:" + ad_id, "$", document)
            pipe.execute()

    def add_iab_taxonomy_mapping(self, taxonomy_mapping_json, is_content_to_product=True):
        with self.client.pipeline() as pipe:
            for key, value in taxonomy_mapping_json.items():
                if is_content_to_product:
                    pipe.hset("iab_product_to_content", key, value)
                else:
                    pipe.hset("iab_content_to_product", key, value)
            pipe.execute()


async def read_iab_taxonomy_json(path):
    with open(path, 'r') as f:
        taxonomy_json = json.load(f)
    return taxonomy_json


async def main():
    cg = ContextGenerator()
    index = Index()
    ad_results = await cg.generate_ad_context()
    print(f"Generated context for {len(ad_results)} ads.")
    index.add_ad_context(ad_results)
    print("Indexed ad context.")
    page_results = await cg.generate_page_context()
    print(f"Generated context for {len(page_results)} pages.")
    index.add_page_context(page_results)
    print(f"Indexed {len(page_results)} pages.")
    product_to_content_mapping = await read_iab_taxonomy_json(
        path='../data/ad_product_to_content_taxonomy_mapping.json')
    content_to_product_mapping = await read_iab_taxonomy_json(
        path='../data/content_to_ad_product_taxonomy_mapping.json')
    index.add_iab_taxonomy_mapping(product_to_content_mapping, is_content_to_product=False)
    index.add_iab_taxonomy_mapping(content_to_product_mapping, is_content_to_product=True)
    print("Indexed IAB taxonomy mappings.")


if __name__ == "__main__":
    asyncio.run(main())
