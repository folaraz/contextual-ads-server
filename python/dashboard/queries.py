"""
SQL Queries for the Business Metrics Dashboard.

Strategy:
  - Aggregate tables/charts use the hourly materialized views
    (campaign_metrics_hourly, ad_metrics_hourly, auction_metrics_hourly)
    for fast pre-computed results.
  - Time-series charts use raw tables with SQL-level bucketing
    (via the %(bucket_secs)s parameter) so result sets stay at ~200-500 rows
    instead of returning every raw event row.
  - KPI summary cards use raw tables for exact time-range accuracy.
  - Pacing queries use raw tables (no materialized view) with LIMIT guards.

Enrichment joins use LEFT JOIN + COALESCE so the dashboard never breaks
when main-schema rows are absent — it falls back to raw numeric IDs.
"""

# =============================================================================
# Overview / Business KPIs
# =============================================================================

# ---------------------------------------------------------------------------
# KPI summary — exact range from raw tables (single-row result, partition-pruned)
# ---------------------------------------------------------------------------
KPI_SUMMARY = """
    SELECT
        COALESCE(imp.total_impressions, 0)  AS total_impressions,
        COALESCE(imp.total_spend_cents, 0)  AS total_spend_cents,
        COALESCE(clk.total_clicks, 0)       AS total_clicks,
        CASE WHEN COALESCE(imp.total_impressions, 0) > 0
             THEN (COALESCE(clk.total_clicks, 0)::DECIMAL / imp.total_impressions) * 100
             ELSE 0 END                     AS ctr_pct,
        COALESCE(auc.total_auctions, 0)     AS total_auctions,
        COALESCE(auc.auctions_filled, 0)    AS auctions_filled,
        CASE WHEN COALESCE(auc.total_auctions, 0) > 0
             THEN (COALESCE(auc.auctions_filled, 0)::DECIMAL / auc.total_auctions) * 100
             ELSE 0 END                     AS fill_rate_pct
    FROM
        (SELECT COUNT(*) AS total_impressions,
                SUM(price_cents) AS total_spend_cents
         FROM ads_analytics.ad_impression_events
         WHERE event_time >= %(start)s AND event_time < %(end)s) imp,
        (SELECT COUNT(*) AS total_clicks
         FROM ads_analytics.ad_click_events
         WHERE event_time >= %(start)s AND event_time < %(end)s) clk,
        (SELECT COUNT(*) AS total_auctions,
                COUNT(winner_ad_id) AS auctions_filled
         FROM ads_analytics.auction_events
         WHERE event_time >= %(start)s AND event_time < %(end)s) auc
"""

# Active campaigns - fast distinct count from materialized view
ACTIVE_CAMPAIGNS_COUNT = """
    SELECT COUNT(DISTINCT campaign_id) AS active_campaigns
    FROM ads_analytics.campaign_metrics_hourly
    WHERE hour >= date_trunc('hour', %(start)s::timestamptz)
      AND hour <= date_trunc('hour', %(end)s::timestamptz)
"""

# ---------------------------------------------------------------------------
# Spend over time — SQL-bucketed from raw impressions table for exact spend numbers
# ---------------------------------------------------------------------------
SPEND_OVER_TIME = """
    SELECT
        to_timestamp(
            floor(extract(epoch from event_time) / %(bucket_secs)s) * %(bucket_secs)s
        ) AS bucket,
        SUM(price_cents) AS spend_cents,
        COUNT(*)          AS impressions
    FROM ads_analytics.ad_impression_events
    WHERE event_time >= %(start)s AND event_time < %(end)s
    GROUP BY 1
    ORDER BY 1
"""

# ---------------------------------------------------------------------------
# Impressions + Clicks rate over time — SQL-bucketed
# ---------------------------------------------------------------------------
IMPRESSIONS_OVER_TIME = """
    SELECT
        to_timestamp(
            floor(extract(epoch from event_time) / %(bucket_secs)s) * %(bucket_secs)s
        ) AS bucket,
        COUNT(*) AS impressions
    FROM ads_analytics.ad_impression_events
    WHERE event_time >= %(start)s AND event_time < %(end)s
    GROUP BY 1
    ORDER BY 1
"""

CLICKS_OVER_TIME = """
    SELECT
        to_timestamp(
            floor(extract(epoch from event_time) / %(bucket_secs)s) * %(bucket_secs)s
        ) AS bucket,
        COUNT(*) AS clicks
    FROM ads_analytics.ad_click_events
    WHERE event_time >= %(start)s AND event_time < %(end)s
    GROUP BY 1
    ORDER BY 1
"""

# ---------------------------------------------------------------------------
# Spend by advertiser — materialized view + enrichment
# ---------------------------------------------------------------------------
SPEND_BY_ADVERTISER = """
    SELECT
        COALESCE(adv.name, 'Advertiser #' || c.advertiser_id::TEXT) AS advertiser_name,
        c.advertiser_id,
        SUM(m.spend_cents) AS spend_cents,
        SUM(m.impressions) AS impressions
    FROM ads_analytics.campaign_metrics_hourly m
    LEFT JOIN public.campaigns c ON m.campaign_id = c.id
    LEFT JOIN public.advertisers adv ON c.advertiser_id = adv.id
    WHERE m.hour >= date_trunc('hour', %(start)s::timestamptz)
      AND m.hour <= date_trunc('hour', %(end)s::timestamptz)
    GROUP BY adv.name, c.advertiser_id
    ORDER BY spend_cents DESC
    LIMIT 20
"""

# ---------------------------------------------------------------------------
# Spend by pricing model — materialized view + enrichment
# ---------------------------------------------------------------------------
SPEND_BY_PRICING_MODEL = """
    SELECT
        COALESCE(aset.pricing_model, 'Unknown') AS pricing_model,
        SUM(m.spend_cents) AS spend_cents,
        SUM(m.impressions) AS impressions
    FROM ads_analytics.ad_metrics_hourly m
    LEFT JOIN public.ads a ON m.ad_id = a.id
    LEFT JOIN public.ad_sets aset ON a.ad_set_id = aset.id
    WHERE m.hour >= date_trunc('hour', %(start)s::timestamptz)
      AND m.hour <= date_trunc('hour', %(end)s::timestamptz)
    GROUP BY aset.pricing_model
    ORDER BY spend_cents DESC
"""

# ---------------------------------------------------------------------------
# Fill rate over time — SQL-bucketed
# ---------------------------------------------------------------------------
FILL_RATE_OVER_TIME = """
    SELECT
        to_timestamp(
            floor(extract(epoch from event_time) / %(bucket_secs)s) * %(bucket_secs)s
        ) AS bucket,
        COUNT(*)            AS total_auctions,
        COUNT(winner_ad_id) AS filled_auctions,
        CASE WHEN COUNT(*) > 0
             THEN COUNT(winner_ad_id)::DECIMAL / COUNT(*) * 100
             ELSE 0 END    AS fill_rate_pct
    FROM ads_analytics.auction_events
    WHERE event_time >= %(start)s AND event_time < %(end)s
    GROUP BY 1
    ORDER BY 1
"""

# =============================================================================
# Pacing Deep Dive
# =============================================================================

# ---------------------------------------------------------------------------
# Top-N campaigns by impression count — materialized view + enrichment
# ---------------------------------------------------------------------------
TOP_CAMPAIGNS_BY_IMPRESSIONS = """
    SELECT
        m.campaign_id,
        COALESCE(c.name, 'Campaign #' || m.campaign_id::TEXT) AS campaign_name,
        COALESCE(adv.name, 'Advertiser #' || COALESCE(c.advertiser_id::TEXT, '?')) AS advertiser_name,
        SUM(m.impressions)  AS impressions,
        SUM(m.spend_cents)  AS spend_cents,
        c.total_budget      AS total_budget_cents,
        COALESCE(aset.daily_budget_cents, 0) AS daily_budget_cents,
        c.status            AS campaign_status
    FROM ads_analytics.campaign_metrics_hourly m
    LEFT JOIN public.campaigns c   ON m.campaign_id = c.id
    LEFT JOIN public.advertisers adv ON c.advertiser_id = adv.id
    LEFT JOIN public.ad_sets aset  ON aset.campaign_id = c.id
    WHERE m.hour >= date_trunc('hour', %(start)s::timestamptz)
      AND m.hour <= date_trunc('hour', %(end)s::timestamptz)
    GROUP BY m.campaign_id, c.name, adv.name, c.advertiser_id,
             c.total_budget, c.status, aset.daily_budget_cents
    ORDER BY impressions DESC
    LIMIT %(limit)s
"""

# ---------------------------------------------------------------------------
# Pacing multiplier time-series — raw table with LIMIT guard
# ---------------------------------------------------------------------------
PACING_MULTIPLIER_TIMESERIES = """
    SELECT
        ph.event_time,
        ph.campaign_id,
        COALESCE(c.name, 'Campaign #' || ph.campaign_id::TEXT) AS campaign_name,
        ph.previous_multiplier,
        ph.new_multiplier,
        ph.error_normalized,
        ph.p_term,
        ph.i_term,
        ph.urgency,
        ph.adjustment,
        ph.spent_today_cents,
        ph.daily_budget_cents,
        ph.remaining_budget_cents,
        ph.total_budget_cents,
        ph.status
    FROM ads_analytics.pacing_history ph
    LEFT JOIN public.campaigns c ON ph.campaign_id = c.id
    WHERE ph.event_time >= %(start)s AND ph.event_time < %(end)s
      AND ph.campaign_id = ANY(%(campaign_ids)s)
    ORDER BY ph.event_time
    LIMIT 10000
"""

# ---------------------------------------------------------------------------
# Pacing summary stats per campaign
# ---------------------------------------------------------------------------
PACING_SUMMARY = """
    WITH latest AS (
        SELECT DISTINCT ON (campaign_id)
            campaign_id,
            new_multiplier,
            status,
            spent_today_cents,
            daily_budget_cents,
            remaining_budget_cents,
            total_budget_cents
        FROM ads_analytics.pacing_history
        WHERE event_time >= %(start)s AND event_time < %(end)s
        ORDER BY campaign_id, event_time DESC
    )
    SELECT
        ph.campaign_id,
        COALESCE(c.name, 'Campaign #' || ph.campaign_id::TEXT) AS campaign_name,
        COALESCE(adv.name, 'Advertiser #' || COALESCE(c.advertiser_id::TEXT, '?')) AS advertiser_name,
        COUNT(*) AS pacing_updates,
        AVG(ph.new_multiplier) AS avg_multiplier,
        MIN(ph.new_multiplier) AS min_multiplier,
        MAX(ph.new_multiplier) AS max_multiplier,
        STDDEV(ph.new_multiplier) AS multiplier_stddev,
        MAX(ph.new_multiplier) - MIN(ph.new_multiplier) AS multiplier_range,
        l.new_multiplier AS latest_multiplier,
        l.status AS latest_status,
        l.spent_today_cents AS latest_spent_today_cents,
        l.daily_budget_cents AS latest_daily_budget_cents,
        l.remaining_budget_cents AS latest_remaining_budget_cents,
        l.total_budget_cents AS latest_total_budget_cents,
        COALESCE(c.total_budget, 0) - COALESCE(l.remaining_budget_cents, 0) AS total_spend_cents
    FROM ads_analytics.pacing_history ph
    LEFT JOIN public.campaigns c ON ph.campaign_id = c.id
    LEFT JOIN public.advertisers adv ON c.advertiser_id = adv.id
    LEFT JOIN latest l ON l.campaign_id = ph.campaign_id
    WHERE ph.event_time >= %(start)s AND ph.event_time < %(end)s
    GROUP BY ph.campaign_id, c.name, adv.name, c.advertiser_id,
             l.new_multiplier, l.status, l.spent_today_cents,
             l.daily_budget_cents, l.remaining_budget_cents,
             l.total_budget_cents, c.total_budget
    ORDER BY pacing_updates DESC
    LIMIT %(limit)s
"""

# ---------------------------------------------------------------------------
# Campaigns currently in budget_exhausted status
# ---------------------------------------------------------------------------
BUDGET_EXHAUSTED_CAMPAIGNS = """
    SELECT DISTINCT ON (ph.campaign_id)
        ph.campaign_id,
        COALESCE(c.name, 'Campaign #' || ph.campaign_id::TEXT) AS campaign_name,
        COALESCE(adv.name, 'Advertiser #' || COALESCE(c.advertiser_id::TEXT, '?')) AS advertiser_name,
        ph.event_time AS exhausted_at,
        COALESCE(NULLIF(ph.total_budget_cents, 0), c.total_budget, 0) AS total_budget_cents,
        ph.remaining_budget_cents,
        ph.spent_today_cents,
        ph.daily_budget_cents
    FROM ads_analytics.pacing_history ph
    LEFT JOIN public.campaigns c ON ph.campaign_id = c.id
    LEFT JOIN public.advertisers adv ON c.advertiser_id = adv.id
    WHERE ph.status = 'budget_exhausted'
      AND ph.event_time >= %(start)s AND ph.event_time < %(end)s
    ORDER BY ph.campaign_id, ph.event_time DESC
"""

# =============================================================================
# Ad & Campaign Performance
# =============================================================================

# ---------------------------------------------------------------------------
# Campaign performance table — materialized view + enrichment
# ---------------------------------------------------------------------------
CAMPAIGN_PERFORMANCE = """
    SELECT
        m.campaign_id,
        COALESCE(c.name, 'Campaign #' || m.campaign_id::TEXT) AS campaign_name,
        COALESCE(adv.name, 'Advertiser #' || COALESCE(c.advertiser_id::TEXT, '?')) AS advertiser_name,
        SUM(m.impressions) AS impressions,
        SUM(m.clicks)      AS clicks,
        SUM(m.spend_cents) AS spend_cents,
        CASE WHEN SUM(m.impressions) > 0
             THEN (SUM(m.clicks)::DECIMAL / SUM(m.impressions)) * 100
             ELSE 0 END AS ctr_pct,
        CASE WHEN SUM(m.impressions) > 0
             THEN (SUM(m.spend_cents)::DECIMAL / SUM(m.impressions)) * 1000 / 100
             ELSE 0 END AS ecpm_dollars,
        c.total_budget AS total_budget_cents,
        COALESCE(aset.daily_budget_cents, 0) AS daily_budget_cents,
        c.status AS campaign_status
    FROM ads_analytics.campaign_metrics_hourly m
    LEFT JOIN public.campaigns c    ON m.campaign_id = c.id
    LEFT JOIN public.advertisers adv ON c.advertiser_id = adv.id
    LEFT JOIN public.ad_sets aset   ON aset.campaign_id = c.id
    WHERE m.hour >= date_trunc('hour', %(start)s::timestamptz)
      AND m.hour <= date_trunc('hour', %(end)s::timestamptz)
    GROUP BY m.campaign_id, c.name, adv.name, c.advertiser_id,
             c.total_budget, c.status, aset.daily_budget_cents
    ORDER BY spend_cents DESC
"""

# ---------------------------------------------------------------------------
# Batch ad performance for multiple campaigns — materialized view (N+1 fix)
# ---------------------------------------------------------------------------
ADS_IN_CAMPAIGNS = """
    SELECT
        m.campaign_id,
        m.ad_id,
        COALESCE(a.headline, 'Ad #' || m.ad_id::TEXT) AS headline,
        COALESCE(a.destination_url, '') AS destination_url,
        COALESCE(aset.pricing_model, 'Unknown') AS pricing_model,
        COALESCE(aset.bid_amount_cents, 0) AS bid_amount_cents,
        SUM(m.impressions) AS impressions,
        SUM(m.clicks)      AS clicks,
        SUM(m.spend_cents) AS spend_cents,
        CASE WHEN SUM(m.impressions) > 0
             THEN (SUM(m.clicks)::DECIMAL / SUM(m.impressions)) * 100
             ELSE 0 END AS ctr_pct
    FROM ads_analytics.ad_metrics_hourly m
    LEFT JOIN public.ads a         ON m.ad_id = a.id
    LEFT JOIN public.ad_sets aset  ON a.ad_set_id = aset.id
    WHERE m.campaign_id = ANY(%(campaign_ids)s)
      AND m.hour >= date_trunc('hour', %(start)s::timestamptz)
      AND m.hour <= date_trunc('hour', %(end)s::timestamptz)
    GROUP BY m.campaign_id, m.ad_id, a.headline, a.destination_url,
             aset.pricing_model, aset.bid_amount_cents
    ORDER BY m.campaign_id, spend_cents DESC
"""

# ---------------------------------------------------------------------------
# Top winning ads from auctions (enriched)
# ---------------------------------------------------------------------------
TOP_WINNING_ADS = """
    SELECT
        ae.winner_ad_id AS ad_id,
        COALESCE(a.headline, 'Ad #' || ae.winner_ad_id::TEXT) AS headline,
        COALESCE(a.destination_url, '') AS destination_url,
        ae.winner_campaign_id AS campaign_id,
        COALESCE(c.name, 'Campaign #' || ae.winner_campaign_id::TEXT) AS campaign_name,
        COUNT(*) AS auction_wins,
        AVG(ae.winning_bid_cents) AS avg_winning_bid_cents,
        AVG(ae.winning_final_score) AS avg_final_score
    FROM ads_analytics.auction_events ae
    LEFT JOIN public.ads a ON ae.winner_ad_id = a.id
    LEFT JOIN public.campaigns c ON ae.winner_campaign_id = c.id
    WHERE ae.winner_ad_id IS NOT NULL
      AND ae.event_time >= %(start)s AND ae.event_time < %(end)s
    GROUP BY ae.winner_ad_id, a.headline, a.destination_url,
             ae.winner_campaign_id, c.name
    ORDER BY auction_wins DESC
    LIMIT %(limit)s
"""

# ---------------------------------------------------------------------------
# Campaign spend burn-down (from pacing_history, with LIMIT guard)
# ---------------------------------------------------------------------------
CAMPAIGN_SPEND_BURNDOWN = """
    SELECT
        ph.event_time,
        ph.campaign_id,
        COALESCE(c.name, 'Campaign #' || ph.campaign_id::TEXT) AS campaign_name,
        ph.remaining_budget_cents,
        ph.total_budget_cents,
        ph.spent_today_cents,
        ph.daily_budget_cents
    FROM ads_analytics.pacing_history ph
    LEFT JOIN public.campaigns c ON ph.campaign_id = c.id
    WHERE ph.campaign_id = ANY(%(campaign_ids)s)
      AND ph.event_time >= %(start)s AND ph.event_time < %(end)s
    ORDER BY ph.event_time
    LIMIT 5000
"""

REFRESH_MATERIALIZED_VIEWS = """
    SELECT ads_analytics.refresh_materialized_views();
"""

