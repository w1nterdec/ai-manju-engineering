"""Offline regression tests. Byte fixtures are not generated media or quality evidence."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manju.build import compile_episode, timestamp
from manju.io import digest, read_json, write_json
from manju.project import load_episode, validate_series
from manju.providers import Capabilities
from manju.review import gate, review_template
from manju.validation import validate


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples/midnight_letter/episode.json"
SERIES = ROOT / "examples/midnight_letter/series/series.json"


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.data = read_json(EXAMPLE)

    def errors(self):
        return [x.code for x in validate(self.data) if x.level == "error"]

    def test_original_and_explicit_offscreen_pass(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.data["shots"][2]["character_ids"], [])

    def test_unknown_fields_rejected(self):
        self.data["shots"][0]["duraton_ms"] = 8000
        self.assertIn("E001", self.errors())

    def test_wrong_root_and_malformed_values_never_crash(self):
        for value in [None, [], 17, "episode", {}, {"schema_version": "0.1"}]:
            with self.subTest(value=value):
                self.assertTrue(validate(value))
        for field in self.data:
            mutated = copy.deepcopy(self.data)
            mutated[field] = None
            with self.subTest(field=field):
                self.assertTrue(validate(mutated))

    def test_bool_is_not_duration(self):
        self.data["shots"][0]["duration_ms"] = True
        self.assertIn("E001", self.errors())

    def test_duplicate_ids_rejected(self):
        self.data["characters"][1]["id"] = self.data["characters"][0]["id"]
        self.assertIn("E002", self.errors())

    def test_unsafe_id_rejected_before_build(self):
        self.data["shots"][0]["id"] = "../../outside"
        self.assertIn("E001", self.errors())

    def test_missing_name_pronunciation_rejected(self):
        self.data["pronunciation_lexicon"].pop()
        self.assertIn("E003", self.errors())

    def test_unknown_speaker_rejected(self):
        self.data["beats"][0]["lines"][0]["speaker_id"] = "GHOST"
        self.assertIn("E004", self.errors())

    def test_unknown_line_rejected(self):
        self.data["shots"][0]["lines"][0]["line_id"] = "MISSING"
        self.assertIn("E004", self.errors())

    def test_reordered_beats_and_lines_rejected(self):
        self.data["shots"][0], self.data["shots"][1] = self.data["shots"][1], self.data["shots"][0]
        self.assertIn("E005", self.errors())

    def test_state_discontinuity_rejected(self):
        self.data["shots"][1]["state_before"]["letter.location"] = "table"
        self.assertIn("E006", self.errors())

    def test_state_key_typo_rejected(self):
        self.data["shots"][1]["state_after"]["leter.location"] = "table"
        self.assertIn("E006", self.errors())

    def test_line_must_belong_to_shot_beat(self):
        self.data["shots"][0]["lines"][0]["line_id"] = "L002"
        self.assertIn("E007", self.errors())

    def test_onscreen_speaker_must_appear(self):
        self.data["shots"][0]["character_ids"] = ["C002"]
        self.assertIn("E008", self.errors())

    def test_negative_and_out_of_shot_times_rejected(self):
        self.data["shots"][0]["lines"][0]["end_ms"] = 9000
        self.assertIn("E009", self.errors())

    def test_overlapping_dialogue_rejected(self):
        shot = self.data["shots"][0]
        self.data["beats"][0]["lines"].append({"id": "L005", "speaker_id": "C001", "text": "等一下。"})
        shot["lines"].append({"line_id": "L005", "delivery": "on_screen", "start_ms": 5000, "end_ms": 7000})
        self.assertIn("E009", self.errors())

    def test_missing_story_and_line_rejected(self):
        self.data["shots"].pop()
        self.assertIn("E010", self.errors())

    def test_speech_override_warns_but_preserves_contract(self):
        self.data["beats"][0]["lines"][0]["speech_text"] = "经审核的配音输入。"
        self.assertEqual(self.errors(), [])
        self.assertIn("W002", [x.code for x in validate(self.data)])


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "episode.json"
        self.source.write_bytes(EXAMPLE.read_bytes())
        self.bundle = self.root / "bundle"
        self.manifest = compile_episode(self.source, self.bundle)

    def approved_fixture(self):
        """Simulated review/bytes exercise integrity logic, not real media quality."""
        review = review_template(self.bundle)
        (self.bundle / "media").mkdir(exist_ok=True)
        for shot in review["shots"]:
            shot["reviewer"] = "UNIT_TEST_FIXTURE"
            shot["reviewed_at"] = "2026-10-24T12:00:00+08:00"
            for check in shot["checks"].values():
                check.update(status="pass", note="SIMULATED: testing record integrity only")
            for artifact in shot["artifacts"]:
                path = self.bundle / artifact["path"]
                path.write_bytes(b"unit-test bytes, NOT valid audio or video")
                artifact["sha256"] = digest(path)
        review_path = self.bundle / "test-review.json"
        write_json(review_path, review)
        return review_path, review

    def test_outputs_preserve_names_and_planned_status(self):
        srt = (self.bundle / "subtitles.preview.srt").read_text(encoding="utf-8")
        self.assertIn("乐知遥", srt)
        self.assertIn("单行舟", srt)
        self.assertIn("00:00:08,500 --> 00:00:14,500", srt)
        voices = read_json(self.bundle / "voice_plan.json")
        self.assertEqual(voices[0]["pronunciation_hints"][0]["pinyin"], "yue4 zhi1 yao2")
        self.assertEqual(voices[0]["status"], "not_synthesized")
        self.assertIsNone(voices[0]["provider"])
        self.assertEqual(self.manifest["status"], "planning_only")

    def test_same_inputs_generate_identical_bundle(self):
        other = self.root / "other"
        second = compile_episode(self.source, other)
        self.assertEqual(self.manifest, second)
        for name in ["manifest.json"] + list(self.manifest["files"]):
            self.assertEqual((self.bundle / name).read_bytes(), (other / name).read_bytes())

    def test_existing_output_not_overwritten(self):
        with self.assertRaises(ValueError):
            compile_episode(self.source, self.bundle)

    def test_all_task_dependencies_exist_and_are_acyclic(self):
        tasks = read_json(self.bundle / "tasks.json")
        ids = {task["id"] for task in tasks}
        self.assertEqual(len(ids), len(tasks))
        resolved = set()
        remaining = tasks[:]
        while remaining:
            ready = [task for task in remaining if set(task["depends_on"]) <= resolved]
            self.assertTrue(ready, "task dependencies are missing or cyclic")
            for task in ready:
                resolved.add(task["id"])
                remaining.remove(task)

    def test_pending_reviews_and_missing_media_fail(self):
        path = self.bundle / "review.json"
        write_json(path, review_template(self.bundle))
        findings = gate(self.bundle, path, self.source)
        self.assertTrue(findings)

    def test_complete_simulated_record_passes_integrity_checks(self):
        path, _ = self.approved_fixture()
        self.assertEqual(gate(self.bundle, path, self.source), [])

    def test_media_change_invalidates_review(self):
        path, review = self.approved_fixture()
        (self.bundle / review["shots"][0]["artifacts"][0]["path"]).write_bytes(b"changed")
        self.assertTrue(gate(self.bundle, path, self.source))

    def test_plan_change_invalidates_review(self):
        path, _ = self.approved_fixture()
        (self.bundle / "shots/S001.md").write_text("changed", encoding="utf-8")
        self.assertTrue(gate(self.bundle, path, self.source))

    def test_source_change_invalidates_review(self):
        path, _ = self.approved_fixture()
        self.source.write_bytes(self.source.read_bytes() + b"\n")
        self.assertTrue(gate(self.bundle, path, self.source))

    def test_omitted_review_fails(self):
        path, review = self.approved_fixture()
        review["shots"].pop()
        write_json(path, review)
        self.assertTrue(gate(self.bundle, path, self.source))

    def test_foreign_manifest_review_fails(self):
        path, review = self.approved_fixture()
        review["manifest_sha256"] = "0" * 64
        write_json(path, review)
        self.assertTrue(gate(self.bundle, path, self.source))

    def test_invalid_review_status_type_fails_without_crash(self):
        path, review = self.approved_fixture()
        review["shots"][0]["checks"]["visual"]["status"] = []
        write_json(path, review)
        self.assertTrue(gate(self.bundle, path, self.source))

    def test_artifact_cannot_escape_bundle(self):
        path, review = self.approved_fixture()
        review["shots"][0]["artifacts"][0]["path"] = "../episode.json"
        write_json(path, review)
        self.assertTrue(gate(self.bundle, path, self.source))


class SeriesAndIOTests(unittest.TestCase):
    def test_example_series_passes(self):
        self.assertFalse([x for x in validate_series(SERIES) if x.level == "error"])

    def test_shared_canon_change_invalidates_source_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in SERIES.parent.glob("*.json"):
                (root / path.name).write_bytes(path.read_bytes())
            source = root / "ep001.json"
            bundle = root / "bundle"
            manifest = compile_episode(source, bundle)
            canon = root / "canon.json"
            canon.write_bytes(canon.read_bytes() + b"\n")
            _, inputs = load_episode(source)
            self.assertNotEqual(inputs, manifest["input_hashes"])
            review_path = root / "review.json"
            write_json(review_path, review_template(bundle))
            self.assertTrue(any(x.path == "source" for x in gate(bundle, review_path, source)))

    def test_cross_episode_state_change_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in SERIES.parent.glob("*.json"):
                (root / path.name).write_bytes(path.read_bytes())
            episode = read_json(root / "ep002.json")
            # Keep the second episode internally consistent but break the cross-episode chain.
            episode["initial_state"]["letter.location"] = "table"
            episode["shots"][0]["state_before"]["letter.location"] = "table"
            write_json(root / "ep002.json", episode)
            self.assertTrue(any(x.code == "S001" for x in validate_series(root / "series.json")))

    def test_strict_json_duplicate_keys_and_nan(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            for content in ['{"id": 1, "id": 2}', '{"rate": NaN}', '{"rate": Infinity}']:
                path.write_text(content, encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(ValueError):
                    read_json(path)

    def test_timestamp_carry(self):
        self.assertEqual(timestamp(3600001), "01:00:00,001")

    def test_capability_mismatch_is_explicit(self):
        caps = Capabilities(frozenset({"tts"}), frozenset())
        with self.assertRaises(ValueError):
            caps.require("tts", frozenset({"pronunciation_lexicon"}))

    def test_cli_json_success_and_parse_failure(self):
        result = subprocess.run([sys.executable, "-m", "manju", "check", str(EXAMPLE), "--json"], cwd=ROOT, capture_output=True, encoding="utf-8", env=self.utf8_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text("{", encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "manju", "check", str(path), "--json"], cwd=ROOT, capture_output=True, encoding="utf-8", env=self.utf8_env())
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["passed"])

    @staticmethod
    def utf8_env():
        import os
        return {**os.environ, "PYTHONUTF8": "1"}


if __name__ == "__main__":
    unittest.main()
