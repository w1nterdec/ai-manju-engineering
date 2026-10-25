"""Optional local helper for the guide; never logs in to production websites."""

import json

from .creator import STAGES, catalog, load_project, new_project, pack_project, verify_pack


def handle(args):
    action = args.creator_command
    if action == "tools":
        tools, _ = catalog()
        items = [tool for tool in tools["tools"] if not args.stage or args.stage in tool["stages"]]
        if args.json:
            print(json.dumps({"as_of": tools["as_of"], "tools": items}, ensure_ascii=False, indent=2))
        else:
            print(f"国内个人工具目录 · 核对日期 {tools['as_of']} · 链接不等于已接入")
            for tool in items:
                print(f"{tool['id']} | {tool['name']} | {tool['url']}\n  {tool['usage_mode']}")
    elif action == "routes":
        _, data = catalog()
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            for route in data["routes"]:
                print(f"{route['id']} | {route['title']} | {route['audience']}")
    elif action == "new":
        new_project(args.out, args.route, args.title)
        print(f"已创建可编辑的原创示例：{args.out}\n修改剧本、人物、读音和镜头表后运行 creator check。未生成媒体。")
    elif action == "check":
        data = load_project(args.project)
        result = {"passed": True, "scope": "仅引用、台词原文、顺序和读音登记检查；不判断实际媒体", "shots": len(data["shots"]), "duration_seconds": data["duration_seconds"], "route_id": data["route"]["id"]}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"PASS：{result['shots']} 镜头，计划 {result['duration_seconds']} 秒。{result['scope']}")
    elif action == "pack":
        pack_project(args.project, args.out)
        print(f"已导出制作包：{args.out}\n打开 index.html 或 README.md，按卡片进入现有工具生成。字幕未实测，审核全部待办。")
    elif action == "verify-pack":
        data = verify_pack(args.pack)
        print(f"PASS：{len(data['files'])} 个参考文件摘要匹配；仅完整性检查，不证明媒体或人审质量。")
    return 0


def add_creator_commands(commands):
    creator = commands.add_parser("creator", help="个人创作指南：工具目录、三条线路、台词检查与制作包导出")
    sub = creator.add_subparsers(dest="creator_command", required=True)
    tools = sub.add_parser("tools", help="列出已引用的国内工具及官网，不发起网络请求")
    tools.add_argument("--stage", choices=STAGES)
    tools.add_argument("--json", action="store_true")
    routes = sub.add_parser("routes", help="查看三条个人生成线路")
    routes.add_argument("--json", action="store_true")
    new = sub.add_parser("new", help="复制可编辑的六镜头原创样例，不覆盖旧目录")
    new.add_argument("--route", default="motion_comic")
    new.add_argument("--title", default="雨夜来信")
    new.add_argument("--out", required=True)
    check = sub.add_parser("check", help="检查镜头引用、原台词和姓名读音登记")
    check.add_argument("project")
    check.add_argument("--json", action="store_true")
    pack = sub.add_parser("pack", help="导出工具入口、逐镜提示词、配音、字幕草稿及审核表")
    pack.add_argument("project")
    pack.add_argument("--out", required=True)
    verify = sub.add_parser("verify-pack", help="核对冻结参考包文件摘要，不代表成片验收")
    verify.add_argument("pack")
    creator.set_defaults(handler=handle)
