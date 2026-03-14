"""Main dashboard — metrics, charts, broker detail table."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from tracker.sheets import read_config, read_brokers, read_monthly_revenue, read_daily_revenue
from tracker.calc import compute_all


def _get_ss_key():
    return st.secrets["spreadsheet_key"]


def render_dashboard():
    st.header("Dashboard")

    config = read_config(_get_ss_key())
    period = config["current_period"]
    brokers_df = read_brokers(_get_ss_key(), period)

    if brokers_df.empty:
        st.warning(f"No broker data for period {period}. Go to Data Entry to seed data.")
        return

    monthly_df = read_monthly_revenue(_get_ss_key(), period)
    daily_df = read_daily_revenue(_get_ss_key(), period)

    st.subheader(f"Period: {period}")
    usd_sgd = st.number_input(
        "USD/SGD Rate",
        min_value=0.50, max_value=3.00,
        value=float(config["usd_sgd_rate"]),
        step=0.01, format="%.4f",
    )
    config["usd_sgd_rate"] = usd_sgd

    # Recompute with updated rate
    results = compute_all(brokers_df, monthly_df, daily_df, config)
    actual_pool = results["actual_pool"]
    projected_pool = results["projected_pool"]
    display = results["display"]

    # --- Row 1: Metric Cards ---
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric(
            "Revenue (Actual)",
            f"${actual_pool['total_revenue']:,.0f}",
        )
    with c2:
        st.metric(
            "Revenue (Projected)",
            f"${projected_pool['total_revenue']:,.0f}",
        )
    with c3:
        st.metric(
            "R/TC Ratio (Proj.)",
            f"{projected_pool['rtc_ratio']:.2f}x",
        )
    with c4:
        st.metric(
            "Bonus Pool (Proj.)",
            f"${projected_pool['distributable_pool']:,.0f}",
        )
    with c5:
        st.metric(
            "Kelly 5% Override",
            f"${projected_pool['kelly_override']:,.0f}",
        )

    st.markdown("---")

    # --- Row 2: Charts ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Revenue by Broker")
        chart_df = display[["broker", "actual_revenue", "projected_revenue"]].copy()
        chart_df["remaining"] = chart_df["projected_revenue"] - chart_df["actual_revenue"]
        chart_df.loc[chart_df["remaining"] < 0, "remaining"] = 0

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=chart_df["broker"], y=chart_df["actual_revenue"],
            name="Actual", marker_color="#2196F3"
        ))
        fig.add_trace(go.Bar(
            x=chart_df["broker"], y=chart_df["remaining"],
            name="Projected Remaining", marker_color="#90CAF9"
        ))
        fig.update_layout(barmode="stack", height=400, margin=dict(t=20, b=20))
        st.plotly_chart(fig, width="stretch")

    with col_right:
        st.subheader("Monthly Revenue Trend")
        if not monthly_df.empty:
            trend = monthly_df.groupby("month")["revenue_usd"].sum().reset_index()
            trend.columns = ["Month", "Revenue"]
            trend = trend.sort_values("Month")
            # Convert "2026-01" to "Jan 26" etc.
            trend["Month"] = pd.to_datetime(trend["Month"]).dt.strftime("%b %y")
            fig2 = px.bar(trend, x="Month", y="Revenue", color_discrete_sequence=["#2196F3"])
            fig2.update_layout(height=400, margin=dict(t=20, b=20))
            fig2.update_xaxes(type="category")
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("No monthly revenue data yet.")

    st.markdown("---")

    # --- Row 3: Broker Detail Table ---
    st.subheader(f"Broker Detail (USD/SGD: {usd_sgd:.4f})")
    table = display.copy()
    table.columns = [
        "Broker", "T&E (SGD)", "Total Cost (SGD)", "Cost (USD)",
        "Revenue (Actual)", "Revenue (Projected)",
        "Daily Run Rate", "Rev Share %", "Formula Bonus", "Payout Ratio"
    ]

    # Add Kelly's override to her row
    kelly_override = projected_pool["kelly_override"]
    table["Total Bonus"] = table["Formula Bonus"]
    table.loc[table["Broker"] == "Kelly Tan", "Total Bonus"] += kelly_override

    # Format for display
    fmt = table.copy()
    fmt["T&E (SGD)"] = fmt["T&E (SGD)"].map("S${:,.0f}".format)
    fmt["Total Cost (SGD)"] = fmt["Total Cost (SGD)"].map("S${:,.0f}".format)
    fmt["Cost (USD)"] = fmt["Cost (USD)"].map("${:,.0f}".format)
    fmt["Revenue (Actual)"] = fmt["Revenue (Actual)"].map("${:,.0f}".format)
    fmt["Revenue (Projected)"] = fmt["Revenue (Projected)"].map("${:,.0f}".format)
    fmt["Daily Run Rate"] = fmt["Daily Run Rate"].map("${:,.0f}".format)
    fmt["Rev Share %"] = fmt["Rev Share %"].map("{:.1%}".format)
    fmt["Formula Bonus"] = fmt["Formula Bonus"].map("${:,.0f}".format)
    fmt["Total Bonus"] = fmt["Total Bonus"].map("${:,.0f}".format)
    fmt["Payout Ratio"] = fmt["Payout Ratio"].apply(
        lambda x: f"{x:.1%}" if pd.notna(x) else "--"
    )

    st.dataframe(fmt, width="stretch", hide_index=True)

    # --- Row 4: Bonus Pool Breakdown ---
    st.markdown("---")
    st.subheader("Projected Bonus Pool Breakdown")
    pool = projected_pool

    breakdown = pd.DataFrame({
        "Item": [
            "Total Revenue",
            "1% Promo Deduction",
            "Net Revenue",
            f"Mgmt Share ({config['mgmt_split']:.0%})",
            f"Desk Share ({config['desk_split']:.0%})",
            "Total Cost",
            "Bonus Pool (Max)",
            f"Kelly Override ({config['kelly_override_pct']:.0%})",
            "Distributable Pool",
        ],
        "Amount (USD)": [
            pool["total_revenue"],
            -pool["promo"],
            pool["net_revenue"],
            pool["mgmt_share"],
            pool["desk_share"],
            -pool["total_cost"],
            pool["bonus_pool_max"],
            -pool["kelly_override"],
            pool["distributable_pool"],
        ],
    })
    breakdown["Amount (USD)"] = breakdown["Amount (USD)"].map("${:,.0f}".format)
    st.dataframe(breakdown, width="stretch", hide_index=True)

    # Footer
    st.caption(f"Projections as of {results['as_of_date']} | USD/SGD: {usd_sgd:.4f} | Data refreshes every 5 minutes")
