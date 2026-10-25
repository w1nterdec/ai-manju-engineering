"""Run offline tests and every executable README example in a fresh directory."""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    commands = []
    for source in (ROOT / "README.md", ROOT / "docs/engineering/README.md"):
        for block in re.findall(r"```bash\n(.*?)```", source.read_text(encoding="utf-8"), re.S):
            for line in block.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                text, _, comment = line.partition("#")
                expected = int(re.search(r"expect:\s*(\d+)", comment).group(1)) if "expect:" in comment else 0
                args = shlex.split(text.strip())
                if args[0] != "python" or "tools/verify.py" in args:
                    raise ValueError("README executable blocks must be offline Python examples without recursive verification")
                commands.append(([sys.executable] + args[1:], expected))
    with tempfile.TemporaryDirectory(prefix="manju-verify-") as directory:
        stage = Path(directory)
        for name in ("manju", "examples", "prompts", "tests", "configs", "catalog", "tools"):
            if (ROOT / name).exists():
                shutil.copytree(ROOT / name, stage / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        env = {**os.environ, "PYTHONUTF8": "1"}
        for args, expected in commands:
            result = subprocess.run(args, cwd=stage, env=env, capture_output=True, text=True, encoding="utf-8")
            if result.returncode != expected:
                print("FAIL", args[1:], "expected", expected, "actual", result.returncode)
                print(result.stdout, result.stderr)
                return 1
            print("PASS", " ".join(args[1:]), f"(exit {expected})")
    print(f"README: {len(commands)} offline commands verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
