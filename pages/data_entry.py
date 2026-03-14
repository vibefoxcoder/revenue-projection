"""Data entry page — monthly revenue, daily snapshots, T&E updates."""

import streamlit as st
from datetime import date, datetime
from tracker.sheets import (
    read_config, read_brokers, read_monthly_revenue, read_daily_revenue,
    append_monthly_revenue, append_daily_revenue, update_broker_te,
)


def _get_ss_key():
    return st.secrets["spreadsheet_key"]


def render_data_entry():
    st.header("Data Entry")

    config = read_config(_get_ss_key())
    period = config["current_period"]
    brokers_df = read_brokers(_get_ss_key(), period)

    if brokers_df.empty:
        st.warning(f"No broker data found for period {period}. Seed data first.")
        return

    broker_names = brokers_df["broker"].tolist()

    tab1, tab2, tab3 = st.tabs(["Monthly Revenue", "Daily Snapshot", "Update T&E"])

    # --- Monthly Revenue Entry ---
    with tab1:
        st.subheader("Monthly Revenue (Month-End Actuals)")

        period_start = config["period_start"]
        period_end = config["period_end"]

        # Generate month options for the period
        months = []
        current = period_start.replace(day=1)
        while current <= period_end:
            months.append(current.strftime("%Y-%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        selected_month = st.selectbox("Month", months)

        # Load existing data for this month
        monthly_df = read_monthly_revenue(_get_ss_key(), period)
        existing = {}
        if not monthly_df.empty:
            month_data = monthly_df[monthly_df["month"] == selected_month]
            for _, row in month_data.iterrows():
                existing[row["broker"]] = float(row["revenue_usd"])

        has_existing = bool(existing)
        if has_existing:
            st.info(f"Existing data found for {selected_month}. Values pre-filled below.")

        with st.form(f"monthly_revenue_form_{selected_month}"):
            st.caption("Enter confirmed revenue (USD) for each broker:")
            revenues = {}
            cols = st.columns(2)
            for i, broker in enumerate(broker_names):
                with cols[i % 2]:
                    revenues[broker] = st.number_input(
                        broker, min_value=0.0,
                        value=existing.get(broker, 0.0),
                        step=1000.0, format="%.0f",
                        key=f"monthly_{selected_month}_{broker}"
                    )

            submitted = st.form_submit_button("Save Monthly Revenue")
            if submitted:
                today_str = date.today().isoformat()
                rows = [
                    [period, selected_month, broker, rev, today_str]
                    for broker, rev in revenues.items()
                    if rev > 0
                ]
                if rows:
                    append_monthly_revenue(_get_ss_key(), rows)
                    st.success(f"Saved {len(rows)} entries for {selected_month}")
                else:
                    st.warning("No revenue entered (all zeros).")

    # --- Daily Revenue Snapshot ---
    with tab2:
        st.subheader("Daily Revenue Snapshot (MTD Cumulative)")

        snapshot_date = st.date_input("Snapshot Date", value=date.today())

        # Load existing data for this date
        daily_df = read_daily_revenue(_get_ss_key(), period)
        existing_daily = {}
        if not daily_df.empty:
            date_str = snapshot_date.isoformat()
            day_data = daily_df[daily_df["date"] == date_str]
            for _, row in day_data.iterrows():
                existing_daily[row["broker"]] = float(row["revenue_usd"])

        if existing_daily:
            st.info(f"Existing snapshot found for {snapshot_date}. Values pre-filled below.")

        date_key = snapshot_date.isoformat()
        with st.form(f"daily_revenue_form_{date_key}"):
            st.caption("Enter month-to-date cumulative revenue (USD) per broker:")
            revenues = {}
            cols = st.columns(2)
            for i, broker in enumerate(broker_names):
                with cols[i % 2]:
                    revenues[broker] = st.number_input(
                        broker, min_value=0.0,
                        value=existing_daily.get(broker, 0.0),
                        step=1000.0, format="%.0f",
                        key=f"daily_{date_key}_{broker}"
                    )

            submitted = st.form_submit_button("Save Daily Snapshot")
            if submitted:
                today_str = date.today().isoformat()
                date_str = snapshot_date.isoformat()
                rows = [
                    [period, date_str, broker, rev, today_str]
                    for broker, rev in revenues.items()
                    if rev > 0
                ]
                if rows:
                    append_daily_revenue(_get_ss_key(), rows)
                    st.success(f"Saved {len(rows)} entries for {date_str}")
                else:
                    st.warning("No revenue entered (all zeros).")

    # --- T&E Update ---
    with tab3:
        st.subheader("Update Travel & Entertainment Costs")

        selected_broker = st.selectbox("Broker", broker_names)

        current_te = brokers_df.loc[
            brokers_df["broker"] == selected_broker, "te_sgd"
        ].iloc[0]
        st.info(f"Current T&E for {selected_broker}: S${current_te:,.0f}")

        with st.form("te_update_form"):
            new_te = st.number_input(
                "New T&E (SGD)", min_value=0.0, value=float(current_te),
                step=500.0, format="%.0f"
            )
            submitted = st.form_submit_button("Update T&E")
            if submitted:
                update_broker_te(_get_ss_key(), period, selected_broker, new_te)
                st.success(f"Updated {selected_broker} T&E to S${new_te:,.0f}")
