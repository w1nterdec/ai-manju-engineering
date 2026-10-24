"""Local media measurements and phrase-level alignment; no generation/network calls."""
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import wave
import re

from .build import timestamp
from .io import digest, digest_bytes, inside, read_json
from .review import gate, load_bundle
from .safeio import atomic_json, redact


def probe(path, ffprobe=None):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("媒体文件不存在")
    result = {"probe_version": "1.0", "sha256": digest(path), "status": "unavailable", "duration_ms": None, "streams": []}
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as audio:
                remaining = audio.getnframes()
                frame_size = audio.getnchannels() * audio.getsampwidth()
                while remaining:
                    frames = min(remaining, 65536)
                    if len(audio.readframes(frames)) != frames * frame_size:
                        raise wave.Error("PCM 数据被截断")
                    remaining -= frames
                result.update(status="measured", backend="stdlib.wave", duration_ms=round(Fraction(audio.getnframes() * 1000, audio.getframerate())), streams=[{"codec_type": "audio", "sample_rate": audio.getframerate(), "channels": audio.getnchannels()}])
                return result
        except (wave.Error, EOFError):
            pass
    executable = ffprobe or shutil.which("ffprobe")
    if not executable:
        result["reason"] = "未安装可选 ffprobe；无法自动确认视频技术规格，不能视为通过"
        return result
    try:
        process = subprocess.run([str(executable), "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-output_format", "json", str(path)], capture_output=True, timeout=20, text=True, encoding="utf-8")
        if process.returncode:
            raise ValueError("ffprobe 无法读取媒体")
        data = json.loads(process.stdout)
        duration = Decimal(str(data.get("format", {}).get("duration", "NaN")))
        if not duration.is_finite() or duration <= 0 or not isinstance(data.get("streams"), list):
            raise ValueError("媒体缺少有效实测时长或流信息")
        streams = []
        for stream in data["streams"]:
            normalized = {key: stream[key] for key in ("codec_type", "codec_name", "width", "height", "sample_rate", "channels") if key in stream}
            if stream.get("codec_type") == "video":
                try:
                    rate = Fraction(stream.get("avg_frame_rate", "0/0"))
                    normalized["fps"] = str(rate) if rate > 0 else None
                except (ValueError, ZeroDivisionError):
                    normalized["fps"] = None
            streams.append(normalized)
        result.update(status="measured", backend="ffprobe", duration_ms=round(duration * 1000), streams=streams)
    except (OSError, subprocess.TimeoutExpired, ValueError, InvalidOperation, TypeError) as exc:
        result.update(status="failed", reason=redact(str(exc)))
    return result


def align(bundle, audio_map_path, output):
    bundle, audio_map_path, output = Path(bundle), Path(audio_map_path), Path(output)
    load_bundle(bundle)
    if output.exists():
        raise ValueError("对齐输出目录已存在")
    mapping = read_json(audio_map_path)
    voices = {line["line_id"]: line for line in read_json(bundle / "voice_plan.json")}
    if not isinstance(mapping, dict) or mapping.get("audio_map_version") != "1.0" or not isinstance(mapping.get("lines"), dict) or set(mapping["lines"]) != set(voices):
        raise ValueError("audio_map_version 1.0 须为每句台词提供且仅提供一个本地音频路径")
    episode = read_json(bundle / "episode.snapshot.json")
    offset, number, subtitles, timeline = 0, 1, [], []
    measurements = {}
    for line_id, relative in mapping["lines"].items():
        measured = probe(inside(audio_map_path.parent, relative))
        if measured["status"] != "measured" or not measured["duration_ms"] or not any(stream["codec_type"] == "audio" for stream in measured["streams"]):
            raise ValueError(f"不能获得 {line_id} 的实测音频长度")
        measurements[line_id] = measured
    for shot in episode["shots"]:
        end, cues = 0, []
        for cue in shot["lines"]:
            line_id = cue["line_id"]
            start = max(cue["start_ms"], end)
            end = start + measurements[line_id]["duration_ms"]
            subtitles.append(f"{number}\n{timestamp(offset + start)} --> {timestamp(offset + end)}\n{voices[line_id]['display_text']}\n")
            number += 1
            cues.append({"line_id": line_id, "start_ms": offset + start, "end_ms": offset + end, "audio_sha256": measurements[line_id]["sha256"]})
        duration = max(shot["duration_ms"], end)
        timeline.append({"shot_id": shot["id"], "start_ms": offset, "duration_ms": duration, "requires_video_retiming": duration != shot["duration_ms"], "cues": cues})
        offset += duration
    output.mkdir(parents=True)
    with (output / "subtitles.measured.srt").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(subtitles))
    report = {"alignment_version": "1.0", "mock": bool(mapping.get("mock", False)), "manifest_sha256": digest(bundle / "manifest.json"), "timeline": timeline, "measurements": measurements, "duration_ms": offset, "subtitle_sha256": digest(output / "subtitles.measured.srt"), "limitations": "按逐句音频长度重排，非字级强制对齐；不验证读音、口型或视频重定时是否完成。"}
    atomic_json(output / "alignment.json", report)
    return report


def alignment_subtitles(bundle, report):
    voices = {line["line_id"]: line for line in read_json(Path(bundle) / "voice_plan.json")}
    subtitles = []
    for shot in report["timeline"]:
        for cue in shot["cues"]:
            subtitles.append(f"{len(subtitles) + 1}\n{timestamp(cue['start_ms'])} --> {timestamp(cue['end_ms'])}\n{voices[cue['line_id']]['display_text']}\n")
    return "\n".join(subtitles)


def validate_alignment(bundle, directory):
    bundle, directory = Path(bundle), Path(directory)
    load_bundle(bundle)
    report = read_json(directory / "alignment.json")
    if not isinstance(report, dict) or report.get("alignment_version") != "1.0" or type(report.get("mock")) is not bool:
        raise ValueError("对齐记录须为 alignment_version 1.0，包含明确的 mock 标志")
    if report.get("manifest_sha256") != digest(bundle / "manifest.json"):
        raise ValueError("对齐记录不属于本构建")
    episode = read_json(bundle / "episode.snapshot.json")
    timeline, measurements = report.get("timeline"), report.get("measurements")
    line_ids = {cue["line_id"] for shot in episode["shots"] for cue in shot["lines"]}
    if not isinstance(timeline, list) or len(timeline) != len(episode["shots"]):
        raise ValueError("对齐时间线必须完整覆盖全部镜头")
    if not isinstance(measurements, dict) or measurements.keys() != line_ids:
        raise ValueError("对齐测量必须完整覆盖全部台词")
    offset = 0
    for source, shot in zip(episode["shots"], timeline):
        if not isinstance(shot, dict) or shot.get("shot_id") != source["id"]:
            raise ValueError("对齐镜头 ID 或顺序与原剧本不同")
        start, duration = shot.get("start_ms"), shot.get("duration_ms")
        if type(start) is not int or start != offset or type(duration) is not int or duration < source["duration_ms"]:
            raise ValueError("对齐镜头时间不连续或短于计划")
        cues = shot.get("cues")
        expected_ids = [cue["line_id"] for cue in source["lines"]]
        if not isinstance(cues, list) or any(not isinstance(cue, dict) for cue in cues) or [cue.get("line_id") for cue in cues] != expected_ids:
            raise ValueError("对齐台词必须按原顺序完整覆盖镜头")
        previous_end = start
        for cue in cues:
            cue_start, cue_end = cue.get("start_ms"), cue.get("end_ms")
            measured = measurements[cue["line_id"]]
            if type(cue_start) is not int or type(cue_end) is not int or not previous_end <= cue_start < cue_end <= start + duration:
                raise ValueError("对齐台词时间越界、重叠或倒序")
            if not isinstance(measured, dict) or measured.get("status") != "measured" or type(measured.get("duration_ms")) is not int or measured["duration_ms"] != cue_end - cue_start:
                raise ValueError("台词时间与实测音频长度不同")
            sha = cue.get("audio_sha256")
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha) or measured.get("sha256") != sha:
                raise ValueError("对齐台词与实测音频摘要不同")
            previous_end = cue_end
        offset += duration
    if type(report.get("duration_ms")) is not int or report["duration_ms"] != offset:
        raise ValueError("对齐总时长与镜头时间线不同")
    expected = alignment_subtitles(bundle, report).encode("utf-8")
    if (directory / "subtitles.measured.srt").read_bytes() != expected:
        raise ValueError("字幕缺失或与对齐时间线、原文不一致")
    if "subtitle_sha256" in report and report["subtitle_sha256"] != digest_bytes(expected):
        raise ValueError("对齐字幕摘要不匹配")
    return report


def asr_screen(expected, transcript):
    if not isinstance(expected, str) or not isinstance(transcript, str):
        raise ValueError("目标台词和转写须为字符串")
    return {"screen_version": "1.0", "matches": expected == transcript, "similarity": SequenceMatcher(None, expected, transcript).ratio(), "requires_pronunciation_review": True, "limitations": "仅筛查已提供转写的文本偏差；ASR 可能纠回错误读音，同音字和多音字仍须人工试听。"}


def quality_report(bundle, review_path=None, config=None, run=None, alignment=None):
    bundle = Path(bundle)
    manifest = load_bundle(bundle)
    aligned = validate_alignment(bundle, alignment) if alignment else None
    durations = {shot["shot_id"]: shot["duration_ms"] for shot in aligned["timeline"]} if aligned else {shot["id"]: shot["duration_ms"] for shot in manifest["shots"]}
    human_findings = gate(bundle, review_path) if review_path else []
    human = "recorded_pass" if review_path and not human_findings else "pending_or_failed"
    measurements, issues = [], []
    if review_path:
        review = read_json(review_path)
        records = review.get("shots", []) if isinstance(review, dict) else []
        if not isinstance(records, list):
            records = []
        for shot in records:
            if not isinstance(shot, dict) or not isinstance(shot.get("artifacts"), list):
                issues.append("人工复核记录结构无效")
                continue
            for artifact in shot.get("artifacts", []):
                try:
                    if not isinstance(artifact, dict):
                        raise ValueError("媒体记录结构无效")
                    measured = probe(inside(bundle, artifact["path"]))
                    measured.update(shot_id=shot["shot_id"], kind=artifact["kind"])
                    measurements.append(measured)
                    if measured["status"] != "measured":
                        issues.append(f"{shot['shot_id']}: 媒体未实测通过")
                        continue
                    kinds = {stream["codec_type"] for stream in measured["streams"]}
                    if artifact["kind"] not in kinds:
                        issues.append(f"{shot['shot_id']}: 实际流类型与记录不匹配")
                    expected_duration = durations[shot["shot_id"]]
                    tolerance = (config or {}).get("media_spec", {}).get("duration_tolerance_ms", 250)
                    if artifact["kind"] == "video" and abs(measured["duration_ms"] - expected_duration) > tolerance:
                        issues.append(f"{shot['shot_id']}: 视频与{'实测对齐' if aligned else '计划'}时长不一致")
                    specification = (config or {}).get("media_spec", {})
                    for stream in measured["streams"]:
                        if stream["codec_type"] == "video":
                            for key in ("width", "height", "fps"):
                                if key in specification:
                                    matches = Fraction(str(stream.get(key, "0"))) == Fraction(str(specification[key])) if key == "fps" else str(stream.get(key)) == str(specification[key])
                                    if not matches:
                                        issues.append(f"{shot['shot_id']}: {key} 与交付规格不同")
                            if specification.get("require_audio") and "audio" not in kinds:
                                issues.append(f"{shot['shot_id']}: 缺少要求的内嵌音轨")
                except (OSError, ValueError, KeyError, StopIteration) as exc:
                    issues.append(redact(str(exc)))
    else:
        issues.append("未提供实际媒体人工审核记录")
    mock = bool(aligned and aligned["mock"]) or (bool(read_json(Path(run) / "status.json").get("mock")) if run else False)
    return {"quality_version": "1.0", "manifest_sha256": digest(bundle / "manifest.json"), "review_sha256": digest(review_path) if review_path else None, "mock": mock, "automatic": {"passed": bool(measurements) and not issues, "issues": issues, "measurements": measurements}, "human": {"status": human, "findings": [item.to_dict() for item in human_findings]}, "metrics": {"first_pass_rate": None, "average_rework": None, "identity_human_score": None, "pronunciation_errors": None}, "production_ready": not mock and bool(measurements) and not issues and human == "recorded_pass", "notice": "技术规格通过与人工记录分开；不自动证明语义、读音或法律授权。"}
