DROP MATERIALIZED VIEW IF EXISTS ads_analytics.auction_metrics_hourly;
DROP MATERIALIZED VIEW IF EXISTS ads_analytics.campaign_metrics_hourly;
DROP MATERIALIZED VIEW IF EXISTS ads_analytics.ad_metrics_hourly;

DROP FUNCTION IF EXISTS ads_analytics.refresh_materialized_views();
DROP FUNCTION IF EXISTS ads_analytics.drop_old_partitions(INT);
DROP FUNCTION IF EXISTS ads_analytics.create_future_partitions(INT);

DROP TABLE IF EXISTS ads_analytics.pacing_history;
DROP TABLE IF EXISTS ads_analytics.auction_events;
DROP TABLE IF EXISTS ads_analytics.ad_click_events;
DROP TABLE IF EXISTS ads_analytics.ad_impression_events;

DROP SCHEMA IF EXISTS ads_analytics CASCADE;
