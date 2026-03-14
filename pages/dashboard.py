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

    # --- Metric Cards (2 per row for mobile) ---
    breakeven_rev = actual_pool["total_cost"] / (config["desk_split"] * (1 - config["promo_pct"]))
    gap_to_breakeven = breakeven_rev - actual_pool["total_revenue"]

    # Row 1: Actuals
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Revenue (Actual)", f"${actual_pool['total_revenue']:,.0f}")
    with c2:
        st.metric("Total Cost (6M)", f"${actual_pool['total_cost']:,.0f}")
    with c3:
        st.metric("R/TC (Actual)", f"{actual_pool['rtc_ratio']:.2f}x")

    # Row 2: Breakeven + Projections
    c4, c5, c6 = st.columns(3)
    with c4:
        if gap_to_breakeven > 0:
            st.metric("Breakeven Revenue", f"${breakeven_rev:,.0f}", delta=f"${gap_to_breakeven:,.0f} more needed", delta_color="inverse")
        else:
            st.metric("Breakeven Revenue", f"${breakeven_rev:,.0f}", delta=f"${-gap_to_breakeven:,.0f} above", delta_color="normal")
    with c5:
        st.metric("Revenue (Projected)", f"${projected_pool['total_revenue']:,.0f}")
    with c6:
        st.metric("R/TC (Projected)", f"{projected_pool['rtc_ratio']:.2f}x")

    # Row 3: Bonus
    c7, c8 = st.columns(2)
    with c7:
        st.metric("Bonus Pool (Proj.)", f"${projected_pool['distributable_pool']:,.0f}")
    with c8:
        st.metric("Kelly 5% Override", f"${projected_pool['kelly_override']:,.0f}")

    st.markdown("---")

    # --- Broker Rev/Cost Table + Chart ---
    st.subheader("Broker Rev/Cost Ratio")
    ratio_df = display[["broker", "cost_usd", "actual_revenue", "projected_revenue"]].copy()
    ratio_df["rev_cost_ratio"] = ratio_df.apply(
        lambda r: r["actual_revenue"] / r["cost_usd"] if r["cost_usd"] > 0 else 0, axis=1
    )

    # Table — reorder: Broker, Cost, Actual Rev, Rev/Cost, Projected Rev
    ratio_fmt = ratio_df[["broker", "cost_usd", "actual_revenue", "rev_cost_ratio", "projected_revenue"]].copy()
    ratio_fmt.columns = ["Broker", "Cost (6M)", "Revenue (Actual)", "Rev/Cost", "Revenue (Proj.)"]
    ratio_fmt["Cost (6M)"] = ratio_fmt["Cost (6M)"].map("${:,.0f}".format)
    ratio_fmt["Revenue (Actual)"] = ratio_fmt["Revenue (Actual)"].map("${:,.0f}".format)
    ratio_fmt["Rev/Cost"] = ratio_fmt["Rev/Cost"].map("{:.2f}x".format)
    ratio_fmt["Revenue (Proj.)"] = ratio_fmt["Revenue (Proj.)"].map("${:,.0f}".format)
    st.dataframe(ratio_fmt, width="stretch", hide_index=True)

    # Chart
    chart_data = ratio_df[ratio_df["actual_revenue"] > 0].sort_values("rev_cost_ratio", ascending=True)
    colors = ["#E53935" if r < 1 else "#FFA726" if r < 2 else "#43A047" for r in chart_data["rev_cost_ratio"]]
    fig = go.Figure(go.Bar(
        x=chart_data["rev_cost_ratio"],
        y=chart_data["broker"],
        orientation="h",
        marker_color=colors,
        text=chart_data["rev_cost_ratio"].map("{:.2f}x".format),
        textposition="outside",
    ))
    fig.add_vline(x=1, line_dash="dash", line_color="red", annotation_text="Breakeven")
    fig.update_layout(height=350, margin=dict(t=20, b=20, l=10, r=40), xaxis_title="Actual Rev / 6M Cost")
    st.plotly_chart(fig, width="stretch")

    # --- Monthly Revenue Table ---
    if not monthly_df.empty:
        st.subheader("Monthly Revenue")
        pivot = monthly_df.pivot_table(index="broker", columns="month", values="revenue_usd", aggfunc="sum", fill_value=0)
        pivot.columns = [pd.to_datetime(c).strftime("%b %y") for c in pivot.columns]
        pivot["Total"] = pivot.sum(axis=1)
        pivot = pivot.reset_index()
        pivot.columns = ["Broker"] + list(pivot.columns[1:])
        # Format
        fmt_pivot = pivot.copy()
        for col in fmt_pivot.columns[1:]:
            fmt_pivot[col] = fmt_pivot[col].map("${:,.0f}".format)
        st.dataframe(fmt_pivot, width="stretch", hide_index=True)

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
