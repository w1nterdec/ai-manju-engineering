"""Personal creator recipes and deterministic handoff packs; no provider calls."""

import csv
from decimal import Decimal, InvalidOperation
import html
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

from .io import digest, digest_bytes, read_json
from .safeio import fingerprint


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = ("script.md", "characters.md", "pronunciation.csv", "shots.csv")
SHOT_FIELDS = ("shot_id", "scene_id", "character_ids", "line_id", "speaker_id", "dialogue", "visual", "duration_seconds", "image_prompt", "video_prompt")
WORD_FIELDS = ("term", "pinyin", "note")
ID = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
STAGES = ("script", "reference", "image", "video", "audio", "edit", "review", "manage", "publish")
PROMPT_FILES = ("07-reference-and-keyframes.md", "08-image-to-video.md", "09-agent-handoff.md", "10-continuity-check.md")


def catalog():
    tools = read_json(ROOT / "catalog" / "tools.json")
    routes = read_json(ROOT / "catalog" / "routes.json")
    if tools.get("catalog_version") != "1.0" or routes.get("catalog_version") != "1.0":
        raise ValueError("工具与线路目录版本不支持")
    by_id = {}
    for tool in tools["tools"]:
        key = tool["id"]
        if key in by_id:
            raise ValueError("工具 ID 重复")
        address = urlsplit(tool["url"])
        if address.scheme != "https" or not address.hostname or address.username or address.password:
            raise ValueError("工具入口必须是无凭据的 HTTPS 地址")
        if not tool.get("sources") or not set(tool["stages"]) <= set(STAGES):
            raise ValueError("工具必须登记来源和已知环节")
        by_id[key] = tool
    route_ids = set()
    for route in routes["routes"]:
        if route["id"] in route_ids or not ID.fullmatch(route["id"].upper()):
            raise ValueError("线路 ID 无效或重复")
        route_ids.add(route["id"])
        steps = set()
        for step in route["steps"]:
            if step["id"] in steps or step["id"] not in STAGES:
                raise ValueError("线路环节无效或重复")
            steps.add(step["id"])
            if not set(step["tool_ids"]) <= by_id.keys():
                raise ValueError("线路引用了未登记的工具")
    return tools, routes


def get_route(route_id):
    _, routes = catalog()
    for route in routes["routes"]:
        if route["id"] == route_id:
            return route
    raise ValueError(f"未知线路 {route_id}；请先运行 creator routes")


def _csv_read(path, fields, content=None):
    stream = io.StringIO(content.decode("utf-8-sig"), newline="") if content is not None else path.open(encoding="utf-8-sig", newline="")
    with stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(fields):
            raise ValueError(f"{path.name} 表头应为：{','.join(fields)}")
        rows = []
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path.name} 第 {number} 行列数不匹配")
            if any(len(value) > 20000 for value in row.values()):
                raise ValueError(f"{path.name} 第 {number} 行内容过长")
            rows.append(row)
            if len(rows) > 1000:
                raise ValueError(f"{path.name} 超出个人制作包的 1000 行上限")
        return rows


def _csv_write(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _publish_directory(destination, populate):
    """Publish a complete new directory, without overwriting an earlier version."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("输出已存在，请使用新目录，避免覆盖制作记录")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".manju-creator-", dir=destination.parent) as temp:
        stage = Path(temp) / "result"
        stage.mkdir()
        populate(stage)
        if destination.exists() or destination.is_symlink():
            raise ValueError("输出在制作过程中已被创建，拒绝覆盖")
        stage.rename(destination)


def new_project(destination, route_id="motion_comic", title="雨夜来信"):
    get_route(route_id)
    if not title.strip() or len(title) > 120 or any(ord(c) < 32 for c in title):
        raise ValueError("标题须为 1 至 120 字的单行文字")

    def populate(stage):
        for name in SOURCE_FILES:
            shutil.copyfile(ROOT / "examples" / "creator" / name, stage / name)
        data = {"creator_version": "1.0", "title": title, "route_id": route_id}
        (stage / "project.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "README.md").write_text(
            "# 个人创作项目\n\n编辑 script.md 原台词、characters.md 设定、pronunciation.csv 读音和 shots.csv 分镜。\n"
            "标题参数只设置项目名，不会自动改写示例故事；创作自己的作品时请一起替换四份输入。\n\n"
            "运行 creator check 检查引用，再用 creator pack 导出新版本制作包。网站中的生成、试听和选片由本人完成。\n",
            encoding="utf-8",
        )
    _publish_directory(destination, populate)


def load_project(directory):
    directory = Path(directory).resolve()
    for name in ("project.json",) + SOURCE_FILES:
        path = directory / name
        if not path.is_file() or path.resolve().parent != directory:
            raise ValueError(f"缺少项目输入或输入位于项目外：{name}")
    # Parse a single byte snapshot, rather than mixing reads while an editor saves.
    raw = {name: (directory / name).read_bytes() for name in ("project.json",) + SOURCE_FILES}
    source_hashes = {name: digest_bytes(value) for name, value in raw.items()}

    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("project.json 有重复字段")
            data[key] = value
        return data

    config = json.loads(raw["project.json"].decode("utf-8-sig"), object_pairs_hook=unique)
    if not isinstance(config, dict) or set(config) != {"creator_version", "title", "route_id"} or config.get("creator_version") != "1.0":
        raise ValueError("project.json 须包含 creator_version 1.0、title 和 route_id")
    if not isinstance(config["title"], str) or not config["title"].strip() or len(config["title"]) > 120 or any(ord(c) < 32 for c in config["title"]):
        raise ValueError("项目标题无效")
    route = get_route(config["route_id"])
    characters = {}
    scenes = set()
    character_text = raw["characters.md"].decode("utf-8-sig")
    for line in character_text.splitlines():
        match = re.fullmatch(r"##\s+(C[A-Z0-9_]{0,63})\s+(.+)", line.strip())
        scene = re.fullmatch(r"##\s+(SC[A-Z0-9_]{0,62})\s+(.+)", line.strip())
        if match:
            key, name = match.groups()
            if key in characters or name.strip() in characters.values():
                raise ValueError("characters.md 角色 ID 或姓名重复")
            characters[key] = name.strip()
        if scene:
            if scene.group(1) in scenes:
                raise ValueError("characters.md 场景 ID 重复")
            scenes.add(scene.group(1))
    if not characters or not scenes:
        raise ValueError("characters.md 需要 ## C001 姓名 和 ## SC001 场景 这类标题")
    lines = {}
    for line in raw["script.md"].decode("utf-8-sig").splitlines():
        match = re.fullmatch(r"(L[A-Z0-9_]{0,63})\s*\|\s*(C[A-Z0-9_]{0,63})\s*\|\s*(.+)", line.strip())
        if match:
            key, speaker, text = match.groups()
            if key in lines or speaker not in characters:
                raise ValueError("script.md 台词 ID 重复或说话人不存在")
            lines[key] = (speaker, text.strip())
    if not lines:
        raise ValueError("script.md 需有独立台词索引行，例如 L001 | C001 | 台词原文")
    words = _csv_read(directory / "pronunciation.csv", WORD_FIELDS, raw["pronunciation.csv"])
    terms = set()
    for row in words:
        if not row["term"].strip() or row["term"] in terms or not re.fullmatch(r"[a-züv]+[1-5](?:\s+[a-züv]+[1-5])*", row["pinyin"]):
            raise ValueError("读音词典需有唯一术语和带数字声调的拼音；它不证明读音正确")
        terms.add(row["term"])
    if not set(characters.values()) <= terms:
        raise ValueError("pronunciation.csv 必须登记每位角色的完整姓名")
    shots = _csv_read(directory / "shots.csv", SHOT_FIELDS, raw["shots.csv"])
    if not shots:
        raise ValueError("镜头表不能为空")
    seen = set()
    used_lines = []
    duration = Decimal(0)
    for shot in shots:
        sid = shot["shot_id"]
        if not ID.fullmatch(sid) or sid in seen:
            raise ValueError("镜头 ID 无效或重复，禁止将路径用作 ID")
        seen.add(sid)
        if shot["scene_id"] not in scenes:
            raise ValueError(f"{sid} 引用的场景未在 characters.md 登记")
        cast = shot["character_ids"].split(";") if shot["character_ids"] else []
        if len(cast) != len(set(cast)) or not set(cast) <= characters.keys():
            raise ValueError(f"{sid} 引用的画面角色不存在或重复")
        if not shot["visual"].strip() or not shot["image_prompt"].strip():
            raise ValueError(f"{sid} 缺少画面内容或图片提示词")
        if route["id"] != "motion_comic" and not shot["video_prompt"].strip():
            raise ValueError(f"{sid} 视频线路需要视频提示词")
        try:
            seconds = Decimal(shot["duration_seconds"])
        except InvalidOperation as exc:
            raise ValueError(f"{sid} 时长须为正数秒") from exc
        if not seconds.is_finite() or seconds <= 0 or seconds > 600:
            raise ValueError(f"{sid} 计划时长须在 0 至 600 秒之间，不含 0")
        if seconds * 1000 != (seconds * 1000).to_integral_value():
            raise ValueError(f"{sid} 时长最多保留三位小数")
        duration += seconds
        lid, speaker, dialogue = shot["line_id"], shot["speaker_id"], shot["dialogue"]
        if lid:
            if lid not in lines or lines[lid] != (speaker, dialogue):
                raise ValueError(f"{sid} 台词或说话人与 script.md 原文不匹配")
            used_lines.append(lid)
        elif speaker or dialogue:
            raise ValueError(f"{sid} 有台词时必须填写 line_id 和 speaker_id")
    if used_lines != list(lines):
        raise ValueError("原台词必须按原顺序恰好分配一次，不能遗漏、重复或调序")
    if any(digest(directory / name) != value for name, value in source_hashes.items()):
        raise ValueError("读取期间项目输入发生变化，请保存编辑后重试")
    return {"directory": directory, "config": config, "route": route, "characters": characters, "words": words, "shots": shots, "lines": lines, "duration_seconds": str(duration), "source_hashes": source_hashes}


def _hint(words, text):
    return "；".join(f"{word['term']}：{word['pinyin']}（{word['note']}）" for word in words if word["term"] in text)


def _stamp(milliseconds):
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def pack_project(directory, destination):
    project = load_project(directory)
    source = project["directory"]
    target = Path(destination).resolve()
    if target == source or target.is_relative_to(source):
        raise ValueError("制作包请放在项目目录外，以保留输入与导出的边界")
    tool_catalog, route_catalog = catalog()
    route = project["route"]
    selected = {key for step in route["steps"] for key in step["tool_ids"]}
    tools = [tool for tool in tool_catalog["tools"] if tool["id"] in selected]
    inputs = project["source_hashes"]

    def populate(stage):
        (stage / "inputs").mkdir()
        (stage / "shots").mkdir()
        (stage / "prompt-library").mkdir()
        for name in inputs:
            shutil.copyfile(source / name, stage / "inputs" / name)
            if digest(stage / "inputs" / name) != inputs[name]:
                raise ValueError("导出期间输入发生变化，请重新检查后再导出")
        for name in PROMPT_FILES:
            shutil.copyfile(ROOT / "prompts" / name, stage / "prompt-library" / name)
        for name, data in (("tools.snapshot.json", tool_catalog), ("routes.snapshot.json", route_catalog)):
            (stage / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        readme = [f"# {project['config']['title']} 制作包", "", f"生成线路：{route['title']}。计划 {project['duration_seconds']} 秒；尚未生成、试听或审核媒体。", "", "## 操作顺序", ""]
        for step in route["steps"]:
            readme.extend([f"### {step['title']}", f"输入：{step['input']}。输出：{step['output']}。", f"本人检查：{step['human_check']}。", ""])
        readme += ["## 工具入口", ""] + [f"- [{tool['name']}]({tool['url']})：{tool['usage_mode']}" for tool in tools]
        readme += ["", "## 文件使用", "", "逐镜查看 shots/ 中的制作卡；实际操作时上传经本人确认的参考图片。", "tts-lines.csv 保留原台词与独立读音提示，不能将拼音说明当成配音正文。", "subtitles.planned.srt 仅按计划镜头时长分配，必须在实际配音和终剪后重新对齐。", "review.csv 全部为 pending；由本人观看、试听后填写。attempts.csv 用于记录每次尝试与费用，空金额表示未知，不能当成零。", "本目录是冻结参考包。先将审核和尝试表复制到包外的工作记录目录再填写，保留原包用于完整性校验。", "平台导出的素材、声音、模型与参考版本由本人填写，网站不会自动读取本地文件。", "", route["fallbacks"], route["limitations"], "", "本制作包不登录平台、不自动提交生成、不调用付费 API，不证明实际画面或读音质量。"]
        (stage / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
        voices, reviews, subtitles = [], [], []
        elapsed = 0
        cards = []
        for shot in project["shots"]:
            hints = _hint(project["words"], shot["dialogue"])
            card = [f"# 镜头 {shot['shot_id']}", "", f"场景：{shot['scene_id']}；画面角色：{shot['character_ids'] or '无'}；计划 {shot['duration_seconds']} 秒。", "", "## 画面与剧情", shot["visual"], "", "## 图片提示词", shot["image_prompt"], "", "## 视频或动态化提示词", shot["video_prompt"] or "在剪映使用关键帧与局部动态。", "", "## 声音与字幕", f"原台词：{shot['dialogue'] or '无'}", f"说话人：{shot['speaker_id'] or '无'}；台词编号：{shot['line_id'] or '无'}", f"独立读音提示：{hints or '无匹配词；仍须逐句试听'}", "", "## 本人检查", "- 姓名、音色、停顿与原文。", "- 人物、服装、手部、站位、道具与完整动作。", "- 本镜头是否真实表达原剧本中的信息，相邻镜头是否衔接。", "", "本地角色 ID 和参考文件名不会自动绑定平台角色；请主动上传并核对。"]
            (stage / "shots" / f"{shot['shot_id']}.md").write_text("\n".join(card) + "\n", encoding="utf-8")
            ms = int(Decimal(shot["duration_seconds"]) * 1000)
            if shot["line_id"]:
                voices.append({"line_id": shot["line_id"], "shot_id": shot["shot_id"], "speaker_id": shot["speaker_id"], "text": shot["dialogue"], "pronunciation_hints": hints})
                subtitles.append(f"{len(subtitles) + 1}\n{_stamp(elapsed)} --> {_stamp(elapsed + ms)}\n{shot['dialogue']}\n")
            elapsed += ms
            reviews.append({"shot_id": shot["shot_id"], "pronunciation": "pending", "visual": "pending", "story": "pending", "artifact_path": "", "reviewer": "", "note": ""})
            cards.append(f'<li><a href="shots/{shot["shot_id"]}.md">{html.escape(shot["shot_id"])}</a> {html.escape(shot["visual"])}<br><small>{html.escape(shot["dialogue"] or "无台词")}</small></li>')
        _csv_write(stage / "tts-lines.csv", ("line_id", "shot_id", "speaker_id", "text", "pronunciation_hints"), voices)
        _csv_write(stage / "review.csv", ("shot_id", "pronunciation", "visual", "story", "artifact_path", "reviewer", "note"), reviews)
        _csv_write(stage / "attempts.csv", ("shot_id", "stage", "tool_id", "model", "reference_version", "artifact_path", "decision", "reason", "cost_amount", "currency", "created_at"), [])
        (stage / "subtitles.planned.srt").write_text("\n".join(subtitles), encoding="utf-8")
        links = "".join(f'<li><a href="{html.escape(tool["url"], quote=True)}" rel="noreferrer">{html.escape(tool["name"])}</a></li>' for tool in tools)
        page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        page += f'<title>{html.escape(project["config"]["title"])}</title>'
        page += '<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:32px auto;padding:0 20px;line-height:1.7}li{margin:12px 0}small{color:#555}a{overflow-wrap:anywhere}</style>'
        page += f'<h1>{html.escape(project["config"]["title"])} 制作参考</h1><p>{html.escape(route["title"])} · {len(project["shots"])} 镜头 · 计划 {project["duration_seconds"]} 秒</p>'
        page += '<p>这是待生成的冻结参考包，未生成或审核真实媒体。字幕为计划草稿。请将审核和尝试表复制到包外再填写，保留原包供完整性校验。</p><p><a href="README.md">制作顺序</a> · <a href="tts-lines.csv">配音清单</a> · <a href="review.csv">审核表</a> · <a href="attempts.csv">尝试记录</a></p>'
        page += '<h2>镜头</h2><ol>' + "".join(cards) + '</ol><h2>工具入口</h2><ul>' + links + '</ul></html>'
        (stage / "index.html").write_text(page, encoding="utf-8")
        if any(digest(source / name) != value for name, value in inputs.items()):
            raise ValueError("导出期间原项目被修改，制作包未发布")
        files = {path.relative_to(stage).as_posix(): digest(path) for path in sorted(stage.rglob("*")) if path.is_file()}
        manifest = {"creator_pack_version": "1.0", "status": "planning_only", "route_id": route["id"], "source_hashes": inputs, "catalog_as_of": tool_catalog["as_of"], "duration_seconds": project["duration_seconds"], "subtitle_status": "planned_not_measured", "files": files}
        manifest["pack_id"] = fingerprint(manifest)
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _publish_directory(destination, populate)


def verify_pack(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("creator_pack_version") != "1.0" or manifest.get("status") != "planning_only" or not isinstance(manifest.get("files"), dict) or not manifest["files"]:
        raise ValueError("不是有效的个人制作参考包")
    if any(not isinstance(name, str) or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for name, value in manifest["files"].items()):
        raise ValueError("制作包文件索引格式无效")
    payload = {key: value for key, value in manifest.items() if key != "pack_id"}
    if fingerprint(payload) != manifest.get("pack_id"):
        raise ValueError("制作包清单摘要不匹配")
    for name, value in manifest["files"].items():
        path = directory / name
        if not path.resolve().is_relative_to(directory) or not path.is_file() or path.is_symlink() or digest(path) != value:
            raise ValueError(f"制作包文件缺失、越界或已改动：{name}")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    if actual != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("制作包存在未登记文件；记录与返工请使用副本")
    return manifest
