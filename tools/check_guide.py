"""Offline checks for guide links, tool provenance and personal route references."""

from datetime import date
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from manju.creator import catalog  # noqa: E402
from manju.io import read_json  # noqa: E402


def check():
    tools, routes = catalog()
    date.fromisoformat(tools["as_of"])
    for tool in tools["tools"]:
        for source in tool["sources"]:
            address = urlsplit(source["url"])
            if address.scheme != "https" or not address.hostname or address.username or address.password:
                raise ValueError(f"工具 {tool['id']} 的官方来源地址无效")
            date.fromisoformat(source["verified_on"])
    reuse = read_json(ROOT / "catalog" / "reuse.json")
    seen = set()
    for project in reuse["projects"]:
        if project["id"] in seen or not re.fullmatch(r"[0-9a-f]{40}", project["ref"]):
            raise ValueError("复用项目 ID 或固定版本无效")
        seen.add(project["id"])
        if project["ref"] not in project["license_url"] or project["integration_status"] != "reference_only":
            raise ValueError("复用候选必须有固定版本许可证，并准确标记尚未集成")
        date.fromisoformat(project["checked_on"])
    documents = [ROOT / name for name in ("README.md", "ROADMAP.md", "CONTRIBUTING.md", "docs/start-here.md", "docs/references.md")]
    for directory in ("docs/creator-guide", "docs/engineering", "catalog", "prompts", "examples/creator", "docs/plans"):
        documents.extend(sorted((ROOT / directory).glob("*.md")))
    failures = []
    checked = 0
    for path in documents:
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for raw in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            link = raw.strip().strip("<>")
            parts = urlsplit(link)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            target = (path.parent / unquote(parts.path)).resolve()
            checked += 1
            if not target.is_relative_to(ROOT) or not target.exists():
                failures.append(f"{path.relative_to(ROOT)} -> {link}")
    if failures:
        raise ValueError("内部链接缺失或越界：\n" + "\n".join(failures))
    print(f"PASS：{len(documents)} 篇文档，{checked} 个内部链接，{len(tools['tools'])} 个工具，{len(routes['routes'])} 条线路，{len(reuse['projects'])} 个固定版本复用候选。")
    print("仅离线校验目录和链接，不代表外部网站实时可用、许可证法律结论或实际生成效果。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(check())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL：{exc}", file=sys.stderr)
        raise SystemExit(1)
