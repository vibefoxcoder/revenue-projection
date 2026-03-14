"""Load configuration from Google Sheets config tab."""

from datetime import date, datetime

DEFAULTS = {
    "usd_sgd_rate": 1.29,
    "mgmt_split": 0.45,
    "desk_split": 0.55,
    "promo_pct": 0.01,
    "kelly_override_pct": 0.05,
    "current_period": "1H26",
    "period_start": date(2026, 1, 1),
    "period_end": date(2026, 6, 30),
}

# Keys that should be parsed as floats
FLOAT_KEYS = {"usd_sgd_rate", "mgmt_split", "desk_split", "promo_pct", "kelly_override_pct"}
# Keys that should be parsed as dates
DATE_KEYS = {"period_start", "period_end"}


def parse_config(raw: dict[str, str]) -> dict:
    """Parse raw string key-value pairs from the config sheet into typed values."""
    config = dict(DEFAULTS)
    for key, val in raw.items():
        if key in FLOAT_KEYS:
            config[key] = float(val)
        elif key in DATE_KEYS:
            config[key] = datetime.strptime(val, "%Y-%m-%d").date()
        else:
            config[key] = val
    return config
