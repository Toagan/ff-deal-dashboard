"""Read-only HubSpot client: pipelines, owners and all deals."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config


class HubSpotError(RuntimeError):
    """Raised when HubSpot cannot be read. Never contains the token."""


def _get(path: str, token: str, params: dict | None = None) -> dict:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    request = urllib.request.Request(
        f"{config.API_BASE}{path}{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    for attempt in range(config.MAX_RETRIES):
        try:
            with urllib.request.urlopen(
                request, timeout=config.REQUEST_TIMEOUT_SECONDS
            ) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            is_retryable = error.code == 429 or error.code >= 500
            if not is_retryable or attempt == config.MAX_RETRIES - 1:
                raise HubSpotError(
                    f"HubSpot returned HTTP {error.code} for {path}"
                ) from None
        except urllib.error.URLError as error:
            if attempt == config.MAX_RETRIES - 1:
                raise HubSpotError(
                    f"Could not reach HubSpot for {path}: {error.reason}"
                ) from None
        time.sleep(2**attempt)
    raise HubSpotError(f"Gave up on {path}")


def fetch_pipelines(token: str) -> list[dict]:
    return _get("/crm/v3/pipelines/deals", token)["results"]


def _fetch_paged(path: str, token: str, params: dict) -> list[dict]:
    results: list[dict] = []
    after = None
    while True:
        page_params = {**params, **({"after": after} if after else {})}
        page = _get(path, token, page_params)
        results = [*results, *page.get("results", [])]
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after:
            return results


def fetch_owners(token: str) -> list[dict]:
    return _fetch_paged("/crm/v3/owners", token, {"limit": config.PAGE_SIZE})


def fetch_deals(token: str) -> list[dict]:
    return _fetch_paged(
        "/crm/v3/objects/deals",
        token,
        {
            "limit": config.PAGE_SIZE,
            "properties": ",".join(config.DEAL_PROPERTIES),
        },
    )
