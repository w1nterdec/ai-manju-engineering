import json
from pathlib import Path
import tempfile
import unittest

from manju.adapters import load_config
from manju.build import compile_episode
from manju.execution import Engine
from manju.io import read_json, write_json
from manju.planning import make_plan

SOURCE = Path(__file__).resolve().parents[1] / "examples/midnight_letter/episode.json"


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / "bundle"
        compile_episode(SOURCE, self.bundle)
        self.config = load_config()
        self.plan = make_plan(self.bundle, self.config)
        self.engine = Engine(self.root / "run", self.config)
        self.addCleanup(self.engine.close)

    def test_complete_mock_and_resume_skip_success(self):
        result = self.engine.run(self.plan, auto_review_mock=True)
        self.assertTrue(all(t["state"] == "succeeded" for t in result["tasks"].values()))
        attempts = {k: t["attempts"] for k, t in result["tasks"].items()}
        resumed = self.engine.run(self.plan, auto_review_mock=True)
        self.assertEqual(attempts, {k: t["attempts"] for k, t in resumed["tasks"].items()})

    def test_human_review_default_blocks_edit(self):
        rows = self.engine.run(self.plan)["tasks"]
        self.assertEqual(rows["review:S001"]["state"], "needs_review")
        self.assertEqual(rows["edit:episode"]["state"], "pending")

    def test_interruption_recovery_skips_success(self):
        rows = self.engine.run(self.plan, stop_after=1)["tasks"]
        completed = {k: r["attempts"] for k, r in rows.items() if r["state"] == "succeeded"}
        self.assertTrue(completed)
        rows = self.engine.run(self.plan, auto_review_mock=True)["tasks"]
        self.assertTrue(all(r["state"] == "succeeded" for r in rows.values()))
        for key, attempts in completed.items():
            self.assertEqual(rows[key]["attempts"], attempts)

    def test_crash_after_output_before_commit(self):
        self.engine.sync(self.plan)
        task = self.plan["tasks"][0]
        output = self.engine._generate(task, 1)
        self.engine.db.execute("UPDATE tasks SET state='running',attempts=1 WHERE id=?", (task["id"],))
        self.engine.db.commit()
        self.engine.run(self.plan, stop_after=1)
        self.assertEqual(json.loads(self.engine.state()[task["id"]]["result"])["sha256"], output["sha256"])
        self.assertEqual(len(list((self.engine.root / "artifacts").glob(f"{task['key']}.json"))), 1)

    def test_retries_are_bounded(self):
        self.config["simulation"] = {"fail_first": {"tts:L001": 10}}
        row = self.engine.run(self.plan, auto_review_mock=True)["tasks"]["tts:L001"]
        self.assertEqual((row["state"], row["attempts"]), ("failed", 2))

    def test_local_change_stales_only_downstream(self):
        self.engine.run(self.plan, auto_review_mock=True)
        source = read_json(SOURCE)
        source["shots"][0]["emotion"] += " 更加警觉。"
        path = self.root / "changed.json"
        write_json(path, source)
        bundle = self.root / "changed"
        compile_episode(path, bundle)
        self.engine.sync(make_plan(bundle, self.config))
        stale = {k for k, r in self.engine.state().items() if r["state"] == "stale"}
        self.assertEqual(stale, {"image:S001", "video:S001", "review:S001", "edit:episode"})

    def test_cancel_prevents_dispatch(self):
        write_json(self.engine.root / "cancel.json", {"cancel": True})
        rows = self.engine.run(self.plan)["tasks"]
        self.assertTrue(all(r["attempts"] == 0 for r in rows.values()))

    def test_tampered_success_is_rejected(self):
        row = self.engine.run(self.plan, auto_review_mock=True)["tasks"]["tts:L001"]
        path = self.engine.root / "artifacts" / json.loads(row["result"])["path"]
        path.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.engine.run(self.plan)
