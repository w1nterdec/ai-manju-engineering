from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from manju.media import align, asr_screen, probe, quality_report
from manju.io import write_json
import test_execution as execution_fixture


class ProbeTests(unittest.TestCase):
    def test_wave_is_measured_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "silence.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                stream.writeframes(b"\0\0" * 12000)
            self.assertEqual(probe(path)["duration_ms"], 1500)

    def test_missing_ffprobe_is_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mock.json"
            path.write_text("{}", encoding="utf-8")
            with patch("manju.media.shutil.which", return_value=None):
                self.assertEqual(probe(path)["status"], "unavailable")

    def test_asr_matching_text_still_needs_listening(self):
        result = asr_screen("乐知遥", "乐知遥")
        self.assertTrue(result["matches"])
        self.assertTrue(result["requires_pronunciation_review"])


class AlignmentTests(unittest.TestCase):
    setUp = execution_fixture.ExecutionTests.setUp

    def test_mock_audio_alignment_and_quality_remain_simulation(self):
        import json
        rows = self.engine.run(self.plan, auto_review_mock=True)["tasks"]
        lines = {key.split(":", 1)[1]: "run/artifacts/" + json.loads(row["result"])["media_path"] for key, row in rows.items() if key.startswith("tts:")}
        path = self.root / "audio-map.json"
        write_json(path, {"audio_map_version": "1.0", "mock": True, "lines": lines})
        result = align(self.bundle, path, self.root / "aligned")
        self.assertTrue(result["mock"])
        self.assertEqual(len(result["measurements"]), 4)
        self.assertIn("乐知遥", (self.root / "aligned/subtitles.measured.srt").read_text(encoding="utf-8"))
        report = quality_report(self.bundle, run=self.engine.root)
        self.assertFalse(report["production_ready"])
        self.assertTrue(report["mock"])

    def test_missing_audio_line_fails_alignment(self):
        path = self.root / "bad.json"
        write_json(path, {"audio_map_version": "1.0", "lines": {}})
        with self.assertRaises(ValueError):
            align(self.bundle, path, self.root / "aligned")
