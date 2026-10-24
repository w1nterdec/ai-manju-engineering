from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from manju.adapters import load_config
from manju.costs import CostLedger, BudgetExceeded, estimate, money, price
import test_execution as execution_fixture


class MoneyTests(unittest.TestCase):
    def test_invalid_amounts(self):
        for value in (None, True, "NaN", "Infinity", "-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money(value)

    def test_explicit_credit_conversion_and_provenance(self):
        config = load_config()
        config["pricing"]["rates"]["default"] = {"unit": "credit", "per": "second", "amount": "3", "credit_source": "demo-pool"}
        config["pricing"]["conversions"]["credit:demo-pool"] = {"to_internal": "0.02", "as_of": "2026-10-24", "source_url": "https://example.invalid/conversion", "example": True}
        quote = price(config, {"kind": "video", "parameters": {"duration_ms": 2500}}, {"provider": "mock", "model": "mock-video"})
        self.assertEqual(Decimal(quote["amount"]), Decimal("0.15"))
        self.assertEqual(quote["source"], "demo-pool")
        config["pricing"]["conversions"].clear()
        with self.assertRaises(ValueError):
            price(config, {"kind": "video", "parameters": {}}, {"provider": "mock", "model": "mock-video"})


class BudgetTests(unittest.TestCase):
    setUp = execution_fixture.ExecutionTests.setUp
    def test_zero_budget_denies_before_dispatch(self):
        self.config["budgets"]["project"] = "0"
        rows = self.engine.run(self.plan, auto_review_mock=True)["tasks"]
        self.assertTrue(any("预算" in (row["error"] or "") for row in rows.values()))
        self.assertEqual(len(list((self.engine.root / "artifacts").glob("*.json"))), 0)

    def test_retry_cost_and_resume_reconcile_exactly(self):
        self.config["simulation"] = {"fail_first": {"tts:L001": 1}}
        self.engine.run(self.plan, auto_review_mock=True)
        report = self.engine.costs.report()
        billable = sum(1 for task in self.plan["tasks"] if task["kind"] != "human_review") + 1
        self.assertEqual(Decimal(report["totals"]["DEMO"]["actual"]), Decimal("0.01") * billable)
        self.assertEqual(Decimal(report["totals"]["DEMO"]["reserved"]), 0)
        self.engine.run(self.plan, auto_review_mock=True)
        self.assertEqual(self.engine.costs.report()["totals"], report["totals"])

    def test_shared_project_cap_covers_other_runs(self):
        task = self.plan["tasks"][0]
        self.config["budgets"]["project"] = "0.01"
        first = self.engine.costs.reserve("run-a", self.plan, task, 1)
        with self.assertRaises(BudgetExceeded):
            self.engine.costs.reserve("run-b", self.plan, task, 1)
        self.assertEqual(self.engine.costs.reserve("run-a", self.plan, task, 1), first)

    def test_each_scope_cap_is_enforced(self):
        task = next(task for task in self.plan["tasks"] if task["shot_id"])
        for scope in ("project", "episode", "shot", "batch"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                config = load_config()
                config["budgets"][scope] = "0"
                ledger = CostLedger(Path(directory) / "cost.sqlite3", config)
                try:
                    with self.assertRaises(BudgetExceeded):
                        ledger.reserve("test", self.plan, task, 1)
                finally:
                    ledger.close()
