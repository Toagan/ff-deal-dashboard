"""Entry point: read HubSpot, write the aggregate-only site/data.json."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import aggregate, config, hubspot, normalize

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "site" / "data.json"
logger = logging.getLogger("deal-dashboard")


def read_token() -> str:
    token = os.environ.get(config.TOKEN_ENV_VAR) or os.environ.get(
        config.FALLBACK_TOKEN_ENV_VAR
    )
    if not token:
        raise SystemExit(
            f"Missing HubSpot token: set the {config.TOKEN_ENV_VAR} environment variable."
        )
    return token


def stages_by_pipeline(stage_index: dict) -> dict:
    grouped: dict = {config.SALES_PIPELINE_ID: [], config.CS_PIPELINE_ID: []}
    for (pipeline_id, _stage_id), stage in stage_index.items():
        if pipeline_id in grouped:
            grouped[pipeline_id] = [*grouped[pipeline_id], stage]
    return {
        pipeline_id: sorted(stages, key=lambda stage: stage["order"])
        for pipeline_id, stages in grouped.items()
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    token = read_token()
    try:
        stage_index = normalize.build_stage_index(hubspot.fetch_pipelines(token))
        owner_index = normalize.build_owner_index(hubspot.fetch_owners(token))
        raw_deals = hubspot.fetch_deals(token)
    except hubspot.HubSpotError as error:
        logger.error("Sync failed: %s", error)
        return 1
    deals, skipped = normalize.normalize_deals(raw_deals, stage_index, owner_index)
    if not deals:
        logger.error("Sync failed: HubSpot returned no usable deals.")
        return 1
    payload = aggregate.build_payload(
        deals, stages_by_pipeline(stage_index), datetime.now(timezone.utc)
    )
    OUTPUT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    logger.info(
        "Wrote %s from %d deals (%d skipped: no known stage).",
        OUTPUT_PATH.name, len(deals), skipped,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
