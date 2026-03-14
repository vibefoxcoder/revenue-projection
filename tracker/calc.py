"""Pure business logic for revenue projection and bonus calculations.

No Streamlit or gspread dependencies — operates on DataFrames and dicts only.
"""

import numpy as np
import pandas as pd
from datetime import date


def compute_broker_costs(brokers_df: pd.DataFrame, usd_sgd_rate: float) -> pd.DataFrame:
    """Add total_cost_sgd and cost_usd columns to broker cost data."""
    df = brokers_df.copy()
    cost_cols = ["salary_sgd", "cpf_sgd", "ins_sgd", "te_sgd", "comms_sgd"]
    df["total_cost_sgd"] = df[cost_cols].fillna(0).sum(axis=1)
    df["cost_usd"] = df["total_cost_sgd"] / usd_sgd_rate
    return df


def compute_actual_revenue(
    monthly_df: pd.DataFrame, daily_df: pd.DataFrame, brokers: list[str]
) -> pd.DataFrame:
    """Compute per-broker actual YTD revenue from monthly + daily snapshots.

    monthly_df: confirmed month-end revenue (period, month, broker, revenue_usd)
    daily_df: intra-month MTD snapshots (period, date, broker, revenue_usd)
    brokers: list of broker names to ensure all appear in output
    """
    # Sum all completed months per broker
    monthly_totals = (
        monthly_df.groupby("broker")["revenue_usd"].sum()
        if not monthly_df.empty
        else pd.Series(dtype=float)
    )

    # Latest daily snapshot per broker for current month
    if not daily_df.empty:
        latest_daily = (
            daily_df.sort_values("date")
            .groupby("broker")
            .last()["revenue_usd"]
        )
    else:
        latest_daily = pd.Series(dtype=float)

    # Build result for all brokers
    result = pd.DataFrame({"broker": brokers})
    result["monthly_revenue"] = result["broker"].map(monthly_totals).fillna(0)
    result["current_month_mtd"] = result["broker"].map(latest_daily).fillna(0)
    result["actual_revenue"] = result["monthly_revenue"] + result["current_month_mtd"]
    return result


def compute_projected_revenue(
    actual_revenue_df: pd.DataFrame,
    period_start: date,
    period_end: date,
    as_of_date: date,
) -> pd.DataFrame:
    """Run-rate projection based on business days elapsed vs total."""
    total_biz_days = int(np.busday_count(period_start, period_end))
    elapsed_biz_days = int(np.busday_count(period_start, as_of_date))

    df = actual_revenue_df.copy()

    if elapsed_biz_days <= 0:
        df["projected_revenue"] = 0.0
        df["run_rate_daily"] = 0.0
        return df

    run_rate_multiplier = total_biz_days / elapsed_biz_days
    df["projected_revenue"] = df["actual_revenue"] * run_rate_multiplier
    df["run_rate_daily"] = df["actual_revenue"] / elapsed_biz_days
    return df


def compute_bonus_pool(total_revenue: float, total_cost: float, config: dict) -> dict:
    """Calculate bonus pool using the desk formula.

    Returns dict with all intermediate values for display.
    """
    promo_pct = config.get("promo_pct", 0.01)
    desk_split = config.get("desk_split", 0.55)
    mgmt_split = config.get("mgmt_split", 0.45)
    kelly_override_pct = config.get("kelly_override_pct", 0.05)

    promo = total_revenue * promo_pct
    net_revenue = total_revenue - promo
    mgmt_share = net_revenue * mgmt_split
    desk_share = net_revenue * desk_split
    bonus_pool_max = max(desk_share - total_cost, 0)
    kelly_override = bonus_pool_max * kelly_override_pct
    distributable_pool = bonus_pool_max - kelly_override

    return {
        "total_revenue": total_revenue,
        "promo": promo,
        "net_revenue": net_revenue,
        "mgmt_share": mgmt_share,
        "desk_share": desk_share,
        "total_cost": total_cost,
        "bonus_pool_max": bonus_pool_max,
        "kelly_override": kelly_override,
        "distributable_pool": distributable_pool,
        "rtc_ratio": net_revenue / total_cost if total_cost > 0 else 0,
    }


def compute_broker_bonuses(
    broker_costs_df: pd.DataFrame,
    revenue_df: pd.DataFrame,
    distributable_pool: float,
    revenue_col: str = "actual_revenue",
) -> pd.DataFrame:
    """Calculate per-broker bonus allocation and payout ratio."""
    df = broker_costs_df[["broker", "cost_usd"]].merge(
        revenue_df[["broker", revenue_col]], on="broker", how="left"
    )
    df[revenue_col] = df[revenue_col].fillna(0)

    total_rev = df[revenue_col].sum()
    if total_rev > 0:
        df["revenue_share"] = df[revenue_col] / total_rev
    else:
        df["revenue_share"] = 0.0

    df["formula_bonus"] = df["revenue_share"] * distributable_pool

    df["payout_ratio"] = None
    mask = df[revenue_col] > 0
    df.loc[mask, "payout_ratio"] = (
        (df.loc[mask, "cost_usd"] + df.loc[mask, "formula_bonus"])
        / df.loc[mask, revenue_col]
    )

    return df


def compute_all(
    brokers_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    config: dict,
    as_of_date: date | None = None,
) -> dict:
    """Orchestrate all calculations. Returns dict of DataFrames and summaries."""
    if as_of_date is None:
        as_of_date = date.today()

    usd_sgd = config.get("usd_sgd_rate", 1.29)
    period_start = config["period_start"]
    period_end = config["period_end"]

    # Costs
    costs_df = compute_broker_costs(brokers_df, usd_sgd)
    brokers = costs_df["broker"].tolist()
    total_cost = costs_df["cost_usd"].sum()

    # Revenue
    actual_rev = compute_actual_revenue(monthly_df, daily_df, brokers)
    projected_rev = compute_projected_revenue(
        actual_rev, period_start, period_end, as_of_date
    )

    # Bonus pool — actual
    total_actual_rev = actual_rev["actual_revenue"].sum()
    actual_pool = compute_bonus_pool(total_actual_rev, total_cost, config)

    # Bonus pool — projected
    total_projected_rev = projected_rev["projected_revenue"].sum()
    projected_pool = compute_bonus_pool(total_projected_rev, total_cost, config)

    # Per-broker bonuses (projected)
    broker_bonuses = compute_broker_bonuses(
        costs_df, projected_rev, projected_pool["distributable_pool"],
        revenue_col="projected_revenue",
    )

    # Merge everything into one display table
    display = costs_df[["broker", "te_sgd", "total_cost_sgd", "cost_usd"]].copy()
    display = display.merge(
        actual_rev[["broker", "actual_revenue"]], on="broker"
    )
    display = display.merge(
        projected_rev[["broker", "projected_revenue", "run_rate_daily"]], on="broker"
    )
    display = display.merge(
        broker_bonuses[["broker", "revenue_share", "formula_bonus", "payout_ratio"]],
        on="broker",
    )

    return {
        "display": display,
        "costs_df": costs_df,
        "actual_revenue": actual_rev,
        "projected_revenue": projected_rev,
        "actual_pool": actual_pool,
        "projected_pool": projected_pool,
        "broker_bonuses": broker_bonuses,
        "total_cost": total_cost,
        "as_of_date": as_of_date,
    }
