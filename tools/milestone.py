"""Local release guard. Network pushes are explicit and never target main."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def call(*args, capture=False):
    result = subprocess.run(args, cwd=ROOT, check=True, capture_output=capture, text=True, encoding="utf-8")
    return result.stdout.strip() if capture else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("milestone")
    parser.add_argument("version")
    parser.add_argument("summary")
    args = parser.parse_args()
    if args.milestone not in {f"M{i}" for i in range(9)}:
        raise ValueError("unknown milestone")
    if call("git", "branch", "--show-current", capture=True) != "codex/autopilot":
        raise ValueError("release guard: wrong branch")
    if call("git", "remote", "get-url", "origin", capture=True) != "https://github.com/w1nterdec/ai-manju-engineering.git":
        raise ValueError("release guard: unexpected origin")
    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    state = ROOT / "docs/progress/STATE.md"
    prior = call("git", "ls-remote", "origin", "codex/autopilot", capture=True).split()[0]
    state.write_text(state.read_text(encoding="utf-8") + f"\n## {args.milestone} / {args.version}\n\n{args.summary}\n\n最近一次已核验推送：codex/autopilot `{prior}`，核验时间 {now}。本次提交 SHA 以 git log 和里程碑标签为准，避免在提交内容中自引用自身摘要。\n", encoding="utf-8")
    (ROOT / "manju/__init__.py").write_text(f'"""Offline-first AI motion-comic production engineering."""\n\n__version__ = "{args.version}"\n', encoding="utf-8")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    start = text.index("**当前版本：")
    end = text.index("\n", start)
    text = text[:start] + f"**当前版本：{args.version} / {args.milestone}。** {args.summary} 尚未接入真实生成服务、未经过真实成片或行业评测。进度见 [STATE](docs/progress/STATE.md)。" + text[end:]
    readme.write_text(text, encoding="utf-8")
    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    changelog.write_text(text.replace("# 更新记录\n", f"# 更新记录\n\n## {args.version} — 2026-10-24 / {args.milestone}\n\n- {args.summary}\n- 保持旧 episode/build/CLI 契约兼容；仅离线验证，无真实生成费用。\n", 1), encoding="utf-8")
    call(sys.executable, "tools/verify.py")
    call("git", "add", ".")
    call(sys.executable, "tools/secret_scan.py")
    call("git", "diff", "--cached", "--check")
    call("git", "-c", "user.name=w1nterdec", "-c", "user.email=187599463+w1nterdec@users.noreply.github.com", "commit", "-m", f"feat({args.milestone}): {args.summary}")
    print("LOCAL_VERIFIED", call("git", "rev-parse", "HEAD", capture=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
