from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from manju.business import add_revision, batch, export_shoppable, load_profile, new_project, unit_cost
from manju.build import compile_episode
from manju.io import read_json, write_json
from manju.project import load_episode
from manju.validation import validate

ROOT = Path(__file__).resolve().parents[1]


class BusinessTests(unittest.TestCase):
    def test_all_four_profiles_create_valid_independent_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("series_drama", "ad_batch", "client_service", "shoppable_export"):
                output = Path(directory) / name
                new_project(name, output)
                data, _ = load_episode(output / "episode.json")
                self.assertFalse([finding for finding in validate(data) if finding.level == "error"])
                compile_episode(output / "episode.json", output / "bundle")
                self.assertEqual(read_json(output / "project.json")["business_profile"], name)
                with self.assertRaises(ValueError):
                    new_project(name, output)

    def test_parameterized_cost_models_are_reproducible(self):
        parameters = read_json(ROOT / "examples/business/cost-inputs.json")
        for name in ("series_drama", "ad_batch", "client_service", "shoppable_export"):
            first = unit_cost(load_profile(name), parameters)
            self.assertEqual(first, unit_cost(load_profile(name), parameters))
        client = unit_cost(load_profile("client_service"), parameters)
        self.assertEqual(Decimal(client["calculated_quote"]), Decimal("19.25"))
        parameters["margin"] = "1"
        with self.assertRaises(ValueError):
            unit_cost(load_profile("client_service"), parameters)

    def test_batch_variants_failure_isolation_and_shared_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            new_project("ad_batch", root / "project")
            items = {"items": [{"sku": "DEMO-A", "product_name": "例甲", "selling_point": "输入卖点甲", "hooks": ["开头甲", "开头乙"]}, {"sku": "BROKEN"}, {"sku": "DEMO-B", "product_name": "例乙", "selling_point": "输入卖点乙", "hooks": ["开头丙"]}]}
            write_json(root / "items.json", items)
            result = batch(root / "project", root / "items.json", root / "batch", execute=True, auto_review_mock=True)
            self.assertEqual(sum(job["status"] == "succeeded" for job in result["jobs"]), 3)
            self.assertEqual(sum(job["status"] == "failed" for job in result["jobs"]), 1)
            accounts = {read_json(root / "batch" / job["directory"] / "production.json")["budget_account"] for job in result["jobs"] if "directory" in job}
            self.assertEqual(len(accounts), 1)
            variants = [read_json(root / "batch" / job["directory"] / "variant.json") for job in result["jobs"] if "directory" in job]
            self.assertEqual(len({variant["variant_id"] for variant in variants}), 3)

    def test_csv_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            new_project("ad_batch", root / "project")
            result = batch(root / "project", ROOT / "examples/business/products.csv", root / "batch")
            self.assertEqual(len(result["jobs"]), 2)
            self.assertTrue(all(job["status"] == "planned" for job in result["jobs"]))

    def test_shoppable_is_metadata_only_and_validates_times(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            export_shoppable(ROOT / "examples/business/shoppable.json", path)
            data = read_json(path)
            data["items"][0]["end_ms"] = data["duration_ms"] + 1
            write_json(Path(directory) / "bad.json", data)
            with self.assertRaises(ValueError):
                export_shoppable(Path(directory) / "bad.json", Path(directory) / "output.json")

    def test_revision_rounds_append(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "client"
            new_project("client_service", project)
            add_revision(project, "UNIT_FIXTURE", "first simulated request")
            result = add_revision(project, "UNIT_FIXTURE", "second simulated request")
            self.assertEqual([event["round"] for event in result["events"]], [1, 2])
