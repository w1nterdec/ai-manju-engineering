"""Fail closed on tracked secrets, large/generated files, and outgoing secret diffs."""
from pathlib import Path
import re
import subprocess

PATTERNS = (
    rb"gh[pousr]_" + rb"[A-Za-z0-9]{25,}",
    rb"sk-" + rb"[A-Za-z0-9_-]{24,}",
    rb"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"AKIA" + rb"[A-Z0-9]{16}",
    rb"(?i)(?:api_key|access_token|secret_key)\s*[=:]\s*[\"'](?![\"'])[^\"'\r\n]{16,}[\"']",
)


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"]).decode("utf-8").split("\0")
    errors = []
    for name in filter(None, paths):
        path = Path(name)
        if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
            errors.append(f"forbidden environment file: {name}")
        if name.startswith(("build/", ".manju/")) or path.suffix.lower() in {".mp4", ".wav", ".mp3", ".mov", ".png", ".jpg"}:
            errors.append(f"generated/media file tracked: {name}")
        if path.is_file():
            content = path.read_bytes()
            if len(content) > 5 * 1024 * 1024:
                errors.append(f"file exceeds 5 MiB: {name}")
            if any(re.search(pattern, content) for pattern in PATTERNS):
                errors.append(f"possible secret (value redacted): {name}")
    # Check additions in all commits on this branch plus staged/working diffs.
    commits = subprocess.check_output(["git", "rev-list", "origin/main..HEAD"]).decode().split()
    diffs = [subprocess.check_output(["git", "show", "--format=", "--no-ext-diff", commit]) for commit in commits]
    diffs.append(subprocess.check_output(["git", "diff", "HEAD"]))
    for diff in diffs:
        additions = b"\n".join(line[1:] for line in diff.splitlines() if line.startswith(b"+") and not line.startswith(b"+++"))
        if any(re.search(pattern, additions) for pattern in PATTERNS):
            errors.append("possible secret in outgoing additions (value redacted)")
    for error in errors:
        print("FAIL", error)
    print(f"Secret/size/generated-file scan: {'FAIL' if errors else 'PASS'} ({len(list(filter(None, paths)))} tracked paths)")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
