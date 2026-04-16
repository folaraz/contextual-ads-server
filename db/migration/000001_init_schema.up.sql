CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS
$$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE advertisers
(
    id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       TEXT NOT NULL,
    website    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER update_advertisers_updated_at
    BEFORE UPDATE
    ON advertisers
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE campaigns
(
    id            INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    advertiser_id INT REFERENCES advertisers (id) ON DELETE CASCADE,
    name          TEXT        NOT NULL,

    status        TEXT        NOT NULL CHECK (status IN ('ACTIVE', 'PAUSED', 'COMPLETED')),
    total_budget  BIGINT CHECK (total_budget >= 0),

    start_date    TIMESTAMPTZ NOT NULL,
    end_date      TIMESTAMPTZ CHECK (end_date > start_date),

    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_campaigns_advertiser_id ON campaigns (advertiser_id);

CREATE TRIGGER update_campaigns_updated_at
    BEFORE UPDATE
    ON campaigns
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE ad_sets
(
    id                 INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id        INT REFERENCES campaigns (id) ON DELETE CASCADE,
    name               TEXT,

    bid_amount_cents   BIGINT CHECK (bid_amount_cents >= 0),
    daily_budget_cents BIGINT CHECK (daily_budget_cents >= 0),
    pricing_model      TEXT CHECK (pricing_model IN ('CPC', 'CPM')),


    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ad_sets_campaign_id ON ad_sets (campaign_id);

CREATE TRIGGER update_ad_sets_updated_at
    BEFORE UPDATE
    ON ad_sets
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE ads
(
    id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_set_id       INT REFERENCES ad_sets (id) ON DELETE CASCADE,

    headline        TEXT,
    description     TEXT,
    creative_type   TEXT CHECK (creative_type IN ('banner')),
    media_url       TEXT,
    destination_url TEXT,

    status          TEXT NOT NULL CHECK (status IN ('ACTIVE', 'PAUSED', 'ARCHIVED', 'PENDING_ANALYSIS')),

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER update_ads_updated_at
    BEFORE UPDATE
    ON ads
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_ads_updated_at ON ads (updated_at);
CREATE INDEX idx_ads_campaign_status ON ads (ad_set_id, status);

CREATE TABLE ad_targeting_country
(
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_id            INT REFERENCES ads (id) ON DELETE CASCADE,
    country_iso_code CHAR(2) NOT NULL,
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_target_country_ad_id ON ad_targeting_country (ad_id);
CREATE INDEX idx_target_country_updated ON ad_targeting_country (updated_at);

CREATE TRIGGER update_ad_targeting_country_updated_at
    BEFORE UPDATE
    ON ad_targeting_country
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE ad_targeting_keyword
(
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_id           INT REFERENCES ads (id) ON DELETE CASCADE,
    keyword         TEXT NOT NULL,
    relevance_score DECIMAL(3, 2) DEFAULT 1.0 CHECK (relevance_score BETWEEN 0 AND 1),
    updated_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX idx_target_keyword_ad_id ON ad_targeting_keyword (ad_id);
CREATE INDEX idx_target_kw_updated ON ad_targeting_keyword (updated_at);

CREATE TRIGGER update_ad_targeting_keyword_updated_at
    BEFORE UPDATE
    ON ad_targeting_keyword
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE ad_targeting_entity
(
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_id           INT REFERENCES ads (id) ON DELETE CASCADE,
    entity_id       TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    updated_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX idx_target_entity_ad_id ON ad_targeting_entity (ad_id);
CREATE INDEX idx_target_entity_updated ON ad_targeting_entity (updated_at);


CREATE TRIGGER update_ad_targeting_entity_updated_at
    BEFORE UPDATE
    ON ad_targeting_entity
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE iab_topics
(
    id        INT PRIMARY KEY,
    name      TEXT NOT NULL,
    parent_id INT REFERENCES iab_topics (id),
    tier      INT  NOT NULL,
    type      TEXT CHECK (type IN ('CONTENT', 'PRODUCT'))
);

CREATE TABLE iab_topic_mapping
(
    content_topic_id INT REFERENCES iab_topics (id),
    product_topic_id INT REFERENCES iab_topics (id),
    PRIMARY KEY (content_topic_id, product_topic_id)
);

CREATE TABLE entities
(
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE ad_targeting_topic
(
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_id           INT REFERENCES ads (id) ON DELETE CASCADE,
    topic_id        INT REFERENCES iab_topics (id) NOT NULL,
    relevance_score DECIMAL(3, 2) DEFAULT 1.0 CHECK (relevance_score BETWEEN 0 AND 1),
    updated_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX idx_target_topic_ad_id ON ad_targeting_topic (ad_id);
CREATE INDEX idx_target_topic_updated ON ad_targeting_topic (updated_at);
CREATE TRIGGER update_ad_targeting_topic_updated_at
    BEFORE UPDATE
    ON ad_targeting_topic
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE ad_targeting_keyword ADD CONSTRAINT unique_ad_keyword UNIQUE (ad_id, keyword);

ALTER TABLE ad_targeting_entity ADD CONSTRAINT unique_ad_entity UNIQUE (ad_id, entity_id, entity_type);

ALTER TABLE ad_targeting_topic ADD CONSTRAINT unique_ad_topic UNIQUE (ad_id, topic_id);

CREATE TABLE ad_targeting_device
(
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_id       INT REFERENCES ads (id) ON DELETE CASCADE,
    device_type TEXT NOT NULL CHECK (device_type IN ('mobile', 'desktop', 'tablet')),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_target_device_ad_id ON ad_targeting_device (ad_id);
CREATE INDEX idx_target_device_updated ON ad_targeting_device (updated_at);

CREATE TABLE publishers
(
    id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       TEXT NOT NULL,
    domain     TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_publishers_domain ON publishers (domain);

CREATE TRIGGER update_publishers_updated_at
    BEFORE UPDATE
    ON publishers
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE ad_embeddings
(
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_id      INT         NOT NULL REFERENCES ads (id) ON DELETE CASCADE UNIQUE,
    embedding  vector(384) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ad_embeddings_ad_id ON ad_embeddings (ad_id);
CREATE INDEX idx_ad_embeddings_vector ON ad_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TRIGGER update_ad_embeddings_updated_at
    BEFORE UPDATE
    ON ad_embeddings
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE page_embeddings
(
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_url_hash TEXT        NOT NULL UNIQUE,
    url           TEXT        NOT NULL,
    embedding     vector(384) NOT NULL,
    chunk_count   INT         DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_page_embeddings_page_url_hash ON page_embeddings (page_url_hash);
CREATE INDEX idx_page_embeddings_url ON page_embeddings (url);
CREATE INDEX idx_page_embeddings_vector ON page_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TRIGGER update_page_embeddings_updated_at
    BEFORE UPDATE
    ON page_embeddings
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE page_chunk_embeddings
(
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_url_hash TEXT        NOT NULL,
    chunk_index   INT         NOT NULL,
    content       TEXT,
    embedding     vector(384) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_page_chunk_page_url_hash FOREIGN KEY (page_url_hash)
        REFERENCES page_embeddings (page_url_hash) ON DELETE CASCADE,
    CONSTRAINT unique_page_chunk UNIQUE (page_url_hash, chunk_index)
);

CREATE INDEX idx_page_chunk_page_url_hash ON page_chunk_embeddings (page_url_hash);
CREATE INDEX idx_page_chunk_vector ON page_chunk_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE page_contexts
(
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_url_hash TEXT        NOT NULL UNIQUE,
    url           TEXT        NOT NULL,
    title         TEXT,
    description   TEXT,
    publisher_id  INT REFERENCES publishers (id) ON DELETE SET NULL,
    crawled       BOOLEAN     DEFAULT FALSE,
    processed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_page_contexts_page_url_hash ON page_contexts (page_url_hash);
CREATE INDEX idx_page_contexts_publisher_id ON page_contexts (publisher_id);
CREATE INDEX idx_page_contexts_url ON page_contexts (url);

CREATE TRIGGER update_page_contexts_updated_at
    BEFORE UPDATE
    ON page_contexts
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE page_keywords
(
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_url_hash   TEXT           NOT NULL,
    keyword         TEXT           NOT NULL,
    relevance_score DECIMAL(5, 4)  DEFAULT 1.0,
    created_at      TIMESTAMPTZ    DEFAULT NOW(),

    CONSTRAINT fk_page_keywords_page FOREIGN KEY (page_url_hash)
        REFERENCES page_contexts (page_url_hash) ON DELETE CASCADE,
    CONSTRAINT unique_page_keyword UNIQUE (page_url_hash, keyword)
);

CREATE INDEX idx_page_keywords_page_url_hash ON page_keywords (page_url_hash);
CREATE INDEX idx_page_keywords_keyword ON page_keywords (keyword);

CREATE TABLE page_entities
(
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_url_hash TEXT        NOT NULL,
    entity_text   TEXT        NOT NULL,
    entity_type   TEXT        NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_page_entities_page FOREIGN KEY (page_url_hash)
        REFERENCES page_contexts (page_url_hash) ON DELETE CASCADE,
    CONSTRAINT unique_page_entity UNIQUE (page_url_hash, entity_text, entity_type)
);

CREATE INDEX idx_page_entities_page_url_hash ON page_entities (page_url_hash);
CREATE INDEX idx_page_entities_entity_text ON page_entities (entity_text);
CREATE INDEX idx_page_entities_entity_type ON page_entities (entity_type);

CREATE TABLE page_topics
(
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_url_hash   TEXT          NOT NULL,
    topic_id        INT           NOT NULL REFERENCES iab_topics (id),
    iab_id          TEXT          NOT NULL,
    name            TEXT,
    tier            INT,
    relevance_score DECIMAL(5, 4) DEFAULT 1.0,
    created_at      TIMESTAMPTZ   DEFAULT NOW(),

    CONSTRAINT fk_page_topics_page FOREIGN KEY (page_url_hash)
        REFERENCES page_contexts (page_url_hash) ON DELETE CASCADE,
    CONSTRAINT unique_page_topic UNIQUE (page_url_hash, topic_id)
);

CREATE INDEX idx_page_topics_page_url_hash ON page_topics (page_url_hash);
CREATE INDEX idx_page_topics_topic_id ON page_topics (topic_id);
