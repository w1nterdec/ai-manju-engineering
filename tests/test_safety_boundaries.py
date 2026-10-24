from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import wave

from manju.adapters import MockProvider, WorkRequest, load_config
from manju.io import write_json
from manju.media import probe
from manju.safeio import run_lock


class SafetyTests(unittest.TestCase):
    def test_adapter_key_cannot_escape_output(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            MockProvider().generate(WorkRequest("test", "image", "mock-image", "../escape", {}), directory)

    def test_ffprobe_protocols_are_offline_even_for_local_playlists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.m3u8"
            path.write_text("unit fixture", encoding="utf-8")
            process = SimpleNamespace(returncode=0, stdout='{"format":{"duration":"2"},"streams":[{"codec_type":"video","width":128,"height":72,"avg_frame_rate":"30/1"}]}')
            with patch("manju.media.subprocess.run", return_value=process) as run:
                self.assertEqual(probe(path, ffprobe="UNIT_TEST_TOOL")["status"], "measured")
                args = run.call_args[0][0]
                self.assertEqual(args[args.index("-protocol_whitelist") + 1], "file,pipe")

    def test_truncated_pcm_is_not_accepted_as_measured(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setparams((1, 2, 8000, 0, "NONE", "PCM"))
                stream.writeframes(b"\0\0" * 8000)
            path.write_bytes(path.read_bytes()[:100])
            with patch("manju.media.shutil.which", return_value=None):
                self.assertNotEqual(probe(path)["status"], "measured")

    def test_run_directory_has_single_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            with run_lock(directory):
                with self.assertRaises(ValueError):
                    with run_lock(directory):
                        pass

    def test_malformed_routes_and_simulation_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            data = load_config()
            data["routes"]["shots"]["S001"] = "invalid"
            write_json(path, data)
            with self.assertRaises(ValueError):
                load_config(path)
            data = load_config()
            data["simulation"] = {"fail_first": {"tts:L001": []}}
            write_json(path, data)
            with self.assertRaises(ValueError):
                load_config(path)
