"""One-time script: Seed Google Sheets with baseline data from Bonus_calculations.xlsx.

Run locally: python seed_data.py

Requires:
- .streamlit/secrets.toml with gcp_service_account and spreadsheet_key
- Or set environment variables: GCP_CREDENTIALS_JSON (path) and SPREADSHEET_KEY
"""

import json
import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 2H25 broker baseline data from the spreadsheet
BROKERS_2H25 = [
    {"period": "2H25", "broker": "Luke Cheong", "salary_sgd": 187794, "cpf_sgd": 9828, "ins_sgd": 8479, "te_sgd": 20236, "comms_sgd": 36000},
    {"period": "2H25", "broker": "Peggy Ho", "salary_sgd": 148902, "cpf_sgd": 6662, "ins_sgd": 3316, "te_sgd": 20640, "comms_sgd": 36000},
    {"period": "2H25", "broker": "Junnie Liew", "salary_sgd": 200820, "cpf_sgd": 9828, "ins_sgd": 8479, "te_sgd": 13100, "comms_sgd": 36000},
    {"period": "2H25", "broker": "Saurabh Pal", "salary_sgd": 124902, "cpf_sgd": 9848, "ins_sgd": 8465, "te_sgd": 48020, "comms_sgd": 36000},
    {"period": "2H25", "broker": "Kelly Tan", "salary_sgd": 239658, "cpf_sgd": 9848, "ins_sgd": 8619, "te_sgd": 21274, "comms_sgd": 36000},
    {"period": "2H25", "broker": "Dion Tan", "salary_sgd": 27238, "cpf_sgd": 4702, "ins_sgd": 2800, "te_sgd": 3741, "comms_sgd": 36000},
    {"period": "2H25", "broker": "Camille Arena", "salary_sgd": 45300, "cpf_sgd": 0, "ins_sgd": 3096, "te_sgd": 13013, "comms_sgd": 36000},
    {"period": "2H25", "broker": "Adeline Thian", "salary_sgd": 43800, "cpf_sgd": 9346, "ins_sgd": 8191, "te_sgd": 0, "comms_sgd": 0},
]

# 1H26 costs — copied from 2H25 baseline (update T&E as needed)
BROKERS_1H26 = [
    {**b, "period": "1H26"} for b in BROKERS_2H25
]

CONFIG = [
    ["usd_sgd_rate", "1.29"],
    ["mgmt_split", "0.45"],
    ["desk_split", "0.55"],
    ["promo_pct", "0.01"],
    ["kelly_override_pct", "0.05"],
    ["current_period", "1H26"],
    ["period_start", "2026-01-01"],
    ["period_end", "2026-06-30"],
]

BROKER_HEADERS = ["period", "broker", "salary_sgd", "cpf_sgd", "ins_sgd", "te_sgd", "comms_sgd"]


def get_credentials():
    """Get credentials from secrets.toml or environment."""
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        import tomllib
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        creds_info = secrets["gcp_service_account"]
        ss_key = secrets["spreadsheet_key"]
    else:
        creds_path = os.environ["GCP_CREDENTIALS_JSON"]
        with open(creds_path) as f:
            creds_info = json.load(f)
        ss_key = os.environ["SPREADSHEET_KEY"]

    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds), ss_key


def seed():
    client, ss_key = get_credentials()
    ss = client.open_by_key(ss_key)

    # --- Config tab ---
    try:
        ws = ss.worksheet("config")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet("config", rows=20, cols=2)
    ws.clear()
    ws.update(values=CONFIG, range_name="A1")
    print("Config tab seeded.")

    # --- Brokers tab ---
    try:
        ws = ss.worksheet("brokers")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet("brokers", rows=50, cols=len(BROKER_HEADERS))
    ws.clear()
    all_brokers = BROKERS_2H25 + BROKERS_1H26
    rows = [BROKER_HEADERS] + [[b[h] for h in BROKER_HEADERS] for b in all_brokers]
    ws.update(values=rows, range_name="A1")
    print(f"Brokers tab seeded with {len(all_brokers)} rows.")

    # --- Monthly revenue tab (empty with header) ---
    try:
        ws = ss.worksheet("monthly_revenue")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet("monthly_revenue", rows=200, cols=5)
    ws.clear()
    ws.update(values=[["period", "month", "broker", "revenue_usd", "entered_date"]], range_name="A1")
    print("Monthly revenue tab initialized.")

    # --- Daily revenue tab (empty with header) ---
    try:
        ws = ss.worksheet("daily_revenue")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet("daily_revenue", rows=500, cols=5)
    ws.clear()
    ws.update(values=[["period", "date", "broker", "revenue_usd", "entered_date"]], range_name="A1")
    print("Daily revenue tab initialized.")

    print("\nDone! Google Sheet is ready.")


if __name__ == "__main__":
    seed()
