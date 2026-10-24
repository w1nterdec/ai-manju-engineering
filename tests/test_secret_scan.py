"""Exercise both merged and outgoing-history scans in disposable offline Git repos."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCANNER = Path(__file__).resolve().parents[1] / "tools/secret_scan.py"


@unittest.skipUnless(shutil.which("git"), "release scanner integration requires Git")
class SecretScanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "--initial-branch=main")
        (self.root / "README.md").write_text("offline scanner fixture\n", encoding="utf-8")
        self.commit()
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=UNIT_FIXTURE", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgSign=false", "-c", f"core.hooksPath={self.root / '.git/hooks'}", *args], cwd=self.root, capture_output=True, check=True)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-m", "offline fixture")

    def scan(self):
        return subprocess.run([sys.executable, str(SCANNER)], cwd=self.root, env={**os.environ, "PYTHONUTF8": "1"}, capture_output=True, text=True, encoding="utf-8")

    def test_merged_head_with_no_outgoing_objects_passes(self):
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_outgoing_range_still_checks_tracked_environment_files(self):
        (self.root / ".env").write_text("# empty unit fixture, contains no credentials\n", encoding="utf-8")
        self.git("add", "--force", ".env")
        self.git("commit", "-m", "empty environment fixture")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        result = self.scan()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("forbidden environment file", result.stdout)

    def test_deleted_large_file_remains_blocked_in_outgoing_history(self):
        path = self.root / "oversized.txt"
        path.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
        self.commit()
        path.unlink()
        self.commit()
        result = self.scan()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("outgoing history contains a blob over 5 MiB", result.stdout)
