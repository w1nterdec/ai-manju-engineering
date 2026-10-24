"""Local media measurements and phrase-level alignment; no generation/network calls."""
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import wave

from .build import timestamp
from .io import digest, inside, read_json
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
                result.update(status="measured", backend="stdlib.wave", duration_ms=round(Fraction(audio.getnframes() * 1000, audio.getframerate())), streams=[{"codec_type": "audio", "sample_rate": audio.getframerate(), "channels": audio.getnchannels()}])
                return result
        except (wave.Error, EOFError):
            pass
    executable = ffprobe or shutil.which("ffprobe")
    if not executable:
        result["reason"] = "未安装可选 ffprobe；无法自动确认视频技术规格，不能视为通过"
        return result
    try:
        process = subprocess.run([str(executable), "-v", "error", "-show_format", "-show_streams", "-output_format", "json", str(path)], capture_output=True, timeout=20, text=True, encoding="utf-8")
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
    report = {"alignment_version": "1.0", "mock": bool(mapping.get("mock", False)), "manifest_sha256": digest(bundle / "manifest.json"), "timeline": timeline, "measurements": measurements, "duration_ms": offset, "limitations": "按逐句音频长度重排，非字级强制对齐；不验证读音、口型或视频重定时是否完成。"}
    atomic_json(output / "alignment.json", report)
    return report


def asr_screen(expected, transcript):
    if not isinstance(expected, str) or not isinstance(transcript, str):
        raise ValueError("目标台词和转写须为字符串")
    return {"screen_version": "1.0", "matches": expected == transcript, "similarity": SequenceMatcher(None, expected, transcript).ratio(), "requires_pronunciation_review": True, "limitations": "仅筛查已提供转写的文本偏差；ASR 可能纠回错误读音，同音字和多音字仍须人工试听。"}


def quality_report(bundle, review_path=None, config=None, run=None):
    bundle = Path(bundle)
    manifest = load_bundle(bundle)
    human_findings = gate(bundle, review_path) if review_path else []
    human = "recorded_pass" if review_path and not human_findings else "pending_or_failed"
    measurements, issues = [], []
    if review_path:
        review = read_json(review_path)
        for shot in review.get("shots", []):
            for artifact in shot.get("artifacts", []):
                try:
                    measured = probe(inside(bundle, artifact["path"]))
                    measured.update(shot_id=shot["shot_id"], kind=artifact["kind"])
                    measurements.append(measured)
                    if measured["status"] != "measured":
                        issues.append(f"{shot['shot_id']}: 媒体未实测通过")
                        continue
                    kinds = {stream["codec_type"] for stream in measured["streams"]}
                    if artifact["kind"] not in kinds:
                        issues.append(f"{shot['shot_id']}: 实际流类型与记录不匹配")
                    planned = next(item for item in manifest["shots"] if item["id"] == shot["shot_id"])
                    tolerance = (config or {}).get("media_spec", {}).get("duration_tolerance_ms", 250)
                    if artifact["kind"] == "video" and abs(measured["duration_ms"] - planned["duration_ms"]) > tolerance:
                        issues.append(f"{shot['shot_id']}: 视频与计划时长不一致")
                    specification = (config or {}).get("media_spec", {})
                    for stream in measured["streams"]:
                        if stream["codec_type"] == "video":
                            for key in ("width", "height", "fps"):
                                if key in specification and str(stream.get(key)) != str(specification[key]):
                                    issues.append(f"{shot['shot_id']}: {key} 与交付规格不同")
                            if specification.get("require_audio") and "audio" not in kinds:
                                issues.append(f"{shot['shot_id']}: 缺少要求的内嵌音轨")
                except (OSError, ValueError, KeyError, StopIteration) as exc:
                    issues.append(redact(str(exc)))
    else:
        issues.append("未提供实际媒体人工审核记录")
    mock = bool(read_json(Path(run) / "status.json").get("mock")) if run else False
    return {"quality_version": "1.0", "manifest_sha256": digest(bundle / "manifest.json"), "review_sha256": digest(review_path) if review_path else None, "mock": mock, "automatic": {"passed": bool(measurements) and not issues, "issues": issues, "measurements": measurements}, "human": {"status": human, "findings": [item.to_dict() for item in human_findings]}, "metrics": {"first_pass_rate": None, "average_rework": None, "identity_human_score": None, "pronunciation_errors": None}, "production_ready": not mock and bool(measurements) and not issues and human == "recorded_pass", "notice": "技术规格通过与人工记录分开；不自动证明语义、读音或法律授权。"}
