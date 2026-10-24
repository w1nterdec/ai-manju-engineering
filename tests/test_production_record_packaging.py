"""Synthetic record tests with injected probe/rights responses; NOT media validation."""
from pathlib import Path
import unittest
from unittest.mock import patch

from manju.delivery import package, verify_package
from manju.io import digest, digest_bytes, write_json
from manju.review import review_template
import test_execution as execution_fixture


class ProductionRecordTests(unittest.TestCase):
    setUp = execution_fixture.ExecutionTests.setUp

    def fixture(self):
        review = review_template(self.bundle)
        (self.bundle / "media").mkdir()
        sources = {}
        for shot in review["shots"]:
            shot.update(reviewer="UNIT_TEST_FIXTURE", reviewed_at="2026-10-24T12:00:00+08:00")
            for check in shot["checks"].values():
                check.update(status="pass", note="Synthetic record only; no actual review")
            source = {"provider": "UNIT_TEST_IMPORT", "model": "UNIT_TEST_MODEL", "parameters": {"fixture": True}, "prompt": "unit fixture prompt", "prompt_sha256": digest_bytes(b"unit fixture prompt"), "source_prompt_sha256": digest(self.bundle / "shots" / f"{shot['shot_id']}.md"), "input_asset_ids": ["a" * 64]}
            for artifact in shot["artifacts"]:
                path = self.bundle / artifact["path"]
                path.write_bytes(b"SYNTHETIC BYTES - not actual media")
                artifact["sha256"] = digest(path)
                source[artifact["kind"] + "_sha256"] = digest(path)
            sources[shot["shot_id"]] = source
        review_path = self.root / "review.json"
        write_json(review_path, review)
        final = self.root / "synthetic.mp4"
        final.write_bytes(b"SYNTHETIC - not an actual video")
        aligned = self.root / "alignment"
        aligned.mkdir()
        write_json(aligned / "alignment.json", {"alignment_version": "1.0", "mock": False, "fixture": True, "manifest_sha256": digest(self.bundle / "manifest.json"), "duration_ms": 32000, "timeline": []})
        (aligned / "subtitles.measured.srt").write_text("synthetic fixture", encoding="utf-8")
        provenance = self.root / "provenance.json"
        write_json(provenance, {"provenance_version": "1.0", "manifest_sha256": digest(self.bundle / "manifest.json"), "shots": sources, "final": {"sha256": digest(final), "editor": "UNIT_FIXTURE", "tool": "UNIT_FIXTURE"}})
        self.config["ai_label"] = {"platform": "UNIT_TEST", "disclosure": "synthetic record test only", "verified_by": "UNIT_FIXTURE", "as_of": "2026-10-24", "source_url": "https://example.invalid/fixture"}
        continuity = self.root / "continuity.json"
        write_json(continuity, {"fixture": True})
        self.config["delivery_files"] = {"continuity_report": str(continuity)}
        checklist = self.root / "checklist.json"
        write_json(checklist, {"checks_version": "1.0", "final_sha256": digest(final), "checks": {key: {"status": "pass", "reviewer": "UNIT_FIXTURE", "note": "record test, not actual acceptance"} for key in ("cross_episode_identity", "prop_continuity")}})
        return {"review": review_path, "final": final, "alignment": aligned, "provenance": provenance, "profile_checks": checklist}

    def test_full_record_path_copies_reviewed_files_and_nested_build(self):
        inputs = self.fixture()
        # Injected outcomes exercise packaging only; actual rights/media are not asserted.
        rights = {"passed": True, "assets": [{"asset_id": "a" * 64}], "fixture": True}
        measured = {"status": "measured", "duration_ms": 32000, "streams": [{"codec_type": "video", "width": 128, "height": 72, "fps": "30"}, {"codec_type": "audio"}]}
        with patch("manju.delivery.identity_report", return_value=rights), patch("manju.delivery.quality_report", return_value={"production_ready": True, "fixture": True}), patch("manju.delivery.probe", return_value=measured):
            output = self.root / "package"
            package(self.bundle, output, self.config, **inputs)
            self.assertTrue(verify_package(output)["passed"])
            self.assertEqual(len(list((output / "reviewed-media").glob("*"))), 2)
            self.assertTrue((output / "source/subtitles.preview.srt").is_file())

    def test_final_missing_audio_blocks_even_with_injected_other_passes(self):
        inputs = self.fixture()
        rights = {"passed": True, "assets": [{"asset_id": "a" * 64}]}
        measured = {"status": "measured", "duration_ms": 32000, "streams": [{"codec_type": "video", "width": 128, "height": 72, "fps": "30"}]}
        with patch("manju.delivery.identity_report", return_value=rights), patch("manju.delivery.quality_report", return_value={"production_ready": True}), patch("manju.delivery.probe", return_value=measured), self.assertRaises(ValueError):
            package(self.bundle, self.root / "package", self.config, **inputs)
