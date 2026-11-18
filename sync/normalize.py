"""Turn raw HubSpot records into small, anonymous deal rows.

A normalised deal deliberately carries NO deal name, company name, deal ID or
next-step text. Nothing that identifies a client can reach the published file.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import config


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_amount(properties: dict) -> float:
    for key in ("amount_in_home_currency", "amount"):
        raw = properties.get(key)
        if raw in (None, ""):
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return 0.0


def build_stage_index(pipelines: list[dict]) -> dict:
    """Map (pipeline_id, stage_id) to label, probability, order and closed flag."""
    index = {}
    for pipeline in pipelines:
        for stage in pipeline.get("stages", []):
            metadata = stage.get("metadata", {})
            index[(pipeline["id"], stage["id"])] = {
                "label": stage["label"],
                "probability": float(metadata.get("probability") or 0.0),
                "order": stage.get("displayOrder", 0),
                "is_closed": str(metadata.get("isClosed", "false")).lower() == "true",
            }
    return index


def build_owner_index(owners: list[dict]) -> dict:
    """Map owner ID to a first name only (the page is public)."""
    index = {}
    for owner in owners:
        first_name = (owner.get("firstName") or "").strip()
        index[str(owner["id"])] = first_name or config.UNASSIGNED_OWNER_LABEL
    return index


def normalize_deal(raw: dict, stage_index: dict, owner_index: dict) -> dict | None:
    properties = raw.get("properties", {})
    stage = stage_index.get((properties.get("pipeline"), properties.get("dealstage")))
    if stage is None:
        return None
    is_closed = stage["is_closed"]
    return {
        "pipeline": properties["pipeline"],
        "stage": stage["label"],
        "probability": stage["probability"],
        "is_closed": is_closed,
        "is_won": is_closed and stage["probability"] >= 1.0,
        "amount": parse_amount(properties),
        "created": parse_datetime(properties.get("createdate")),
        "close_date": parse_datetime(properties.get("closedate")),
        "entered_stage": parse_datetime(
            properties.get("hs_v2_date_entered_current_stage")
        ),
        "last_activity": parse_datetime(properties.get("notes_last_updated")),
        "has_next_step": bool((properties.get("hs_next_step") or "").strip()),
        "owner": owner_index.get(
            str(properties.get("hubspot_owner_id") or ""),
            config.UNASSIGNED_OWNER_LABEL,
        ),
        "segment": config.SEGMENT_LABELS.get(
            properties.get("fr_segment") or "", config.UNSEGMENTED_LABEL
        ),
        "deal_type": properties.get("dealtype") or "",
    }


def normalize_deals(raw_deals: list[dict], stage_index: dict, owner_index: dict):
    """Return (deals, skipped_count). Skipped deals have no known pipeline stage."""
    normalized = [normalize_deal(raw, stage_index, owner_index) for raw in raw_deals]
    deals = [deal for deal in normalized if deal is not None]
    return deals, len(normalized) - len(deals)
