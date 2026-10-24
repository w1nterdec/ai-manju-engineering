from pathlib import Path
import tempfile
import unittest

from manju.assets import AssetStore, identity_report, lineage
from manju.adapters import load_config
from manju.io import read_json, write_json
from manju.review import gate, review_template
import test_execution as execution_fixture


class AssetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "fixture.txt"
        self.source.write_text("Mock asset, not real identity or license evidence", encoding="utf-8")
        self.store = AssetStore(self.root / "assets")
        self.metadata = {"source": "synthetic unit fixture", "mock": True, "license": {"scope": ["commercial_delivery"], "expires": None, "restrictions": []}}

    def test_content_addressed_dedup_and_immutable_approval(self):
        first = self.store.add(self.source, "identity", self.metadata, self.source)
        second = self.store.add(self.source, "identity", self.metadata, self.source)
        self.assertEqual(first["asset_id"], second["asset_id"])
        approved = self.store.approve(first["asset_id"], "UNIT_FIXTURE", "simulation only")
        self.assertNotEqual(approved["asset_id"], first["asset_id"])
        self.assertIsNone(self.store.get(first["asset_id"])["approval"])
        self.assertTrue(self.store.check(approved["asset_id"], allow_mock=True)["passed"])
        self.assertFalse(self.store.check(approved["asset_id"])["passed"])

    def test_missing_proof_expiry_scope_and_tamper(self):
        self.metadata["license"]["expires"] = "2000-01-01"
        record = self.store.add(self.source, "voice", self.metadata)
        approved = self.store.approve(record["asset_id"], "UNIT_FIXTURE", "simulation")
        result = self.store.check(approved["asset_id"], allow_mock=True)
        self.assertTrue(any("过期" in item for item in result["problems"]))
        self.assertTrue(any("凭据" in item for item in result["problems"]))
        (self.store.root / "blobs" / record["content_sha256"]).write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.store.get(record["asset_id"])

    def test_no_implicit_legal_authorization(self):
        record = self.store.add(self.source, "voice", {"source": "fixture"})
        self.assertFalse(self.store.check(record["asset_id"])["passed"])


class LineageTests(unittest.TestCase):
    setUp = execution_fixture.ExecutionTests.setUp

    def test_lineage_and_missing_rights_gate(self):
        self.engine.run(self.plan, auto_review_mock=True)
        result = lineage(self.bundle, self.engine.root, "review:S001")
        self.assertIn("identity:C001", result["tasks"])
        self.assertIn("tts:L001", result["tasks"])
        review = self.root / "review.json"
        write_json(review, review_template(self.bundle))
        config_path = self.root / "config.json"
        write_json(config_path, self.config)
        self.assertTrue(any(item.code == "R001" for item in gate(self.bundle, review, production_config=config_path)))

    def test_identity_block_policy(self):
        from manju.planning import make_plan
        self.config["identity_policy"] = "block"
        with self.assertRaises(ValueError):
            make_plan(self.bundle, self.config)
