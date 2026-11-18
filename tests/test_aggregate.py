"""TEST DATA ONLY: every deal below is fake."""

import json
import unittest
from datetime import datetime, timedelta, timezone

from sync import aggregate, config, normalize

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
SALES = config.SALES_PIPELINE_ID
CS = config.CS_PIPELINE_ID

STAGES = {
    SALES: [
        {"label": "Lead", "probability": 0.1, "order": 0, "is_closed": False},
        {"label": "Discovery", "probability": 0.3, "order": 1, "is_closed": False},
        {"label": "Contract Sent", "probability": 0.8, "order": 2, "is_closed": False},
        {"label": "Closed Won", "probability": 1.0, "order": 3, "is_closed": True},
        {"label": "Closed Lost", "probability": 0.0, "order": 4, "is_closed": True},
    ],
    CS: [{"label": "Active Contract", "probability": 0.5, "order": 0, "is_closed": False}],
}


def deal(stage="Discovery", amount=100.0, pipeline=SALES, **overrides):
    probability = {s["label"]: s for s in STAGES[pipeline]}[stage]["probability"]
    is_closed = stage.startswith("Closed")
    base = {
        "pipeline": pipeline, "stage": stage, "probability": probability,
        "is_closed": is_closed, "is_won": stage == "Closed Won", "amount": amount,
        "created": NOW - timedelta(days=60), "close_date": NOW + timedelta(days=20),
        "entered_stage": NOW - timedelta(days=10), "last_activity": NOW - timedelta(days=2),
        "has_next_step": True, "owner": "Ada", "segment": "Fintech", "deal_type": "",
    }
    return {**base, **overrides}


class KpiTests(unittest.TestCase):
    def test_open_pipeline_excludes_watchlist_and_closed_deals(self):
        deals = [deal("Lead", 999), deal("Discovery", 100), deal("Contract Sent", 200),
                 deal("Closed Won", 500, close_date=NOW - timedelta(days=5))]
        result = aggregate.kpis(deals, NOW)
        self.assertEqual(result["open_pipeline"], 300)
        self.assertEqual(result["open_count"], 2)
        self.assertEqual(result["weighted_pipeline"], 190)
        self.assertEqual(result["late_stage_amount"], 200)

    def test_live_arr_counts_only_open_renewals_in_customer_success(self):
        deals = [deal("Active Contract", 400, CS, deal_type="renewal"),
                 deal("Active Contract", 50, CS, deal_type="upsell")]
        self.assertEqual(aggregate.kpis(deals, NOW)["live_arr"], 400)

    def test_win_rate_ignores_zero_amount_and_old_deals(self):
        recent = NOW - timedelta(days=10)
        deals = [deal("Closed Won", 100, close_date=recent),
                 deal("Closed Lost", 100, close_date=recent),
                 deal("Closed Lost", 0, close_date=recent),
                 deal("Closed Lost", 100, close_date=NOW - timedelta(days=200))]
        self.assertEqual(aggregate.win_rate(deals, NOW, 90), 0.5)
        self.assertIsNone(aggregate.win_rate([], NOW, 90))

    def test_median_cycle_uses_won_deals(self):
        won = deal("Closed Won", 100, created=NOW - timedelta(days=50),
                   close_date=NOW - timedelta(days=10))
        self.assertEqual(aggregate.kpis([won], NOW)["median_cycle_days_12m"], 40)


class SeriesTests(unittest.TestCase):
    def test_monthly_rows_cover_twelve_months_ending_now(self):
        rows = aggregate.monthly_rows(
            [deal("Closed Won", 70, close_date=NOW - timedelta(days=1))], NOW)
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0]["month"], "2025-12")
        self.assertEqual(rows[-1], {"month": "2026-11", "created": 0, "won": 1,
                                    "won_amount": 70, "lost": 0})

    def test_forecast_buckets_open_deals_by_close_month(self):
        rows = aggregate.forecast_rows(
            [deal("Contract Sent", 100, close_date=datetime(2027, 1, 5, tzinfo=timezone.utc))],
            NOW)
        self.assertEqual([r["month"] for r in rows][:3], ["2026-11", "2026-12", "2027-01"])
        self.assertEqual(rows[2]["weighted"], 80)

    def test_hygiene_flags_late_stage_gaps(self):
        deals = [deal("Contract Sent", 0, has_next_step=False, last_activity=None,
                      close_date=NOW - timedelta(days=1), owner=config.UNASSIGNED_OWNER_LABEL)]
        result = aggregate.hygiene(deals, NOW)
        for key in ("late_stage_without_next_step", "close_date_overdue",
                    "no_activity_30_days", "without_amount", "without_owner"):
            self.assertEqual(result[key], 1, key)


class PayloadTests(unittest.TestCase):
    def test_payload_has_views_per_owner_and_segment(self):
        deals = [deal(owner="Ada"), deal(owner="Bo", segment="Universities")]
        payload = aggregate.build_payload(deals, STAGES, NOW)
        keys = [view["key"] for view in payload["views"]]
        self.assertEqual(keys, ["all", "owner:Ada", "owner:Bo",
                                "segment:Fintech", "segment:Universities"])
        json.dumps(payload)

    def test_normalized_deal_carries_no_identifying_fields(self):
        raw = {"id": "1", "properties": {
            "dealname": "FAKE Corp - TEST", "pipeline": SALES, "dealstage": "s1",
            "amount": "10", "hs_next_step": "call FAKE person", "hubspot_owner_id": "7"}}
        stage_index = {(SALES, "s1"): STAGES[SALES][1]}
        row = normalize.normalize_deal(raw, stage_index, {"7": "Ada"})
        self.assertNotIn("FAKE", json.dumps(row, default=str))
        self.assertEqual(row["owner"], "Ada")
        self.assertTrue(row["has_next_step"])

    def test_deal_with_unknown_stage_is_skipped(self):
        deals, skipped = normalize.normalize_deals(
            [{"properties": {"pipeline": "x", "dealstage": "y"}}], {}, {})
        self.assertEqual((deals, skipped), ([], 1))


if __name__ == "__main__":
    unittest.main()
