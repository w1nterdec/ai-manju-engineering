from pathlib import Path
import unittest

from manju.delivery import handoff, package, verify_package
from manju.io import read_json, write_json
import test_execution as execution_fixture


class DeliveryTests(unittest.TestCase):
    setUp = execution_fixture.ExecutionTests.setUp

    def test_demo_bundle_is_portable_and_verifiable(self):
        self.engine.run(self.plan, auto_review_mock=True)
        output = self.root / "delivery"
        result = package(self.bundle, output, self.config, run=self.engine.root, demo=True)
        self.assertEqual(result["mode"], "demo")
        self.assertFalse(result["production_ready"])
        self.assertTrue(verify_package(output)["passed"])
        self.assertFalse((output / "costs.json").exists())
        self.assertIn("MOCK", (output / "report.html").read_text(encoding="utf-8"))

    def test_production_missing_records_is_blocked(self):
        with self.assertRaises(ValueError):
            package(self.bundle, self.root / "production", self.config)
        self.assertFalse((self.root / "production").exists())

    def test_modified_and_extra_files_fail_independent_verification(self):
        self.engine.run(self.plan, auto_review_mock=True)
        output = self.root / "delivery"
        package(self.bundle, output, self.config, run=self.engine.root, demo=True)
        (output / "extra.txt").write_text("injected", encoding="utf-8")
        self.assertFalse(verify_package(output)["passed"])
        (output / "extra.txt").unlink()
        (output / "report.html").write_text("changed", encoding="utf-8")
        self.assertFalse(verify_package(output)["passed"])

    def test_manifest_path_escape_is_rejected(self):
        self.engine.run(self.plan, auto_review_mock=True)
        output = self.root / "delivery"
        package(self.bundle, output, self.config, run=self.engine.root, demo=True)
        manifest = read_json(output / "package-manifest.json")
        manifest["files"]["../outside.txt"] = "0" * 64
        write_json(output / "package-manifest.json", manifest)
        with self.assertRaises(ValueError):
            verify_package(output)

    def test_partial_run_cannot_package_and_output_never_overwrites(self):
        self.engine.run(self.plan, stop_after=1)
        output = self.root / "delivery"
        with self.assertRaises(ValueError):
            package(self.bundle, output, self.config, run=self.engine.root, demo=True)
        self.engine.run(self.plan, auto_review_mock=True)
        package(self.bundle, output, self.config, run=self.engine.root, demo=True)
        with self.assertRaises(ValueError):
            package(self.bundle, output, self.config, run=self.engine.root, demo=True)

    def test_handoff_uses_explicit_planned_timing(self):
        result = handoff(self.bundle, self.root / "handoff")
        self.assertEqual(result["timing_basis"], "planned_preview")
        self.assertIn("S001", (self.root / "handoff/timeline.csv").read_text(encoding="utf-8"))
