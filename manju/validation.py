"""Validate the editorial contract; never infer media quality from text."""

from collections import Counter
from dataclasses import asdict, dataclass
import math
import re


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    path: str
    message: str

    def to_dict(self):
        return asdict(self)


def validate(data):
    findings = []

    def error(code, path, message):
        findings.append(Finding("error", code, path, message))

    def warn(code, path, message):
        findings.append(Finding("warning", code, path, message))

    def obj(value, path, required, optional=()):
        if not isinstance(value, dict):
            error("E001", path, "必须是对象")
            return False
        for key in sorted(set(required) - value.keys()):
            error("E001", f"{path}.{key}", "缺少必填字段")
        for key in sorted(value.keys() - set(required) - set(optional)):
            error("E001", f"{path}.{key}", "未知字段，请检查拼写或契约版本")
        return True

    def string(value, path, empty=False):
        if not isinstance(value, str) or (not empty and not value.strip()):
            error("E001", path, "必须是非空字符串" if not empty else "必须是字符串")
            return False
        return True

    def integer(value, path, minimum=0):
        if type(value) is not int or value < minimum:
            error("E001", path, f"必须是 >= {minimum} 的整数")

    def strings(value, path, nonempty=False):
        if not isinstance(value, list) or (nonempty and not value):
            error("E001", path, "必须是字符串数组" + ("且不能为空" if nonempty else ""))
            return
        for i, item in enumerate(value):
            string(item, f"{path}[{i}]")
        if all(isinstance(x, str) for x in value) and len(set(value)) != len(value):
            error("E002", path, "不允许重复项")

    def items(value, path, nonempty=True):
        if not isinstance(value, list) or (nonempty and not value):
            error("E001", path, "必须是数组" + ("且不能为空" if nonempty else ""))
            return []
        return list(enumerate(value))

    def state(value, path):
        if not isinstance(value, dict) or not value:
            error("E001", path, "状态必须是非空的字符串键值对象")
            return
        for key, item in value.items():
            string(key, path)
            string(item, f"{path}.{key}")

    def identifier(value, path):
        if string(value, path) and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value):
            error("E001", path, "ID 只允许大写字母开头的 A-Z、0-9、下划线，最长 64 字符")

    root = ("schema_version", "project", "characters", "pronunciation_lexicon", "beats", "initial_state", "shots")
    if not obj(data, "$", root):
        return findings
    if data.get("schema_version") != "0.1":
        error("E001", "$.schema_version", "仅支持契约版本 0.1")
    project = data.get("project")
    if obj(project, "$.project", ("id", "title", "language", "aspect_ratio", "visual_style", "canon_facts", "negative_prompt"), ("dialogue_cps_warning",)):
        identifier(project.get("id"), "$.project.id")
        for key in ("title", "language", "aspect_ratio", "visual_style", "negative_prompt"):
            string(project.get(key), f"$.project.{key}")
        strings(project.get("canon_facts"), "$.project.canon_facts", True)
        rate = project.get("dialogue_cps_warning", 6.0)
        if type(rate) not in (int, float) or not math.isfinite(rate) or rate <= 0:
            error("E001", "$.project.dialogue_cps_warning", "必须是有限正数")
    for i, char in items(data.get("characters"), "$.characters"):
        path = f"$.characters[{i}]"
        if obj(char, path, ("id", "name", "appearance", "voice_direction"), ("reference_image",)):
            identifier(char.get("id"), f"{path}.id")
            for key in ("name", "appearance", "voice_direction"):
                string(char.get(key), f"{path}.{key}")
            if "reference_image" in char:
                string(char["reference_image"], f"{path}.reference_image", True)
    for i, lexeme in items(data.get("pronunciation_lexicon"), "$.pronunciation_lexicon"):
        path = f"$.pronunciation_lexicon[{i}]"
        if obj(lexeme, path, ("term", "pinyin", "note")):
            for key in ("term", "pinyin", "note"):
                string(lexeme.get(key), f"{path}.{key}")
            pinyin = lexeme.get("pinyin")
            if isinstance(pinyin, str) and not re.fullmatch(r"[a-zv:]+[1-5]( [a-zv:]+[1-5])*", pinyin):
                error("E001", f"{path}.pinyin", "使用数字声调，如 shan4 xing2 zhou1；轻声用 5")
    for i, beat in items(data.get("beats"), "$.beats"):
        path = f"$.beats[{i}]"
        if obj(beat, path, ("id", "summary", "required_facts", "lines")):
            identifier(beat.get("id"), f"{path}.id")
            string(beat.get("summary"), f"{path}.summary")
            strings(beat.get("required_facts"), f"{path}.required_facts", True)
            for j, line in items(beat.get("lines"), f"{path}.lines", False):
                lp = f"{path}.lines[{j}]"
                if obj(line, lp, ("id", "speaker_id", "text"), ("speech_text",)):
                    identifier(line.get("id"), f"{lp}.id")
                    identifier(line.get("speaker_id"), f"{lp}.speaker_id")
                    string(line.get("text"), f"{lp}.text")
                    if "speech_text" in line:
                        string(line["speech_text"], f"{lp}.speech_text")
    state(data.get("initial_state"), "$.initial_state")
    for i, shot in items(data.get("shots"), "$.shots"):
        path = f"$.shots[{i}]"
        fields = ("id", "beat_ids", "duration_ms", "location", "time", "character_ids", "framing", "action", "emotion", "state_before", "state_after", "lines")
        if not obj(shot, path, fields):
            continue
        identifier(shot.get("id"), f"{path}.id")
        integer(shot.get("duration_ms"), f"{path}.duration_ms", 1)
        for key in ("location", "time", "framing", "action", "emotion"):
            string(shot.get(key), f"{path}.{key}")
        strings(shot.get("beat_ids"), f"{path}.beat_ids", True)
        strings(shot.get("character_ids"), f"{path}.character_ids")
        for key in ("state_before", "state_after"):
            state(shot.get(key), f"{path}.{key}")
        for j, line in items(shot.get("lines"), f"{path}.lines", False):
            lp = f"{path}.lines[{j}]"
            if obj(line, lp, ("line_id", "delivery", "start_ms", "end_ms")):
                identifier(line.get("line_id"), f"{lp}.line_id")
                if line.get("delivery") not in ("on_screen", "off_screen", "voiceover"):
                    error("E001", f"{lp}.delivery", "须为 on_screen、off_screen 或 voiceover")
                integer(line.get("start_ms"), f"{lp}.start_ms")
                integer(line.get("end_ms"), f"{lp}.end_ms", 1)
    if findings:
        return findings  # Do not perform semantic checks on structurally invalid data.

    def unique(values, path):
        for value, count in Counter(values).items():
            if count > 1:
                error("E002", path, f"重复标识或术语：{value}")

    chars = {x["id"]: x for x in data["characters"]}
    beats = {x["id"]: x for x in data["beats"]}
    all_lines = [x for beat in data["beats"] for x in beat["lines"]]
    lines = {x["id"]: x for x in all_lines}
    unique([x["id"] for x in data["characters"]], "$.characters")
    unique([x["name"] for x in data["characters"]], "$.characters")
    unique([x["id"] for x in data["beats"]], "$.beats")
    unique([x["id"] for x in all_lines], "$.beats.lines")
    unique([x["id"] for x in data["shots"]], "$.shots")
    unique([x["term"] for x in data["pronunciation_lexicon"]], "$.pronunciation_lexicon")
    terms = {x["term"] for x in data["pronunciation_lexicon"]}
    for char in data["characters"]:
        if char["name"] not in terms:
            error("E003", "$.pronunciation_lexicon", f"缺少角色完整姓名的读音：{char['name']}")
        if not char.get("reference_image"):
            warn("W001", f"characters.{char['id']}", "未提供角色参考图；文字设定不能替代参考图")
    for line in all_lines:
        if line["speaker_id"] not in chars:
            error("E004", f"lines.{line['id']}", f"未知说话人：{line['speaker_id']}；旁白也需登记角色")
        if line.get("speech_text", line["text"]) != line["text"]:
            warn("W002", f"lines.{line['id']}", "配音文本与字幕不同，请人工确认没有改写含义或错误替名")
    current = data["initial_state"]
    seen_beats, seen_lines = set(), []
    beat_order = {beat["id"]: i for i, beat in enumerate(data["beats"])}
    previous_beat = -1
    for shot in data["shots"]:
        path = f"shots.{shot['id']}"
        for char_id in shot["character_ids"]:
            if char_id not in chars:
                error("E004", path, f"未知画面角色：{char_id}")
        allowed_lines = set()
        for beat_id in shot["beat_ids"]:
            if beat_id not in beats:
                error("E004", path, f"未知剧情节拍：{beat_id}")
                continue
            seen_beats.add(beat_id)
            allowed_lines.update(x["id"] for x in beats[beat_id]["lines"])
            if beat_order[beat_id] < previous_beat:
                error("E005", path, "剧情节拍倒序；0.1 需先在原剧本中显式编排闪回")
            previous_beat = beat_order[beat_id]
        for state_key in ("state_before", "state_after"):
            if shot[state_key].keys() != data["initial_state"].keys():
                error("E006", f"{path}.{state_key}", "状态键必须与 initial_state 完全一致")
        if shot["state_before"] != current:
            error("E006", f"{path}.state_before", "与上一镜头结束状态不一致（首镜头应与 initial_state 一致）")
        current = shot["state_after"]
        previous_end = 0
        for line in shot["lines"]:
            lp = f"{path}.lines.{line['line_id']}"
            line_id = line["line_id"]
            seen_lines.append(line_id)
            if line_id not in lines:
                error("E004", lp, "引用了不存在的台词")
            elif line_id not in allowed_lines:
                error("E007", lp, "台词不属于本镜头引用的剧情节拍")
            elif line["delivery"] == "on_screen" and lines[line_id]["speaker_id"] not in shot["character_ids"]:
                error("E008", lp, "画面内说话人不在出场角色中；画外音请显式设置 off_screen/voiceover")
            if not (0 <= line["start_ms"] < line["end_ms"] <= shot["duration_ms"]):
                error("E009", lp, "台词时间必须在镜头内，且开始早于结束")
            if line["start_ms"] < previous_end:
                error("E009", lp, "0.1 的单字幕轨不支持台词重叠或倒序")
            previous_end = line["end_ms"]
            if line_id in lines and line["end_ms"] > line["start_ms"]:
                count = len(re.sub(r"[\s，。！？、；：,.!?;:…“”\"'（）()]", "", lines[line_id].get("speech_text", lines[line_id]["text"])))
                cps = count * 1000 / (line["end_ms"] - line["start_ms"])
                if cps > project.get("dialogue_cps_warning", 6.0):
                    warn("W003", lp, f"计划语速约 {cps:.1f} 字符/秒，建议试听后调整；这不是实测时长")
    for beat_id in sorted(beats.keys() - seen_beats):
        error("E010", "$.shots", f"剧情节拍未覆盖：{beat_id}")
    unique(seen_lines, "$.shots.lines")
    for line_id in sorted(lines.keys() - set(seen_lines)):
        error("E010", "$.shots.lines", f"原剧本台词未分配镜头：{line_id}")
    if set(seen_lines) == lines.keys() and len(set(seen_lines)) == len(seen_lines):
        if seen_lines != [line["id"] for line in all_lines]:
            error("E005", "$.shots.lines", "台词次序与原剧本不同，请显式修改原剧本顺序")
    return findings
