import copy
import json
from unittest.mock import patch
import unittest
import wave

from manju.delivery import handoff
from manju.io import read_json, write_json
from manju.media import align, quality_report, validate_alignment
from manju.review import review_template
import test_execution as execution_fixture


class AlignmentValidationTests(unittest.TestCase):
    setUp = execution_fixture.ExecutionTests.setUp

    def aligned(self, long_first=False):
        rows = self.engine.run(self.plan, auto_review_mock=True)["tasks"]
        lines = {key.split(":", 1)[1]: "run/artifacts/" + json.loads(row["result"])["media_path"] for key, row in rows.items() if key.startswith("tts:")}
        if long_first:
            path = self.root / "long.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setparams((1, 2, 8000, 0, "NONE", "synthetic silence"))
                audio.writeframes(b"\0\0" * 72000)
            lines["L001"] = "long.wav"
        audio_map = self.root / "audio-map.json"
        write_json(audio_map, {"audio_map_version": "1.0", "mock": True, "lines": lines})
        directory = self.root / "aligned"
        return directory, align(self.bundle, audio_map, directory)

    def test_complete_legacy_report_without_subtitle_hash_remains_compatible(self):
        directory, report = self.aligned()
        report.pop("subtitle_sha256")
        write_json(directory / "alignment.json", report)
        self.assertEqual(validate_alignment(self.bundle, directory), report)

    def test_missing_shots_lines_bad_measurements_and_totals_are_rejected(self):
        directory, report = self.aligned()
        malformed = []
        for change in ("empty", "missing_line", "overlap", "duration", "digest", "total"):
            modified = copy.deepcopy(report)
            if change == "empty":
                modified["timeline"] = []
            elif change == "missing_line":
                modified["timeline"][0]["cues"] = []
            elif change == "overlap":
                modified["timeline"][1]["start_ms"] = 0
            elif change == "duration":
                modified["measurements"]["L001"]["duration_ms"] += 1
            elif change == "digest":
                modified["timeline"][0]["cues"][0]["audio_sha256"] = "0" * 64
            else:
                modified["duration_ms"] += 1
            malformed.append((change, modified))
        for name, modified in malformed:
            with self.subTest(name=name):
                write_json(directory / "alignment.json", modified)
                with self.assertRaises(ValueError):
                    validate_alignment(self.bundle, directory)

    def test_subtitle_text_and_time_edits_are_rejected_before_handoff(self):
        directory, _ = self.aligned()
        (directory / "subtitles.measured.srt").write_bytes(b"unreviewed replacement")
        with self.assertRaises(ValueError):
            handoff(self.bundle, self.root / "handoff", directory)
        self.assertFalse((self.root / "handoff").exists())

    def test_retimed_video_is_compared_to_validated_audio_timeline(self):
        directory, report = self.aligned(long_first=True)
        durations = {shot["shot_id"]: shot["duration_ms"] for shot in report["timeline"]}
        self.assertEqual(durations["S001"], 11000)
        review = self.root / "review.json"
        write_json(review, review_template(self.bundle))

        def measured(path):
            kind = "video" if path.suffix == ".mp4" else "audio"
            return {"status": "measured", "duration_ms": durations[path.stem], "streams": [{"codec_type": kind}], "fixture": True}

        with patch("manju.media.gate", return_value=[]), patch("manju.media.probe", side_effect=measured):
            planned_report = quality_report(self.bundle, review)
            aligned_report = quality_report(self.bundle, review, alignment=directory)
        self.assertFalse(planned_report["automatic"]["passed"])
        self.assertTrue(aligned_report["automatic"]["passed"])
        self.assertTrue(aligned_report["mock"])
        self.assertFalse(aligned_report["production_ready"])
