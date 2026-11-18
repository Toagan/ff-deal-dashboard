"""Pure aggregation: anonymous deal rows in, publishable totals out.

Definitions used throughout:
- Open pipeline: open Sales Pipeline deals outside the watchlist stages.
- Weighted: amount times the stage's close probability set in HubSpot.
- Live ARR: open renewal deals in the Customer Success pipeline.
- Win rate: won / (won + lost) among Sales Pipeline deals with an amount.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median

from . import config


def month_key(moment: datetime) -> str:
    return f"{moment.year:04d}-{moment.month:02d}"


def shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def month_range(now: datetime, start_offset: int, count: int) -> list[str]:
    months = [shift_month(now.year, now.month, start_offset + i) for i in range(count)]
    return [f"{year:04d}-{month:02d}" for year, month in months]


def quarter_start(now: datetime) -> datetime:
    first_month = 3 * ((now.month - 1) // 3) + 1
    return now.replace(month=first_month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _sum_amount(deals: list[dict]) -> float:
    return round(sum(deal["amount"] for deal in deals), 2)


def _sum_weighted(deals: list[dict]) -> float:
    return round(sum(deal["amount"] * deal["probability"] for deal in deals), 2)


def _is_sales(deal: dict) -> bool:
    return deal["pipeline"] == config.SALES_PIPELINE_ID


def _is_cs(deal: dict) -> bool:
    return deal["pipeline"] == config.CS_PIPELINE_ID


def _is_active_sales(deal: dict) -> bool:
    return (
        _is_sales(deal)
        and not deal["is_closed"]
        and deal["stage"] not in config.WATCHLIST_STAGE_LABELS
    )


def _closed_between(deal: dict, start: datetime, end: datetime) -> bool:
    return deal["close_date"] is not None and start <= deal["close_date"] <= end


def _median_days(spans: list[float]) -> int | None:
    return round(median(spans)) if spans else None


def stage_rows(deals: list[dict], stages: list[dict], now: datetime) -> list[dict]:
    rows = []
    for stage in stages:
        in_stage = [deal for deal in deals if deal["stage"] == stage["label"]]
        ages = [
            (now - deal["entered_stage"]).total_seconds() / 86400
            for deal in in_stage
            if deal["entered_stage"] is not None
        ]
        rows.append(
            {
                "label": stage["label"],
                "probability": stage["probability"],
                "is_watchlist": stage["label"] in config.WATCHLIST_STAGE_LABELS,
                "count": len(in_stage),
                "amount": _sum_amount(in_stage),
                "weighted": _sum_weighted(in_stage),
                "median_days_in_stage": _median_days(ages),
            }
        )
    return rows


def win_rate(sales: list[dict], now: datetime, window_days: int) -> float | None:
    start = now - timedelta(days=window_days)
    decided = [
        deal
        for deal in sales
        if deal["is_closed"] and deal["amount"] > 0 and _closed_between(deal, start, now)
    ]
    if not decided:
        return None
    return round(sum(1 for deal in decided if deal["is_won"]) / len(decided), 4)


def monthly_rows(sales: list[dict], now: datetime) -> list[dict]:
    months = month_range(now, -(config.TRAILING_MONTHS - 1), config.TRAILING_MONTHS)
    rows = {
        month: {"month": month, "created": 0, "won": 0, "won_amount": 0.0, "lost": 0}
        for month in months
    }
    for deal in sales:
        created = deal["created"]
        if created is not None and month_key(created) in rows:
            row = rows[month_key(created)]
            rows[month_key(created)] = {**row, "created": row["created"] + 1}
        closed = deal["close_date"]
        if not deal["is_closed"] or closed is None or month_key(closed) not in rows:
            continue
        row = rows[month_key(closed)]
        if deal["is_won"]:
            rows[month_key(closed)] = {
                **row,
                "won": row["won"] + 1,
                "won_amount": round(row["won_amount"] + deal["amount"], 2),
            }
        else:
            rows[month_key(closed)] = {**row, "lost": row["lost"] + 1}
    return [rows[month] for month in months]


def forecast_rows(active: list[dict], now: datetime) -> list[dict]:
    months = month_range(now, 0, config.FORECAST_MONTHS)
    rows = []
    for month in months:
        due = [
            deal
            for deal in active
            if deal["close_date"] is not None and month_key(deal["close_date"]) == month
        ]
        rows.append(
            {
                "month": month,
                "count": len(due),
                "amount": _sum_amount(due),
                "weighted": _sum_weighted(due),
            }
        )
    return rows


def breakdown_rows(deals: list[dict], field: str, now: datetime) -> list[dict]:
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = []
    for name in sorted({deal[field] for deal in deals}):
        mine = [deal for deal in deals if deal[field] == name]
        active = [deal for deal in mine if _is_active_sales(deal)]
        won = [
            deal
            for deal in mine
            if _is_sales(deal) and deal["is_won"] and _closed_between(deal, year_start, now)
        ]
        if not active and not won:
            continue
        rows.append(
            {
                "name": name,
                "open_count": len(active),
                "open_amount": _sum_amount(active),
                "weighted": _sum_weighted(active),
                "won_ytd_count": len(won),
                "won_ytd_amount": _sum_amount(won),
            }
        )
    return sorted(rows, key=lambda row: row["open_amount"], reverse=True)


def hygiene(active: list[dict], now: datetime) -> dict:
    stale_before = now - timedelta(days=config.STALE_AFTER_DAYS)
    late = [deal for deal in active if deal["stage"] in config.LATE_STAGE_LABELS]
    return {
        "late_stage_without_next_step": sum(1 for d in late if not d["has_next_step"]),
        "late_stage_count": len(late),
        "close_date_overdue": sum(
            1 for d in active if d["close_date"] is not None and d["close_date"] < now
        ),
        "no_activity_30_days": sum(
            1
            for d in active
            if d["last_activity"] is None or d["last_activity"] < stale_before
        ),
        "without_amount": sum(1 for d in active if d["amount"] <= 0),
        "without_owner": sum(
            1 for d in active if d["owner"] == config.UNASSIGNED_OWNER_LABEL
        ),
        "active_count": len(active),
    }


def kpis(deals: list[dict], now: datetime) -> dict:
    sales = [deal for deal in deals if _is_sales(deal)]
    active = [deal for deal in sales if _is_active_sales(deal)]
    late = [deal for deal in active if deal["stage"] in config.LATE_STAGE_LABELS]
    won = [deal for deal in sales if deal["is_won"]]
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    long_start = now - timedelta(days=config.WIN_RATE_LONG_WINDOW_DAYS)
    won_quarter = [d for d in won if _closed_between(d, quarter_start(now), now)]
    won_year = [d for d in won if _closed_between(d, year_start, now)]
    won_trailing = [
        d for d in won if d["amount"] > 0 and _closed_between(d, long_start, now)
    ]
    cycles = [
        (d["close_date"] - d["created"]).total_seconds() / 86400
        for d in won_trailing
        if d["created"] is not None and d["close_date"] >= d["created"]
    ]
    renewals = [
        d
        for d in deals
        if _is_cs(d) and not d["is_closed"] and d["deal_type"] == config.RENEWAL_DEAL_TYPE
    ]
    return {
        "open_pipeline": _sum_amount(active),
        "open_count": len(active),
        "weighted_pipeline": _sum_weighted(active),
        "late_stage_amount": _sum_amount(late),
        "late_stage_count": len(late),
        "live_arr": _sum_amount(renewals),
        "live_contracts": len(renewals),
        "won_qtd_amount": _sum_amount(won_quarter),
        "won_qtd_count": len(won_quarter),
        "won_ytd_amount": _sum_amount(won_year),
        "won_ytd_count": len(won_year),
        "win_rate_90d": win_rate(sales, now, config.WIN_RATE_SHORT_WINDOW_DAYS),
        "win_rate_12m": win_rate(sales, now, config.WIN_RATE_LONG_WINDOW_DAYS),
        "avg_won_amount_12m": (
            round(_sum_amount(won_trailing) / len(won_trailing), 2)
            if won_trailing
            else None
        ),
        "median_cycle_days_12m": _median_days(cycles),
    }


def build_view(deals: list[dict], stages: dict, now: datetime) -> dict:
    """All metrics for one slice of deals. `stages` maps pipeline ID to stage list."""
    sales = [deal for deal in deals if _is_sales(deal)]
    active = [deal for deal in sales if _is_active_sales(deal)]
    open_sales_stages = [s for s in stages[config.SALES_PIPELINE_ID] if not s["is_closed"]]
    cs_deals = [deal for deal in deals if _is_cs(deal)]
    return {
        "kpis": kpis(deals, now),
        "sales_stages": stage_rows(sales, open_sales_stages, now),
        "cs_stages": stage_rows(cs_deals, stages[config.CS_PIPELINE_ID], now),
        "monthly": monthly_rows(sales, now),
        "forecast": forecast_rows(active, now),
        "hygiene": hygiene(active, now),
    }


def build_payload(deals: list[dict], stages: dict, now: datetime) -> dict:
    """The full published document: one view for everything, one per owner and segment."""
    views = [{"key": "all", "group": "All", "label": "All deals",
              "data": build_view(deals, stages, now)}]
    for field, group in (("owner", "Owner"), ("segment", "Segment")):
        for name in sorted({deal[field] for deal in deals}):
            subset = [deal for deal in deals if deal[field] == name]
            views.append(
                {
                    "key": f"{field}:{name}",
                    "group": group,
                    "label": name,
                    "data": build_view(subset, stages, now),
                }
            )
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "currency": "EUR",
        "deal_count": len(deals),
        "views": views,
        "owners": breakdown_rows(deals, "owner", now),
        "segments": breakdown_rows(deals, "segment", now),
    }
