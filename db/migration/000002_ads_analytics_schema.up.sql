CREATE SCHEMA IF NOT EXISTS ads_analytics;

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE TABLE IF NOT EXISTS ads_analytics.ad_impression_events (
    id              BIGSERIAL,
    event_time      TIMESTAMPTZ NOT NULL,
    ad_id           INT NOT NULL,
    campaign_id     INT NOT NULL,
    auction_id      VARCHAR(64),
    publisher_id    VARCHAR(64),
    page_url        TEXT,
    price_cents     BIGINT DEFAULT 0,
    device_type     VARCHAR(32),
    user_agent      TEXT,
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (event_time, id)
) PARTITION BY RANGE (event_time);

CREATE INDEX IF NOT EXISTS idx_impression_ad_id ON ads_analytics.ad_impression_events (ad_id, event_time);
CREATE INDEX IF NOT EXISTS idx_impression_campaign_id ON ads_analytics.ad_impression_events (campaign_id, event_time);
CREATE INDEX IF NOT EXISTS idx_impression_publisher ON ads_analytics.ad_impression_events (publisher_id, event_time);


CREATE TABLE IF NOT EXISTS ads_analytics.ad_click_events (
    id              BIGSERIAL,
    event_time      TIMESTAMPTZ NOT NULL,
    ad_id           INT NOT NULL,
    campaign_id     INT NOT NULL,
    auction_id      VARCHAR(64),
    publisher_id    VARCHAR(64),
    page_url        TEXT,
    click_url       TEXT,
    price_cents     BIGINT DEFAULT 0,
    device_type     VARCHAR(32),
    user_agent      TEXT,
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (event_time, id)
) PARTITION BY RANGE (event_time);

CREATE INDEX IF NOT EXISTS idx_click_ad_id ON ads_analytics.ad_click_events (ad_id, event_time);
CREATE INDEX IF NOT EXISTS idx_click_campaign_id ON ads_analytics.ad_click_events (campaign_id, event_time);
CREATE INDEX IF NOT EXISTS idx_click_publisher ON ads_analytics.ad_click_events (publisher_id, event_time);

CREATE TABLE IF NOT EXISTS ads_analytics.auction_events (
    id                      BIGSERIAL,
    event_time              TIMESTAMPTZ NOT NULL,
    auction_id              VARCHAR(64) NOT NULL,
    publisher_id            VARCHAR(64),
    page_url                TEXT,

    num_candidates          INT DEFAULT 0,
    num_filtered_budget     INT DEFAULT 0,
    num_filtered_targeting  INT DEFAULT 0,
    num_eligible            INT DEFAULT 0,

    winner_ad_id            INT,
    winner_campaign_id      INT,
    winning_bid_cents       BIGINT,
    winning_effective_bid   DECIMAL(12, 6),
    winning_final_score     DECIMAL(12, 6),

    device_type             VARCHAR(32),
    user_agent              TEXT,
    ip_address              INET,

    created_at              TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (event_time, id)
) PARTITION BY RANGE (event_time);

CREATE INDEX IF NOT EXISTS idx_auction_id ON ads_analytics.auction_events (auction_id);
CREATE INDEX IF NOT EXISTS idx_auction_winner_ad ON ads_analytics.auction_events (winner_ad_id, event_time);
CREATE INDEX IF NOT EXISTS idx_auction_winner_campaign ON ads_analytics.auction_events (winner_campaign_id, event_time);
CREATE INDEX IF NOT EXISTS idx_auction_publisher ON ads_analytics.auction_events (publisher_id, event_time);

CREATE TABLE IF NOT EXISTS ads_analytics.pacing_history (
    id                      BIGSERIAL,
    event_time              TIMESTAMPTZ NOT NULL,
    campaign_id             INT NOT NULL,

    total_budget_cents      BIGINT,
    daily_budget_cents      BIGINT,
    remaining_budget_cents  BIGINT,
    spent_today_cents       BIGINT,
    effective_target_cents  BIGINT,

    remaining_days          INT,
    campaign_time_factor    DECIMAL(8, 6),
    daily_time_factor       DECIMAL(8, 6),

    kp                      DECIMAL(8, 6),
    ki                      DECIMAL(8, 6),
    min_multiplier          DECIMAL(8, 6),
    max_multiplier          DECIMAL(8, 6),

    error_normalized        DECIMAL(12, 6),
    p_term                  DECIMAL(12, 6),
    i_term                  DECIMAL(12, 6),
    urgency                 DECIMAL(12, 6),
    adjustment              DECIMAL(12, 6),
    cumulative_error        DECIMAL(12, 6),

    previous_multiplier     DECIMAL(8, 6),
    new_multiplier          DECIMAL(8, 6),
    status                  VARCHAR(32),

    created_at              TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (event_time, id)
) PARTITION BY RANGE (event_time);

CREATE INDEX IF NOT EXISTS idx_pacing_campaign ON ads_analytics.pacing_history (campaign_id, event_time);
CREATE INDEX IF NOT EXISTS idx_pacing_status ON ads_analytics.pacing_history (status, event_time);

CREATE MATERIALIZED VIEW IF NOT EXISTS ads_analytics.ad_metrics_hourly AS
SELECT
    date_trunc('hour', i.event_time) AS hour,
    i.ad_id,
    i.campaign_id,
    COUNT(DISTINCT i.id) AS impressions,
    COALESCE(c.clicks, 0) AS clicks,
    SUM(i.price_cents) AS spend_cents,
    CASE
        WHEN COUNT(DISTINCT i.id) > 0
        THEN (SUM(i.price_cents)::DECIMAL / COUNT(DISTINCT i.id)) * 1000 / 100
        ELSE 0
    END AS avg_ecpm,
    CASE
        WHEN COUNT(DISTINCT i.id) > 0
        THEN (COALESCE(c.clicks, 0)::DECIMAL / COUNT(DISTINCT i.id)) * 100
        ELSE 0
    END AS avg_ctr
FROM ads_analytics.ad_impression_events i
LEFT JOIN (
    SELECT
        date_trunc('hour', event_time) AS hour,
        ad_id,
        COUNT(*) AS clicks
    FROM ads_analytics.ad_click_events
    GROUP BY date_trunc('hour', event_time), ad_id
) c ON date_trunc('hour', i.event_time) = c.hour AND i.ad_id = c.ad_id
GROUP BY date_trunc('hour', i.event_time), i.ad_id, i.campaign_id, c.clicks;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_metrics_hourly_unique
ON ads_analytics.ad_metrics_hourly (hour, ad_id);

CREATE INDEX IF NOT EXISTS idx_ad_metrics_hourly_campaign
ON ads_analytics.ad_metrics_hourly (campaign_id, hour);


CREATE MATERIALIZED VIEW IF NOT EXISTS ads_analytics.campaign_metrics_hourly AS
SELECT
    date_trunc('hour', i.event_time) AS hour,
    i.campaign_id,
    COUNT(DISTINCT i.id) AS impressions,
    COALESCE(c.clicks, 0) AS clicks,
    SUM(i.price_cents) AS spend_cents,
    CASE
        WHEN COUNT(DISTINCT i.id) > 0
        THEN (SUM(i.price_cents)::DECIMAL / COUNT(DISTINCT i.id)) * 1000 / 100
        ELSE 0
    END AS avg_ecpm,
    CASE
        WHEN COUNT(DISTINCT i.id) > 0
        THEN (COALESCE(c.clicks, 0)::DECIMAL / COUNT(DISTINCT i.id)) * 100
        ELSE 0
    END AS avg_ctr
FROM ads_analytics.ad_impression_events i
LEFT JOIN (
    SELECT
        date_trunc('hour', event_time) AS hour,
        campaign_id,
        COUNT(*) AS clicks
    FROM ads_analytics.ad_click_events
    GROUP BY date_trunc('hour', event_time), campaign_id
) c ON date_trunc('hour', i.event_time) = c.hour AND i.campaign_id = c.campaign_id
GROUP BY date_trunc('hour', i.event_time), i.campaign_id, c.clicks;

CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_metrics_hourly_unique
ON ads_analytics.campaign_metrics_hourly (hour, campaign_id);


CREATE MATERIALIZED VIEW IF NOT EXISTS ads_analytics.auction_metrics_hourly AS
SELECT
    date_trunc('hour', event_time) AS hour,
    COUNT(*) AS total_auctions,
    COUNT(winner_ad_id) AS auctions_with_winner,
    AVG(num_candidates) AS avg_candidates,
    AVG(num_filtered_budget) AS avg_filtered_budget,
    AVG(num_filtered_targeting) AS avg_filtered_targeting,
    AVG(num_eligible) AS avg_eligible,
    AVG(winning_bid_cents) FILTER (WHERE winner_ad_id IS NOT NULL) AS avg_winning_bid_cents,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY winning_bid_cents)
        FILTER (WHERE winner_ad_id IS NOT NULL) AS median_winning_bid_cents,
    CASE
        WHEN COUNT(*) > 0
        THEN (COUNT(winner_ad_id)::DECIMAL / COUNT(*)) * 100
        ELSE 0
    END AS fill_rate_pct
FROM ads_analytics.auction_events
GROUP BY date_trunc('hour', event_time);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auction_metrics_hourly_unique
ON ads_analytics.auction_metrics_hourly (hour);


CREATE OR REPLACE FUNCTION ads_analytics.refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY ads_analytics.ad_metrics_hourly;
    REFRESH MATERIALIZED VIEW CONCURRENTLY ads_analytics.campaign_metrics_hourly;
    REFRESH MATERIALIZED VIEW CONCURRENTLY ads_analytics.auction_metrics_hourly;
    RAISE NOTICE 'Materialized views refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql;


DO $$
    DECLARE
        start_date DATE := CURRENT_DATE - INTERVAL '30 days';
        end_date DATE := CURRENT_DATE + INTERVAL '30 days';
        partition_date DATE;
        partition_name TEXT;
    BEGIN
        partition_date := start_date;
        WHILE partition_date < end_date LOOP
                partition_name := 'ad_impression_events_' || TO_CHAR(partition_date, 'YYYY_MM_DD');

                BEGIN
                    EXECUTE format(
                            'CREATE TABLE IF NOT EXISTS ads_analytics.%I PARTITION OF ads_analytics.ad_impression_events
                            FOR VALUES FROM (%L) TO (%L)',
                            partition_name,
                            partition_date,
                            partition_date + INTERVAL '1 day'
                            );
                    RAISE NOTICE 'Created partition: %', partition_name;
                EXCEPTION WHEN duplicate_table THEN
                    NULL;
                END;

                partition_date := partition_date + INTERVAL '1 day';
            END LOOP;
    END $$;

DO $$
    DECLARE
        start_date DATE := CURRENT_DATE - INTERVAL '30 days';
        end_date DATE := CURRENT_DATE + INTERVAL '30 days';
        partition_date DATE;
        partition_name TEXT;
    BEGIN
        partition_date := start_date;
        WHILE partition_date < end_date LOOP
                partition_name := 'ad_click_events_' || TO_CHAR(partition_date, 'YYYY_MM_DD');

                BEGIN
                    EXECUTE format(
                            'CREATE TABLE IF NOT EXISTS ads_analytics.%I PARTITION OF ads_analytics.ad_click_events
                            FOR VALUES FROM (%L) TO (%L)',
                            partition_name,
                            partition_date,
                            partition_date + INTERVAL '1 day'
                            );
                    RAISE NOTICE 'Created partition: %', partition_name;
                EXCEPTION WHEN duplicate_table THEN
                    NULL;
                END;

                partition_date := partition_date + INTERVAL '1 day';
            END LOOP;
    END $$;

DO $$
    DECLARE
        start_date DATE := CURRENT_DATE - INTERVAL '30 days';
        end_date DATE := CURRENT_DATE + INTERVAL '30 days';
        partition_date DATE;
        partition_name TEXT;
    BEGIN
        partition_date := start_date;
        WHILE partition_date < end_date LOOP
                partition_name := 'auction_events_' || TO_CHAR(partition_date, 'YYYY_MM_DD');

                BEGIN
                    EXECUTE format(
                            'CREATE TABLE IF NOT EXISTS ads_analytics.%I PARTITION OF ads_analytics.auction_events
                            FOR VALUES FROM (%L) TO (%L)',
                            partition_name,
                            partition_date,
                            partition_date + INTERVAL '1 day'
                            );
                    RAISE NOTICE 'Created partition: %', partition_name;
                EXCEPTION WHEN duplicate_table THEN
                    NULL;
                END;

                partition_date := partition_date + INTERVAL '1 day';
            END LOOP;
    END $$;

DO $$
    DECLARE
        start_date DATE := CURRENT_DATE - INTERVAL '30 days';
        end_date DATE := CURRENT_DATE + INTERVAL '30 days';
        partition_date DATE;
        partition_name TEXT;
    BEGIN
        partition_date := start_date;
        WHILE partition_date < end_date LOOP
                partition_name := 'pacing_history_' || TO_CHAR(partition_date, 'YYYY_MM_DD');

                BEGIN
                    EXECUTE format(
                            'CREATE TABLE IF NOT EXISTS ads_analytics.%I PARTITION OF ads_analytics.pacing_history
                            FOR VALUES FROM (%L) TO (%L)',
                            partition_name,
                            partition_date,
                            partition_date + INTERVAL '1 day'
                            );
                    RAISE NOTICE 'Created partition: %', partition_name;
                EXCEPTION WHEN duplicate_table THEN
                    NULL;
                END;

                partition_date := partition_date + INTERVAL '1 day';
            END LOOP;
    END $$;

SELECT 'Partitions created successfully for past 30 days and future 30 days' as status;
