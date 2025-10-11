import json

import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
)
from redis.commands.search.index_definition import IndexDefinition, IndexType


class Index:
    def __init__(self):
        self.client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        schema = (
            TextField("$.id", no_stem=True, as_name="id"),
            TextField("$.advertiser.name", no_stem=True, as_name="advertiser_name"),
            TextField("$.advertiser.domain", no_stem=True, as_name="advertiser_domain"),
            NumericField("$.advertiser.budget", as_name="advertiser_budget"),
            TextField("$.advertiser.currency", no_stem=True, as_name="advertiser_currency"),
            TextField("$.campaign.name", no_stem=True, as_name="campaign_name"),
            NumericField("$.campaign.budget", as_name="campaign_budget"),
            TextField("$.creative.headline", as_name="headline"),
            TextField("$.creative.description", as_name="description"),
            TextField("$.creative.image_url", no_stem=True, as_name="image_url"),
            TagField("$.targeting.keywords[*]", as_name="keywords"),
            TagField("$.targeting.topics[*]", as_name="topics"),
            TagField("$.targeting.entities[*]", as_name="entities"),
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
                    "entities": json.dumps([entity["entity"].lower() for entity in document["entities"]]),
                    "embedding": json.dumps(document["embedding_vector"]),
                    "topics": json.dumps(document["topics_iab"]),
                    "meta_data": json.dumps(document["meta_data"]),
                }
                pipe.hset(redis_key, mapping=page_context)
            pipe.execute()

    def add_ad_context(self, documents):
        with self.client.pipeline() as pipe:
            for document in documents:
                ad_id = document["id"]
                pipe.hset("ad:" + ad_id, mapping=document)
            pipe.execute()
