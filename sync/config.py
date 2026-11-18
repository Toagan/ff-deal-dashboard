"""Constants for the HubSpot deal dashboard sync.

Stages are referenced by LABEL, never by internal ID: the IDs in this portal
are misleading (the "Commercial Negotiation" stage has the ID "contractsent").
"""

API_BASE = "https://api.hubapi.com"
TOKEN_ENV_VAR = "HUBSPOT_TOKEN"
FALLBACK_TOKEN_ENV_VAR = "HUBSPOT_PRIVATE_APP_TOKEN"

SALES_PIPELINE_ID = "default"
CS_PIPELINE_ID = "4233782512"

# Placeholder target accounts and parked deals: shown, never counted as pipeline.
WATCHLIST_STAGE_LABELS = frozenset({"Lead", "Future Opportunity"})
LATE_STAGE_LABELS = frozenset({"Commercial Negotiation", "Contract Sent"})
RENEWAL_DEAL_TYPE = "renewal"

DEAL_PROPERTIES = (
    "pipeline",
    "dealstage",
    "amount",
    "amount_in_home_currency",
    "createdate",
    "closedate",
    "hubspot_owner_id",
    "hs_next_step",
    "notes_last_updated",
    "hs_v2_date_entered_current_stage",
    "fr_segment",
    "fr_revenue_type",
    "dealtype",
)

SEGMENT_LABELS = {
    "hedge_fund_asset_manager": "Hedge funds and asset managers",
    "fintech": "Fintech",
    "university": "Universities",
    "government": "Government",
}
UNSEGMENTED_LABEL = "No segment set"
UNASSIGNED_OWNER_LABEL = "Unassigned"

PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 4

TRAILING_MONTHS = 12
FORECAST_MONTHS = 6
STALE_AFTER_DAYS = 30
WIN_RATE_SHORT_WINDOW_DAYS = 90
WIN_RATE_LONG_WINDOW_DAYS = 365
