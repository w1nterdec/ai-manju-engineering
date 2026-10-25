"""Creator handoff integrity and source fidelity; no live generation or quality claims."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manju.creator import SHOT_FIELDS, catalog, load_project, new_project, pack_project, verify_pack
from manju.safeio import fingerprint


ROOT = Path(__file__).resolve().parents[1]


class CreatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        new_project(self.project)

    def change_shots(self, edit):
        path = self.project / "shots.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        edit(rows)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SHOT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_original_sample_and_offscreen_dialogue(self):
        project = load_project(self.project)
        self.assertEqual(project["duration_seconds"], "46")
        self.assertEqual(len(project["shots"]), 6)
        self.assertEqual(project["shots"][3]["speaker_id"], "C002")
        self.assertNotIn("C002", project["shots"][3]["character_ids"].split(";"))

    def test_dialogue_must_match_original_not_rewritten_caption(self):
        self.change_shots(lambda rows: rows[1].update(dialogue="月知夏，这封信是你放的？"))
        with self.assertRaisesRegex(ValueError, "原文不匹配"):
            load_project(self.project)

    def test_missing_and_reordered_lines_are_rejected(self):
        original = (self.project / "shots.csv").read_bytes()
        for edit in (lambda rows: rows.pop(2), lambda rows: rows.reverse()):
            with self.subTest(edit=edit):
                (self.project / "shots.csv").write_bytes(original)
                self.change_shots(edit)
                with self.assertRaisesRegex(ValueError, "恰好分配一次"):
                    load_project(self.project)

    def test_missing_pronunciation_record_is_rejected(self):
        path = self.project / "pronunciation.csv"
        path.write_text("term,pinyin,note\n单于宁,chan2 yu2 ning2,作者指定\n", encoding="utf-8-sig")
        with self.assertRaisesRegex(ValueError, "完整姓名"):
            load_project(self.project)

    def test_unsafe_ids_unknown_references_and_invalid_durations(self):
        original = (self.project / "shots.csv").read_bytes()
        for field, value in (("shot_id", "../../outside"), ("scene_id", "UNKNOWN"), ("character_ids", "C999"), ("duration_seconds", "NaN"), ("duration_seconds", "Infinity"), ("duration_seconds", "0"), ("duration_seconds", "0.0001")):
            with self.subTest(field=field, value=value):
                (self.project / "shots.csv").write_bytes(original)
                self.change_shots(lambda rows: rows[0].update({field: value}))
                with self.assertRaises(ValueError):
                    load_project(self.project)
        self.assertFalse((self.root / "outside.md").exists())

    def test_bad_csv_shape_is_not_silently_ignored(self):
        path = self.project / "shots.csv"
        with path.open("a", encoding="utf-8") as stream:
            stream.write("BROKEN,not,enough,columns\n")
        with self.assertRaisesRegex(ValueError, "列数不匹配"):
            load_project(self.project)

    def test_deterministic_pack_preserves_source_and_pending_reviews(self):
        first, second = self.root / "pack-v1", self.root / "pack-v2"
        pack_project(self.project, first)
        pack_project(self.project, second)
        manifest = verify_pack(first)
        self.assertEqual(manifest, verify_pack(second))
        self.assertEqual(manifest["status"], "planning_only")
        self.assertEqual(manifest["subtitle_status"], "planned_not_measured")
        for name in manifest["files"]:
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        with (first / "tts-lines.csv").open(encoding="utf-8-sig", newline="") as stream:
            lines = list(csv.DictReader(stream))
        self.assertIn("乐知夏", lines[0]["text"])
        self.assertIn("yue4 zhi1 xia4", lines[0]["pronunciation_hints"])
        captions = (first / "subtitles.planned.srt").read_text(encoding="utf-8")
        self.assertIn(lines[0]["text"], captions)
        self.assertNotIn("yue4", captions)
        with (first / "review.csv").open(encoding="utf-8-sig", newline="") as stream:
            for review in csv.DictReader(stream):
                self.assertEqual([review[k] for k in ("pronunciation", "visual", "story")], ["pending"] * 3)
        with (first / "attempts.csv").open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream)), [])

    def test_html_escapes_project_title(self):
        path = self.project / "project.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["title"] = '<script>alert("x")</script>'
        path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        target = self.root / "pack"
        pack_project(self.project, target)
        text = (target / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)

    def test_existing_versions_are_not_overwritten(self):
        before = (self.project / "script.md").read_bytes()
        with self.assertRaises(ValueError):
            new_project(self.project)
        self.assertEqual((self.project / "script.md").read_bytes(), before)
        target = self.root / "pack"
        pack_project(self.project, target)
        manifest = (target / "manifest.json").read_bytes()
        with self.assertRaises(ValueError):
            pack_project(self.project, target)
        self.assertEqual((target / "manifest.json").read_bytes(), manifest)
        with self.assertRaises(ValueError):
            pack_project(self.project, self.project / "nested")

    def test_failed_export_is_not_published(self):
        target = self.root / "pack"
        with patch("manju.creator.shutil.copyfile", side_effect=OSError("interrupted copy")):
            with self.assertRaises(OSError):
                pack_project(self.project, target)
        self.assertFalse(target.exists())
        pack_project(self.project, target)
        verify_pack(target)

    def test_changes_after_parsing_cannot_mix_old_cards_with_new_snapshot(self):
        from manju import creator
        original = creator.load_project

        def changed_after_parse(path):
            parsed = original(path)
            script = self.project / "script.md"
            script.write_text(script.read_text(encoding="utf-8").replace("可门一直锁着。", "门一直没有打开。"), encoding="utf-8")
            self.change_shots(lambda rows: rows[4].update(dialogue="门一直没有打开。"))
            return parsed

        target = self.root / "mixed"
        with patch("manju.creator.load_project", side_effect=changed_after_parse):
            with self.assertRaisesRegex(ValueError, "输入发生变化"):
                pack_project(self.project, target)
        self.assertFalse(target.exists())

    def test_malformed_manifest_returns_input_error(self):
        target = self.root / "malformed"
        target.mkdir()
        for data in ([], None, "manifest", {"creator_pack_version": "1.0", "status": "planning_only", "files": {"README.md": []}}):
            with self.subTest(data=data):
                (target / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    verify_pack(target)

    def test_pack_tampering_and_escaping_manifest_are_rejected(self):
        target = self.root / "pack"
        pack_project(self.project, target)
        (target / "shots" / "S001.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "已改动"):
            verify_pack(target)
        path = target / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["files"]["../outside.txt"] = "0" * 64
        manifest["pack_id"] = fingerprint({k: v for k, v in manifest.items() if k != "pack_id"})
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_pack(target)

    def test_routes_are_resolvable_and_cli_filters_tools(self):
        tools, routes = catalog()
        self.assertEqual({r["id"] for r in routes["routes"]}, {"motion_comic", "story_video", "agent_first"})
        self.assertTrue(all(t["sources"] for t in tools["tools"]))
        result = subprocess.run([sys.executable, "-m", "manju", "creator", "tools", "--stage", "audio", "--json"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all("audio" in tool["stages"] for tool in json.loads(result.stdout)["tools"]))


if __name__ == "__main__":
    unittest.main()
