# Deal dashboard

A public, totals-only view of the HubSpot deal pipelines, rebuilt every hour by
GitHub Actions and served by GitHub Pages.

## What is published

Only aggregates: counts and EUR sums per stage, month, owner first name and
segment. No deal name, company name, deal ID or next-step text ever leaves
HubSpot: `sync/normalize.py` drops them before anything is aggregated, and a
test guards that. `site/data.json` is built in the workflow and is not
committed.

A view with a single deal in it shows that deal's amount, without a name.

## How it works

1. `sync/hubspot.py` reads pipelines, owners and all deals (read-only calls).
2. `sync/normalize.py` reduces each deal to an anonymous row.
3. `sync/aggregate.py` computes the totals for all deals and for each owner and segment.
4. `site/` is a static page that renders `data.json`.

## Definitions

- Open pipeline: open Sales Pipeline deals, leaving out Lead and Future Opportunity.
- Weighted: amount times the stage probability set in HubSpot.
- Live ARR: open renewal deals in the Customer Success pipeline.
- Win rate: won / (won + lost), Sales Pipeline deals with an amount only.
- Sales cycle: create date to close date of deals won in the last 12 months.

## Setup

The workflow needs one repository secret, `HUBSPOT_TOKEN`: a HubSpot private
app token with read-only scopes `crm.objects.deals.read`,
`crm.objects.owners.read` and `crm.schemas.deals.read`.

    gh secret set HUBSPOT_TOKEN

## Run locally

    HUBSPOT_TOKEN=... python3 -m sync.build
    python3 -m http.server --directory site 8000
    python3 -m unittest

GitHub pauses scheduled workflows after 60 days without a commit; re-enable
the workflow in the Actions tab if the sync time on the page stops moving.
