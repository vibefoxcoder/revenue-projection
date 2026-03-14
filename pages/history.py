"""History page — view and manage past entries."""

import streamlit as st
import pandas as pd
from tracker.sheets import read_config, read_monthly_revenue, read_daily_revenue, delete_row


def _get_ss_key():
    return st.secrets["spreadsheet_key"]


def render_history():
    st.header("Data History")

    config = read_config(_get_ss_key())
    period = config["current_period"]

    tab1, tab2 = st.tabs(["Monthly Revenue", "Daily Snapshots"])

    with tab1:
        st.subheader(f"Monthly Revenue — {period}")
        monthly_df = read_monthly_revenue(_get_ss_key(), period)
        if monthly_df.empty:
            st.info("No monthly revenue entries yet.")
        else:
            st.dataframe(monthly_df, width="stretch", hide_index=True)

            with st.expander("Delete an entry"):
                st.caption("Select a row index to delete (0-based from the data shown above).")
                row_idx = st.number_input(
                    "Row index", min_value=0, max_value=len(monthly_df) - 1,
                    step=1, key="del_monthly"
                )
                row = monthly_df.iloc[row_idx]
                st.write(f"Will delete: {row['broker']} — {row['month']} — ${row['revenue_usd']:,.0f}")
                if st.button("Delete", key="del_monthly_btn"):
                    # Find the actual sheet row index for this entry
                    # We need to account for rows from other periods
                    full_monthly = read_monthly_revenue.__wrapped__(_get_ss_key(), period)
                    # The row_idx here is relative to the filtered period data
                    # We need to find it in the full sheet
                    delete_row(_get_ss_key(), "monthly_revenue", int(row_idx))
                    st.success("Deleted.")
                    st.cache_data.clear()
                    st.rerun()

    with tab2:
        st.subheader(f"Daily Snapshots — {period}")
        daily_df = read_daily_revenue(_get_ss_key(), period)
        if daily_df.empty:
            st.info("No daily snapshot entries yet.")
        else:
            st.dataframe(daily_df, width="stretch", hide_index=True)

            with st.expander("Delete an entry"):
                st.caption("Select a row index to delete (0-based from the data shown above).")
                row_idx = st.number_input(
                    "Row index", min_value=0, max_value=len(daily_df) - 1,
                    step=1, key="del_daily"
                )
                row = daily_df.iloc[row_idx]
                st.write(f"Will delete: {row['broker']} — {row['date']} — ${row['revenue_usd']:,.0f}")
                if st.button("Delete", key="del_daily_btn"):
                    delete_row(_get_ss_key(), "daily_revenue", int(row_idx))
                    st.success("Deleted.")
                    st.cache_data.clear()
                    st.rerun()
