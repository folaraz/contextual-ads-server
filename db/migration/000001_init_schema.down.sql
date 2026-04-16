ALTER TABLE ad_targeting_keyword DROP CONSTRAINT IF EXISTS unique_ad_keyword;
ALTER TABLE ad_targeting_entity DROP CONSTRAINT IF EXISTS unique_ad_entity;
ALTER TABLE ad_targeting_topic DROP CONSTRAINT IF EXISTS unique_ad_topic;
ALTER TABLE page_keywords DROP CONSTRAINT IF EXISTS unique_page_keyword;
ALTER TABLE page_entities DROP CONSTRAINT IF EXISTS unique_page_entity;
ALTER TABLE page_topics DROP CONSTRAINT IF EXISTS unique_page_topic;

DROP TRIGGER IF EXISTS update_page_contexts_updated_at ON page_contexts;
DROP TRIGGER IF EXISTS update_page_embeddings_updated_at ON page_embeddings;
DROP TRIGGER IF EXISTS update_ad_embeddings_updated_at ON ad_embeddings;
DROP TRIGGER IF EXISTS update_publishers_updated_at ON publishers;
DROP TRIGGER IF EXISTS update_ad_targeting_topic_updated_at ON ad_targeting_topic;
DROP TRIGGER IF EXISTS update_ad_targeting_entity_updated_at ON ad_targeting_entity;
DROP TRIGGER IF EXISTS update_ad_targeting_keyword_updated_at ON ad_targeting_keyword;
DROP TRIGGER IF EXISTS update_ad_targeting_country_updated_at ON ad_targeting_country;
DROP TRIGGER IF EXISTS update_ads_updated_at ON ads;
DROP TRIGGER IF EXISTS update_ad_sets_updated_at ON ad_sets;
DROP TRIGGER IF EXISTS update_campaigns_updated_at ON campaigns;
DROP TRIGGER IF EXISTS update_advertisers_updated_at ON advertisers;

DROP TABLE IF EXISTS page_topics;
DROP TABLE IF EXISTS page_entities;
DROP TABLE IF EXISTS page_keywords;
DROP TABLE IF EXISTS page_contexts;
DROP TABLE IF EXISTS page_chunk_embeddings;
DROP TABLE IF EXISTS page_embeddings;
DROP TABLE IF EXISTS ad_embeddings;
DROP TABLE IF EXISTS publishers;
DROP TABLE IF EXISTS iab_topic_mapping;
DROP TABLE IF EXISTS ad_targeting_topic;
DROP TABLE IF EXISTS ad_targeting_entity;
DROP TABLE IF EXISTS ad_targeting_keyword;
DROP TABLE IF EXISTS ad_targeting_country;
DROP TABLE IF EXISTS ad_targeting_device;
DROP TABLE IF EXISTS entities;
DROP TABLE IF EXISTS iab_topics;
DROP TABLE IF EXISTS ads;
DROP TABLE IF EXISTS ad_sets;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS advertisers;

DROP FUNCTION IF EXISTS update_updated_at_column();

DROP EXTENSION IF EXISTS vector;
