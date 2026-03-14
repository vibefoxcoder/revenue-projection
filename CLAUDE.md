# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Brokerage desk revenue/bonus projection tracker. Streamlit app with Google Sheets as data store, deployed to Streamlit Community Cloud.

Tracks 8 brokers' costs and revenue, projects bonuses using run-rate extrapolation based on business days.

## Commands

```bash
source venv/Scripts/activate
pip install -r requirements.txt
streamlit run app.py              # local dev
python seed_data.py               # one-time: seed Google Sheets with baseline data
```

## Architecture

- `calc.py` — Pure business logic (no Streamlit/gspread deps). All projection and bonus formulas.
- `config.py` — Config loader/parser from Google Sheets config tab.
- `sheets.py` — Google Sheets CRUD via gspread. Read functions cached with `@st.cache_data(ttl=300)`.
- `app.py` — Streamlit entry point, page routing.
- `pages/dashboard.py` — Metrics, charts, broker detail table.
- `pages/data_entry.py` — Monthly revenue, daily snapshot, T&E update forms.
- `pages/history.py` — View/delete past entries.
- `seed_data.py` — One-time script to populate Google Sheets from hardcoded baseline data.

## Business Logic (calc.py)

Revenue split: 45% management / 55% desk. Bonus pool = 55% * (Revenue - 1% Promo) - Total Cost. Kelly gets 5% off top. Per-broker bonus proportional to revenue share. Costs in SGD converted to USD via configurable rate (default 1.29).

## Google Sheets Structure

4 tabs: `config` (key-value), `brokers` (period/cost data), `monthly_revenue` (month-end actuals), `daily_revenue` (MTD snapshots). Credentials via `st.secrets["gcp_service_account"]`, sheet key via `st.secrets["spreadsheet_key"]`.

## Deployment

Hosted on Streamlit Community Cloud. Requires `.streamlit/secrets.toml` locally (not committed) with `gcp_service_account` and `spreadsheet_key`.
