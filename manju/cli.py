import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .build import compile_episode, init_episode
from .io import digest
from .project import load_episode, validate_series
from .review import gate, review_template
from .validation import validate
from .production_cli import add_commands
from .safeio import redact
from .creator_cli import add_creator_commands


def report(findings, as_json, success):
    passed = not any(x.level == "error" for x in findings)
    if as_json:
        print(json.dumps({"passed": passed, "scope": success, "findings": [x.to_dict() for x in findings]}, ensure_ascii=False, indent=2))
    else:
        for item in findings:
            print(f"{item.level.upper()} {item.code} {item.path}: {item.message}")
        print(f"{'PASS' if passed else 'FAIL'} — {success}")
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m manju", description="个人 AI 短剧与漫剧指南的本地辅助：先用 creator 选线路和导出制作包；旧工程命令可选。不调用生成平台。")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    add_creator_commands(commands)
    init = commands.add_parser("init", help="复制可编辑的原创示例，不覆盖已有文件")
    init.add_argument("destination")
    check = commands.add_parser("check", help="检查结构、台词、读音登记与状态连续性")
    check.add_argument("source")
    check.add_argument("--json", action="store_true")
    series = commands.add_parser("check-series", help="批量检查共享设定、单集 ID 与可选跨集状态连续性")
    series.add_argument("source")
    series.add_argument("--json", action="store_true")
    build = commands.add_parser("build", help="编译提示词、配音清单、预览字幕和依赖计划")
    build.add_argument("source")
    build.add_argument("--out", required=True)
    template = commands.add_parser("review-template", help="为冻结构建创建待复核记录")
    template.add_argument("bundle")
    template.add_argument("--out")
    review = commands.add_parser("gate", help="验证逐镜头人工复核及媒体摘要；不代表最终成片验收")
    review.add_argument("bundle")
    review.add_argument("review")
    review.add_argument("--source", help="同时检查当前源剧本是否仍与本次构建相同")
    review.add_argument("--json", action="store_true")
    review.add_argument("--production-config", help="额外检查实际素材和声音授权记录")
    hash_command = commands.add_parser("hash", help="计算产物 SHA-256，写入复核记录")
    hash_command.add_argument("file")
    add_commands(commands)
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "handler"):
            return args.handler(args)
        if args.command == "init":
            init_episode(args.destination)
            print(f"已创建：{args.destination}")
        elif args.command == "check":
            data, _ = load_episode(args.source)
            return report(validate(data), args.json, "仅剧本静态检查；音视频尚需生成与人工复核")
        elif args.command == "check-series":
            return report(validate_series(args.source), args.json, "仅系列剧本静态检查；音视频尚需生成与人工复核")
        elif args.command == "build":
            manifest = compile_episode(args.source, args.out)
            print(f"已编译 {len(manifest['shots'])} 个镜头 → {args.out}\n状态：planning_only；未生成音视频，字幕时间为草稿。")
        elif args.command == "review-template":
            data = review_template(args.bundle)
            if args.out:
                with Path(args.out).open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                print(f"已创建待复核记录：{args.out}")
            else:
                print(json.dumps(data, ensure_ascii=False, indent=2))
        elif args.command == "gate":
            return report(gate(args.bundle, args.review, args.source, args.production_config), args.json, "冻结构建的逐镜头人工复核记录；非自动媒体质量判定，非最终成片验收")
        elif args.command == "hash":
            print(digest(args.file))
    except (OSError, ValueError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"passed": False, "error": redact(str(exc))}, ensure_ascii=False))
        else:
            print(f"ERROR: {redact(str(exc))}", file=sys.stderr)
        return 2
    return 0
