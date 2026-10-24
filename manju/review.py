"""Hash-bound human review records for a frozen planning bundle."""

from datetime import datetime
from pathlib import Path
import re

from .io import digest, inside, read_json
from .project import load_episode
from .validation import Finding, validate


CHECKS = ("pronunciation", "visual", "story", "timing")


def load_bundle(directory):
    directory = Path(directory)
    manifest = read_json(directory / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != "0.1":
        raise ValueError("不支持的构建清单")
    files = manifest.get("files")
    if not isinstance(files, dict) or "episode.snapshot.json" not in files:
        raise ValueError("构建清单缺少文件索引或剧本快照")
    for name, expected in files.items():
        path = inside(directory, name)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"构建文件摘要无效：{name}")
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"构建文件缺失或已修改：{name}；请重新构建并复审")
    data = read_json(directory / "episode.snapshot.json")
    if any(x.level == "error" for x in validate(data)):
        raise ValueError("构建快照不符合剧本契约")
    expected_shots = []
    offset = 0
    for shot in data["shots"]:
        expected_shots.append({"id": shot["id"], "has_dialogue": bool(shot["lines"]), "start_ms": offset, "duration_ms": shot["duration_ms"]})
        offset += shot["duration_ms"]
    if manifest.get("shots") != expected_shots:
        raise ValueError("构建清单与剧本快照的镜头或时长不一致")
    required = {"episode.snapshot.json", "voice_plan.json", "tasks.json", "subtitles.preview.srt"}
    required.update(f"shots/{shot['id']}.md" for shot in data["shots"])
    if not required <= files.keys():
        raise ValueError("构建清单遗漏必需的计划产物")
    return manifest


def review_template(directory):
    directory = Path(directory)
    manifest = load_bundle(directory)
    return {
        "review_version": "0.1",
        "manifest_sha256": digest(directory / "manifest.json"),
        "shots": [
            {
                "shot_id": shot["id"], "reviewer": "", "reviewed_at": "",
                "checks": {key: {"status": "pending", "note": ""} for key in CHECKS},
                "artifacts": [
                    {"kind": kind, "path": f"media/{shot['id']}.{'mp4' if kind == 'video' else 'wav'}", "sha256": ""}
                    for kind in (["video", "audio"] if shot["has_dialogue"] else ["video"])
                ],
            }
            for shot in manifest["shots"]
        ],
    }


def gate(directory, review_path, source=None):
    directory = Path(directory)
    findings = []

    def error(path, message):
        findings.append(Finding("error", "G001", path, message))

    try:
        manifest = load_bundle(directory)
    except (OSError, ValueError) as exc:
        error("manifest", str(exc))
        return findings
    if source is not None:
        _, input_hashes = load_episode(source)
        if input_hashes != manifest.get("input_hashes"):
            error("source", "当前源剧本或共享设定已改变，请重新构建并复审")
    review = read_json(review_path)
    if not isinstance(review, dict) or review.get("review_version") != "0.1":
        error("review", "不支持的复核记录版本")
        return findings
    if review.get("manifest_sha256") != digest(directory / "manifest.json"):
        error("review.manifest_sha256", "复核记录属于另一次构建，或清单已修改")
    records = review.get("shots")
    if not isinstance(records, list):
        error("review.shots", "须为镜头复核记录数组")
        return findings
    expected = {x["id"]: x for x in manifest["shots"]}
    seen = set()
    for index, record in enumerate(records):
        path = f"review.shots[{index}]"
        if not isinstance(record, dict):
            error(path, "须为对象")
            continue
        shot_id = record.get("shot_id")
        if not isinstance(shot_id, str) or shot_id not in expected or shot_id in seen:
            error(path, "未知或重复的镜头 ID")
            continue
        seen.add(shot_id)
        if not isinstance(record.get("reviewer"), str) or not record["reviewer"].strip():
            error(path, "缺少实际复核人")
        try:
            reviewed_at = record.get("reviewed_at")
            if not isinstance(reviewed_at, str):
                raise ValueError()
            parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            if parsed.utcoffset() is None:
                raise ValueError()
        except (ValueError, TypeError):
            error(path, "reviewed_at 须为带时区的 ISO 8601 时间")
        checks = record.get("checks")
        if not isinstance(checks, dict) or set(checks) != set(CHECKS):
            error(path, "须逐项复核 pronunciation、visual、story、timing")
        else:
            for key in CHECKS:
                check = checks[key]
                if not isinstance(check, dict):
                    error(f"{path}.{key}", "检查项须含 status 与 note")
                    continue
                accepted = {"pass"}
                if key == "pronunciation" and not expected[shot_id]["has_dialogue"]:
                    accepted.add("not_applicable")
                if not isinstance(check.get("status"), str) or check["status"] not in accepted:
                    error(f"{path}.{key}", "尚未通过人工复核")
                if not isinstance(check.get("note"), str) or not check["note"].strip():
                    error(f"{path}.{key}", "须填写具体检查证据或结论说明")
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, list):
            error(path, "缺少媒体产物数组")
            continue
        kinds = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                error(path, "媒体产物须为对象")
                continue
            kind = artifact.get("kind")
            if kind not in ("audio", "video"):
                error(path, "产物种类须为 audio 或 video")
                continue
            kinds.append(kind)
            try:
                artifact_path = inside(directory, artifact.get("path"))
                if not artifact_path.is_file() or digest(artifact_path) != artifact.get("sha256"):
                    error(path, f"{kind} 文件缺失或 SHA-256 不匹配；需要复审实际媒体")
            except (OSError, ValueError) as exc:
                error(path, str(exc))
        required_kinds = ["audio", "video"] if expected[shot_id]["has_dialogue"] else ["video"]
        if sorted(kinds) != required_kinds:
            error(path, "每个镜头须绑定一个 video，有对白时还须绑定一个 audio")
    for shot_id in sorted(expected.keys() - seen):
        error("review.shots", f"缺少镜头复核：{shot_id}")
    return findings
