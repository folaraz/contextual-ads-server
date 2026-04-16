"""
Business Metrics Dashboard — Streamlit application.

Launch:
    cd python && streamlit run dashboard/app.py
    # or from project root:
    make dashboard

Tabs:
    1. Overview – KPI cards, spend/impression/click trends, advertiser & pricing breakdowns
    2. Pacing – Top-N campaign pacing multiplier overlay, per-campaign deep dive
    3. Ad Performance – Campaign & ad-level tables, spend burn-down, top auction winners
"""

import json
import os
import sys
import time as _time
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.db import DashboardDB
from dashboard import queries as Q


st.set_page_config(
    page_title="Contextual Ads, Business Metrics",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_db() -> DashboardDB:
    return DashboardDB()


DB = get_db()

_MV_REFRESH_EVERY_N = 4

if "mv_cycle" not in st.session_state:
    st.session_state["mv_cycle"] = 0
st.session_state["mv_cycle"] += 1

if st.session_state["mv_cycle"] % _MV_REFRESH_EVERY_N == 1:
    try:
        DB.refresh_materialized_views()
    except Exception as e:
        st.sidebar.warning(f" Could not refresh views: {e}")


st.sidebar.title("Dashboard Controls")

TIME_RANGES = {
    "Last 5 min": timedelta(minutes=5),
    "Last 15 min": timedelta(minutes=15),
    "Last 1 hour": timedelta(hours=1),
    "Last 6 hours": timedelta(hours=6),
    "Last 24 hours": timedelta(hours=24),
    "All time": timedelta(days=3650),
    "Custom range": None,
}
selected_range = st.sidebar.selectbox("Time range", list(TIME_RANGES.keys()), index=2)
now_utc = datetime.now(timezone.utc)

if selected_range == "Custom range":
    default_start = (now_utc - timedelta(days=1)).date()
    default_end = now_utc.date()
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        start_date = st.date_input("Start date", value=default_start, key="custom_start_date")
    with col_d2:
        end_date = st.date_input("End date", value=default_end, key="custom_end_date")
    col_t1, col_t2 = st.sidebar.columns(2)
    with col_t1:
        start_time_input = st.time_input("Start time", value=datetime.min.time(), key="custom_start_time")
    with col_t2:
        end_time_input = st.time_input("End time", value=now_utc.time().replace(microsecond=0), key="custom_end_time")
    start_time = datetime.combine(start_date, start_time_input, tzinfo=timezone.utc)
    end_time = datetime.combine(end_date, end_time_input, tzinfo=timezone.utc)
    if start_time >= end_time:
        st.sidebar.error("Start must be before end.")
        st.stop()
else:
    time_delta = TIME_RANGES[selected_range]
    start_time = now_utc - time_delta
    end_time = now_utc

auto_refresh = st.sidebar.toggle("Auto-refresh", value=True)
refresh_interval = st.sidebar.slider(
    "Refresh interval (seconds)", min_value=5, max_value=120, value=15, step=5,
    disabled=not auto_refresh,
)

if st.sidebar.button("Refresh"):
    st.cache_data.clear()


st.sidebar.markdown("---")
st.sidebar.caption(f"Last refreshed: {now_utc.strftime('%H:%M:%S UTC')}")


def cents_to_dollars(cents) -> float:
    """Convert cents (int) to dollars (float)."""
    try:
        return float(cents or 0) / 100.0
    except (TypeError, ValueError):
        return 0.0


def fmt_dollars(val) -> str:
    return f"${val:,.2f}"


def fmt_number(val) -> str:
    return f"{int(val):,}"


def compute_bucket_secs(start: datetime, end: datetime, target_points: int = 300) -> int:
    """Pick a nice time-bucket size aiming for ~target_points data points."""
    range_secs = max(1, int((end - start).total_seconds()))
    raw = max(1, range_secs // target_points)
    nice = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 14400, 86400]
    for n in nice:
        if n >= raw:
            return n
    return 86400


def bucket_label(secs: int) -> str:
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    return f"{secs // 3600}h"


def _serialize_params(params: dict) -> str:
    """Convert params dict to a JSON string suitable for st.cache_data keying."""
    out = {}
    for k, v in sorted(params.items()):
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, (list, tuple)):
            out[k] = list(v)
        else:
            out[k] = v
    return json.dumps(out, sort_keys=True)


@st.cache_data(ttl=15, show_spinner=False)
def cached_query(sql: str, params_json: str) -> pd.DataFrame:
    """Execute SQL with Streamlit data-caching (15 s TTL)."""
    raw = json.loads(params_json)
    restored: dict = {}
    for k, v in raw.items():
        if k in ("start", "end") and isinstance(v, str):
            restored[k] = datetime.fromisoformat(v)
        else:
            restored[k] = v
    return DB.query_df(sql, restored)


bucket_secs = compute_bucket_secs(start_time, end_time)
params = {"start": start_time, "end": end_time}
ts_params = {**params, "bucket_secs": bucket_secs}  # for time-series queries

_bucket_str = bucket_label(bucket_secs)

tab_overview, tab_pacing, tab_ads = st.tabs([
    "Overview",
    "Pacing Deep Dive",
    "Ad & Campaign Performance",
])

with tab_overview:
    st.header("Business Overview")

    # ----- KPI cards --------------------------------------------------------
    kpi_df = cached_query(Q.KPI_SUMMARY, _serialize_params(params))
    active_df = cached_query(Q.ACTIVE_CAMPAIGNS_COUNT, _serialize_params(params))

    if not kpi_df.empty:
        row = kpi_df.iloc[0]
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Total Spend", fmt_dollars(cents_to_dollars(row["total_spend_cents"])))
        k2.metric("Impressions", fmt_number(row["total_impressions"]))
        k3.metric("Clicks", fmt_number(row["total_clicks"]))
        k4.metric("CTR", f"{row['ctr_pct']:.2f}%")
        k5.metric("Fill Rate", f"{row['fill_rate_pct']:.1f}%")
        active_count = int(active_df.iloc[0]["active_campaigns"]) if not active_df.empty else 0
        k6.metric("Active Campaigns", fmt_number(active_count))
    else:
        st.info("No data for the selected time range.")

    st.markdown("---")

    # ----- Cumulative spend over time ----------------------------------------
    spend_df = cached_query(Q.SPEND_OVER_TIME, _serialize_params(ts_params))
    if not spend_df.empty:
        spend_df = spend_df.sort_values("bucket")
        spend_df["cumulative_dollars"] = spend_df["spend_cents"].astype(float).cumsum() / 100.0
        fig_spend = px.line(
            spend_df, x="bucket", y="cumulative_dollars",
            title="Cumulative Spend Over Time",
            labels={"bucket": "Time", "cumulative_dollars": "Spend ($)"},
        )
        fig_spend.update_layout(xaxis_title="Time", hovermode="x unified")
        st.plotly_chart(fig_spend, width="stretch")

    # ----- Impressions & Clicks over time ------------------------------------
    imp_df = cached_query(Q.IMPRESSIONS_OVER_TIME, _serialize_params(ts_params))
    clk_df = cached_query(Q.CLICKS_OVER_TIME, _serialize_params(ts_params))

    col_left, col_right = st.columns(2)

    with col_left:
        if not imp_df.empty:
            fig_imp = px.line(
                imp_df, x="bucket", y="impressions",
                title=f"Impressions per {_bucket_str} bucket",
                labels={"bucket": "Time", "impressions": "Impressions"},
            )
            fig_imp.update_layout(xaxis_title="Time", hovermode="x unified")
            st.plotly_chart(fig_imp, width="stretch")
        else:
            st.info("No impression data.")

    with col_right:
        if not clk_df.empty:
            fig_clk = px.line(
                clk_df, x="bucket", y="clicks",
                title=f"Clicks per {_bucket_str} bucket",
                labels={"bucket": "Time", "clicks": "Clicks"},
                color_discrete_sequence=["#EF553B"],
            )
            fig_clk.update_layout(xaxis_title="Time", hovermode="x unified")
            st.plotly_chart(fig_clk, width="stretch")
        else:
            st.info("No click data.")

    st.markdown("---")

    # ----- Spend by advertiser & pricing model --------------------------------
    col_adv, col_pm = st.columns(2)

    with col_adv:
        adv_df = cached_query(Q.SPEND_BY_ADVERTISER, _serialize_params(params))
        if not adv_df.empty:
            adv_df["spend_dollars"] = adv_df["spend_cents"].apply(cents_to_dollars)
            fig_adv = px.bar(
                adv_df.head(15), x="spend_dollars", y="advertiser_name",
                orientation="h", title="Spend by Advertiser (Top 15)",
                labels={"spend_dollars": "Spend ($)", "advertiser_name": "Advertiser"},
                color="spend_dollars", color_continuous_scale="Blues",
            )
            fig_adv.update_layout(yaxis={"autorange": "reversed"}, showlegend=False)
            st.plotly_chart(fig_adv, width="stretch")
        else:
            st.info("No advertiser spend data.")

    with col_pm:
        pm_df = cached_query(Q.SPEND_BY_PRICING_MODEL, _serialize_params(params))
        if not pm_df.empty:
            pm_df["spend_dollars"] = pm_df["spend_cents"].apply(cents_to_dollars)
            fig_pm = px.pie(
                pm_df, values="spend_dollars", names="pricing_model",
                title="Spend by Pricing Model",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(fig_pm, width="stretch")
        else:
            st.info("No pricing model data.")

    # ----- Fill rate over time ------------------------------------------------
    fill_df = cached_query(Q.FILL_RATE_OVER_TIME, _serialize_params(ts_params))
    if not fill_df.empty:
        fig_fill = px.line(
            fill_df, x="bucket", y="fill_rate_pct",
            title=f"Fill Rate Over Time ({_bucket_str} buckets)",
            labels={"bucket": "Time", "fill_rate_pct": "Fill Rate (%)"},
            color_discrete_sequence=["#00CC96"],
        )
        fig_fill.update_layout(xaxis_title="Time", hovermode="x unified")
        st.plotly_chart(fig_fill, width="stretch")


with tab_pacing:
    st.header("Pacing Deep Dive")

    # ----- Top-N selector ----------------------------------------------------
    top_n = st.slider("Top N campaigns (by impressions)", 5, 30, 10, key="pacing_top_n")
    top_camps_df = cached_query(
        Q.TOP_CAMPAIGNS_BY_IMPRESSIONS,
        _serialize_params({**params, "limit": top_n}),
    )

    if top_camps_df.empty:
        st.info("No campaign impression data in the selected range.")
    else:
        # ----- Campaign ranking table ----------------------------------------
        st.subheader("Top Campaigns by Impressions")
        display_camps = top_camps_df.copy()
        display_camps["spend"] = display_camps["spend_cents"].apply(lambda c: fmt_dollars(cents_to_dollars(c)))
        display_camps["total_budget"] = display_camps["total_budget_cents"].apply(
            lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "N/A"
        )
        display_camps["daily_budget"] = display_camps["daily_budget_cents"].apply(
            lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) and c > 0 else "N/A"
        )
        st.dataframe(
            display_camps[["campaign_id", "campaign_name", "advertiser_name",
                           "impressions", "spend", "daily_budget", "total_budget", "campaign_status"]],
            width="stretch",
            hide_index=True,
        )

        st.markdown("---")

        # ----- Pacing summary table ------------------------------------------
        all_campaign_ids = top_camps_df["campaign_id"].tolist()

        pacing_summary_df = cached_query(
            Q.PACING_SUMMARY,
            _serialize_params({**params, "limit": top_n}),
        )

        if not pacing_summary_df.empty:
            st.subheader("Pacing Summary")
            ps_display = pacing_summary_df.copy()
            for col in ["avg_multiplier", "min_multiplier", "max_multiplier",
                         "multiplier_stddev", "multiplier_range", "latest_multiplier"]:
                if col in ps_display.columns:
                    ps_display[col] = ps_display[col].apply(
                        lambda v: f"{float(v):.4f}" if pd.notna(v) else "—"
                    )
            budget_util_col = []
            for _, r in ps_display.iterrows():
                spent_val = r.get("latest_spent_today_cents")
                daily_val = r.get("latest_daily_budget_cents")
                try:
                    spent_f = float(spent_val) if pd.notna(spent_val) else 0.0
                    daily_f = float(daily_val) if pd.notna(daily_val) else 0.0
                except (TypeError, ValueError):
                    spent_f, daily_f = 0.0, 0.0
                if daily_f > 0:
                    pct = spent_f / daily_f * 100
                    if pct > 100:
                        budget_util_col.append(f"{pct:.1f}%")
                    else:
                        budget_util_col.append(f"{pct:.1f}%")
                else:
                    budget_util_col.append("—")
            ps_display["budget_utilization"] = budget_util_col

            # Format budget columns
            ps_display["daily_budget"] = ps_display["latest_daily_budget_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) and float(c) > 0 else "N/A"
            )
            ps_display["daily_spend"] = ps_display["latest_spent_today_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "$0.00"
            )
            ps_display["total_budget"] = ps_display["latest_total_budget_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) and float(c) > 0 else "N/A"
            )
            ps_display["total_spend"] = ps_display["total_spend_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "$0.00"
            )

            st.dataframe(
                ps_display[["campaign_id", "campaign_name", "advertiser_name",
                            "pacing_updates",
                            "daily_spend", "daily_budget",
                            "total_spend", "total_budget",
                            "budget_utilization",
                            "avg_multiplier", "min_multiplier",
                            "max_multiplier",
                            "latest_multiplier", "latest_status"]],
                width="stretch",
                hide_index=True,
            )

        st.markdown("---")

        # ----- Multiplier overlay chart --------------------------------------
        st.subheader("Pacing Multiplier Comparison")
        st.caption(
            "Overlay of pacing multipliers for selected campaigns. "
            "Compare how multipliers diverge across campaigns over time."
        )

        # Default to top-5 by impressions, cap at 10
        default_ids = all_campaign_ids[:5]
        campaign_options = {
            f"{r['campaign_name']} (#{r['campaign_id']})": r["campaign_id"]
            for _, r in top_camps_df.iterrows()
        }
        multiselect_kwargs = dict(
            label="Campaigns to overlay (max 10)",
            options=list(campaign_options.keys()),
            max_selections=10,
            key="pacing_overlay_select",
        )
        if "pacing_overlay_select" not in st.session_state:
            multiselect_kwargs["default"] = list(campaign_options.keys())[:5]

        selected_labels = st.multiselect(**multiselect_kwargs)
        selected_ids = [campaign_options[lbl] for lbl in selected_labels]

        if selected_ids:
            pacing_ts_df = cached_query(
                Q.PACING_MULTIPLIER_TIMESERIES,
                _serialize_params({**params, "campaign_ids": selected_ids}),
            )

            if not pacing_ts_df.empty:
                pacing_ts_df["event_time"] = pd.to_datetime(pacing_ts_df["event_time"], utc=True)

                # -- Multiplier overlay --
                fig_mult = px.line(
                    pacing_ts_df, x="event_time", y="new_multiplier",
                    color="campaign_name",
                    title="Pacing Multiplier Over Time",
                    labels={
                        "event_time": "Time",
                        "new_multiplier": "Multiplier",
                        "campaign_name": "Campaign",
                    },
                )
                fig_mult.update_layout(
                    xaxis_title="Time (seconds)",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                )
                st.plotly_chart(fig_mult, width="stretch")

                # -- Error signal overlay --
                fig_err = px.line(
                    pacing_ts_df, x="event_time", y="error_normalized",
                    color="campaign_name",
                    title="Normalised Error Signal Over Time",
                    labels={
                        "event_time": "Time",
                        "error_normalized": "Error (normalised)",
                        "campaign_name": "Campaign",
                    },
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_err.update_layout(
                    xaxis_title="Time (seconds)",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                )
                fig_err.add_hline(y=0, line_dash="dash", line_color="grey",
                                  annotation_text="Target (0)")
                st.plotly_chart(fig_err, width="stretch")

                st.markdown("---")

                # ----- Per-campaign expandable deep dive ---------------------
                st.subheader("Per-Campaign Pacing Detail")

                for cid in selected_ids:
                    camp_data = pacing_ts_df[pacing_ts_df["campaign_id"] == cid]
                    if camp_data.empty:
                        continue
                    camp_name = camp_data.iloc[0]["campaign_name"]
                    latest = camp_data.iloc[-1]

                    with st.expander(f"{camp_name} (#{cid})", expanded=False):
                        # Status & budget utilization
                        mc1, mc2, mc3, mc4 = st.columns(4)
                        mult_val = float(latest["new_multiplier"]) if pd.notna(latest["new_multiplier"]) else 0.0
                        mc1.metric("Current Multiplier", f"{mult_val:.4f}")
                        mc2.metric("Status", str(latest["status"]))
                        spent = float(latest.get("spent_today_cents") or 0)
                        daily = float(latest.get("daily_budget_cents") or 0)
                        if daily > 0:
                            util_pct = spent / daily * 100
                            util_label = f"{util_pct:.1f}%" if util_pct > 100 else f"{util_pct:.1f}%"
                            mc3.metric("Budget Utilization", util_label)
                            st.progress(min(util_pct / 100.0, 1.0))
                        else:
                            mc3.metric("Budget Utilization", "N/A")
                        remaining = float(latest.get("remaining_budget_cents") or 0)
                        mc4.metric("Remaining Budget", fmt_dollars(remaining / 100.0))

                        # P-term vs I-term
                        fig_pi = go.Figure()
                        fig_pi.add_trace(go.Scatter(
                            x=camp_data["event_time"], y=camp_data["p_term"],
                            mode="lines", name="P-term",
                        ))
                        fig_pi.add_trace(go.Scatter(
                            x=camp_data["event_time"], y=camp_data["i_term"],
                            mode="lines", name="I-term",
                        ))
                        fig_pi.update_layout(
                            title="P-term vs I-term",
                            xaxis_title="Time (seconds)",
                            yaxis_title="Value",
                            hovermode="x unified",
                        )
                        st.plotly_chart(fig_pi, width="stretch")

                        # Urgency
                        if "urgency" in camp_data.columns:
                            fig_urg = px.line(
                                camp_data, x="event_time", y="urgency",
                                title="Urgency Factor",
                                labels={"event_time": "Time", "urgency": "Urgency"},
                                color_discrete_sequence=["#FFA15A"],
                            )
                            fig_urg.update_layout(xaxis_title="Time (seconds)", hovermode="x unified")
                            st.plotly_chart(fig_urg, width="stretch")
            else:
                st.info("No pacing history data for the selected campaigns.")
        else:
            st.info("Select at least one campaign above to view pacing data.")

        st.markdown("---")

        # ----- Budget exhausted campaigns ------------------------------------
        st.subheader("Budget Exhausted Campaigns")
        exhausted_df = cached_query(Q.BUDGET_EXHAUSTED_CAMPAIGNS, _serialize_params(params))
        if not exhausted_df.empty:
            ex_display = exhausted_df.copy()
            ex_display["total_budget"] = ex_display["total_budget_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "N/A"
            )
            ex_display["remaining"] = ex_display["remaining_budget_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "N/A"
            )
            ex_display["daily_budget"] = ex_display["daily_budget_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) and float(c) > 0 else "N/A"
            )
            ex_display["daily_spend"] = ex_display["spent_today_cents"].apply(
                lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "$0.00"
            )
            st.dataframe(
                ex_display[["campaign_id", "campaign_name", "advertiser_name",
                            "exhausted_at",
                            "daily_spend", "daily_budget",
                            "total_budget", "remaining"]],
                width="stretch",
                hide_index=True,
            )
        else:
            st.success("No campaigns have exhausted their budget in this window.")


with tab_ads:
    st.header("Ad & Campaign Performance")

    # ----- Campaign performance table ----------------------------------------
    st.subheader("Campaign Performance")
    camp_perf_df = cached_query(Q.CAMPAIGN_PERFORMANCE, _serialize_params(params))

    if not camp_perf_df.empty:
        cp_display = camp_perf_df.copy()
        cp_display["spend"] = cp_display["spend_cents"].apply(lambda c: fmt_dollars(cents_to_dollars(c)))
        cp_display["total_budget"] = cp_display["total_budget_cents"].apply(
            lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "N/A"
        )
        cp_display["daily_budget"] = cp_display["daily_budget_cents"].apply(
            lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) and c > 0 else "N/A"
        )
        cp_display["ctr"] = cp_display["ctr_pct"].apply(lambda v: f"{float(v):.2f}%")
        cp_display["ecpm"] = cp_display["ecpm_dollars"].apply(
            lambda v: fmt_dollars(float(v)) if pd.notna(v) else "N/A"
        )
        st.dataframe(
            cp_display[["campaign_id", "campaign_name", "advertiser_name",
                         "impressions", "clicks", "spend", "ctr", "ecpm",
                         "daily_budget", "total_budget", "campaign_status"]],
            width="stretch",
            hide_index=True,
        )

        st.markdown("---")

        # ----- Per-campaign ad breakdown (batch query) -------------------------
        st.subheader("Ads per Campaign")
        st.caption("Expand a campaign to see individual ad performance.")

        top_campaign_ids = camp_perf_df["campaign_id"].head(20).tolist()
        all_ads_df = cached_query(
            Q.ADS_IN_CAMPAIGNS,
            _serialize_params({**params, "campaign_ids": top_campaign_ids}),
        )

        for _, camp_row in camp_perf_df.head(20).iterrows():
            cid = camp_row["campaign_id"]
            label = f"{camp_row['campaign_name']} (#{cid}) — {fmt_dollars(cents_to_dollars(camp_row['spend_cents']))} spend"
            with st.expander(label, expanded=False):
                if not all_ads_df.empty:
                    ads_df = all_ads_df[all_ads_df["campaign_id"] == cid]
                else:
                    ads_df = pd.DataFrame()
                if not ads_df.empty:
                    ad_disp = ads_df.copy()
                    ad_disp["spend"] = ad_disp["spend_cents"].apply(lambda c: fmt_dollars(cents_to_dollars(c)))
                    ad_disp["ctr"] = ad_disp["ctr_pct"].apply(lambda v: f"{float(v):.2f}%")
                    ad_disp["bid"] = ad_disp["bid_amount_cents"].apply(lambda c: fmt_dollars(cents_to_dollars(c)))
                    st.dataframe(
                        ad_disp[["ad_id", "headline", "pricing_model", "bid",
                                 "impressions", "clicks", "spend", "ctr", "destination_url"]],
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("No ad-level data for this campaign.")

        st.markdown("---")

        # ----- Spend burn-down ------------------------------------------------
        st.subheader("Campaign Spend Burn-Down")
        st.caption("Remaining budget over time for top campaigns (from pacing history).")

        burndown_ids = camp_perf_df["campaign_id"].head(10).tolist()
        if burndown_ids:
            burndown_df = cached_query(
                Q.CAMPAIGN_SPEND_BURNDOWN,
                _serialize_params({**params, "campaign_ids": burndown_ids}),
            )
            if not burndown_df.empty:
                burndown_df["event_time"] = pd.to_datetime(burndown_df["event_time"], utc=True)
                burndown_df["remaining_budget_dollars"] = burndown_df["remaining_budget_cents"].apply(
                    lambda c: float(c or 0) / 100.0
                )
                fig_burn = px.line(
                    burndown_df, x="event_time", y="remaining_budget_dollars",
                    color="campaign_name",
                    title="Remaining Budget Over Time",
                    labels={
                        "event_time": "Time",
                        "remaining_budget_dollars": "Remaining Budget ($)",
                        "campaign_name": "Campaign",
                    },
                )
                fig_burn.update_layout(
                    xaxis_title="Time (seconds)",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                )
                st.plotly_chart(fig_burn, width="stretch")
            else:
                st.info("No pacing history for burn-down chart.")

    else:
        st.info("No campaign performance data in the selected range.")

    st.markdown("---")

    # ----- Top winning ads from auctions -------------------------------------
    st.subheader("Top Winning Ads (by Auction Wins)")
    winners_df = cached_query(Q.TOP_WINNING_ADS, _serialize_params({**params, "limit": 20}))
    if not winners_df.empty:
        w_disp = winners_df.copy()
        w_disp["avg_bid"] = w_disp["avg_winning_bid_cents"].apply(
            lambda c: fmt_dollars(cents_to_dollars(c)) if pd.notna(c) else "N/A"
        )
        w_disp["avg_score"] = w_disp["avg_final_score"].apply(
            lambda v: f"{float(v):.4f}" if pd.notna(v) else "N/A"
        )
        st.dataframe(
            w_disp[["ad_id", "headline", "campaign_name", "auction_wins",
                     "avg_bid", "avg_score", "destination_url"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No auction winner data in the selected range.")

if auto_refresh:
    _time.sleep(refresh_interval)
    st.rerun()



