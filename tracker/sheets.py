"""Google Sheets data layer — all read/write operations."""

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from tracker.config import parse_config


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_client() -> gspread.Client:
    """Authenticate with Google Sheets using service account from st.secrets."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def get_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    """Open the tracker spreadsheet by key from secrets."""
    return client.open_by_key(st.secrets["spreadsheet_key"])


# --- Read operations (cached) ---


@st.cache_data(ttl=300)
def read_config(_spreadsheet_key: str) -> dict:
    """Read config tab into a typed dict."""
    client = get_client()
    ss = client.open_by_key(_spreadsheet_key)
    ws = ss.worksheet("config")
    rows = ws.get_all_values()
    raw = {row[0]: row[1] for row in rows if len(row) >= 2 and row[0]}
    return parse_config(raw)


@st.cache_data(ttl=300)
def read_brokers(_spreadsheet_key: str, period: str) -> pd.DataFrame:
    """Read broker cost data for a given period."""
    client = get_client()
    ss = client.open_by_key(_spreadsheet_key)
    ws = ss.worksheet("brokers")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(
            columns=["period", "broker", "salary_sgd", "cpf_sgd", "ins_sgd", "te_sgd", "comms_sgd"]
        )
    # Ensure numeric columns
    for col in ["salary_sgd", "cpf_sgd", "ins_sgd", "te_sgd", "comms_sgd"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df[df["period"] == period].reset_index(drop=True)


@st.cache_data(ttl=300)
def read_monthly_revenue(_spreadsheet_key: str, period: str) -> pd.DataFrame:
    """Read monthly revenue entries for a given period."""
    client = get_client()
    ss = client.open_by_key(_spreadsheet_key)
    ws = ss.worksheet("monthly_revenue")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=["period", "month", "broker", "revenue_usd", "entered_date"])
    df["revenue_usd"] = pd.to_numeric(df["revenue_usd"], errors="coerce").fillna(0)
    return df[df["period"] == period].reset_index(drop=True)


@st.cache_data(ttl=300)
def read_daily_revenue(_spreadsheet_key: str, period: str) -> pd.DataFrame:
    """Read daily revenue snapshots for a given period."""
    client = get_client()
    ss = client.open_by_key(_spreadsheet_key)
    ws = ss.worksheet("daily_revenue")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=["period", "date", "broker", "revenue_usd", "entered_date"])
    df["revenue_usd"] = pd.to_numeric(df["revenue_usd"], errors="coerce").fillna(0)
    return df[df["period"] == period].reset_index(drop=True)


# --- Write operations ---


def save_monthly_revenue(spreadsheet_key: str, period: str, month: str, rows: list[list]) -> None:
    """Save monthly revenue, replacing any existing entries for the same period+month."""
    client = get_client()
    ss = client.open_by_key(spreadsheet_key)
    ws = ss.worksheet("monthly_revenue")
    all_rows = ws.get_all_values()
    header = all_rows[0]
    # Keep rows that don't match this period+month
    kept = [r for r in all_rows[1:] if not (r[0] == period and r[1] == month)]
    # Rewrite sheet: header + kept rows + new rows
    ws.clear()
    ws.update(values=[header] + kept + rows, range_name="A1")
    st.cache_data.clear()


def append_daily_revenue(spreadsheet_key: str, rows: list[list]) -> None:
    """Append daily revenue snapshot rows. Each row: [period, date, broker, revenue_usd, entered_date]."""
    client = get_client()
    ss = client.open_by_key(spreadsheet_key)
    ws = ss.worksheet("daily_revenue")
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    st.cache_data.clear()


def update_broker_te(spreadsheet_key: str, period: str, broker: str, new_te: float) -> None:
    """Update T&E for a specific broker in a given period."""
    client = get_client()
    ss = client.open_by_key(spreadsheet_key)
    ws = ss.worksheet("brokers")
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if row.get("period") == period and row.get("broker") == broker:
            # Row index in sheet is i+2 (1-indexed header + 1-indexed data)
            ws.update_cell(i + 2, 6, new_te)  # te_sgd is column 6
            st.cache_data.clear()
            return
    raise ValueError(f"Broker '{broker}' not found for period '{period}'")


def delete_row(spreadsheet_key: str, sheet_name: str, row_index: int) -> None:
    """Delete a row by index (0-based data index, i.e. row 0 = first data row after header)."""
    client = get_client()
    ss = client.open_by_key(spreadsheet_key)
    ws = ss.worksheet(sheet_name)
    ws.delete_rows(row_index + 2)  # +2 for 1-indexed + header row
    st.cache_data.clear()
