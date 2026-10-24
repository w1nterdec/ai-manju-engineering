"""Compile a reviewed editorial plan into deterministic, provider-neutral assets."""

import json
from pathlib import Path
from string import Template
import tempfile

from . import __version__
from .io import digest, digest_bytes, write_json
from .project import load_episode
from .validation import validate


ROOT = Path(__file__).resolve().parent.parent


def timestamp(ms):
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def compile_episode(source, destination):
    source, destination = Path(source), Path(destination)
    data, input_hashes = load_episode(source)
    findings = validate(data)
    if any(x.level == "error" for x in findings):
        raise ValueError("剧本检查失败，请先运行 check 并修复错误")
    if destination.exists():
        raise ValueError(f"输出目录已存在：{destination}；请为新版本选择新目录")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Construct privately and rename only after every output has been written.
    with tempfile.TemporaryDirectory(prefix=".manju-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "bundle"
        stage.mkdir()
        (stage / "shots").mkdir()
        template_path = ROOT / "prompts" / "shot.md.tmpl"
        template_bytes = template_path.read_bytes()
        template = Template(template_bytes.decode("utf-8"))
        chars = {x["id"]: x for x in data["characters"]}
        beats = {x["id"]: x for x in data["beats"]}
        lines = {x["id"]: x for beat in data["beats"] for x in beat["lines"]}
        voice_plan, subtitles, tasks, manifest_shots = [], [], [], []
        offset, number = 0, 1
        for shot in data["shots"]:
            cast = []
            for cid in shot["character_ids"]:
                char = chars[cid]
                cast.append(f"- {cid} / {char['name']}：{char['appearance']}\n  参考图：{char.get('reference_image') or '待补充并上传，当前没有参考图'}")
            required_facts = [fact for bid in shot["beat_ids"] for fact in beats[bid]["required_facts"]]
            dialogue = []
            audio_tasks = []
            for cue in shot["lines"]:
                line = lines[cue["line_id"]]
                speaker = chars[line["speaker_id"]]
                speech = line.get("speech_text", line["text"])
                lexicon = [x for x in data["pronunciation_lexicon"] if x["term"] in speech]
                absolute_start = offset + cue["start_ms"]
                absolute_end = offset + cue["end_ms"]
                voice_plan.append({
                    "line_id": line["id"], "shot_id": shot["id"],
                    "speaker_id": speaker["id"], "speaker_name": speaker["name"],
                    "provider": None, "voice_id": None,
                    "voice_direction": speaker["voice_direction"],
                    "display_text": line["text"], "speech_text": speech,
                    "pronunciation_hints": lexicon, "delivery": cue["delivery"],
                    "planned_start_ms": absolute_start, "planned_end_ms": absolute_end,
                    "status": "not_synthesized", "pronunciation_review": "pending",
                })
                subtitles.append(f"{number}\n{timestamp(absolute_start)} --> {timestamp(absolute_end)}\n{line['text']}\n")
                number += 1
                dialogue.append(f"- {line['id']} / {speaker['name']} / {cue['delivery']}：{line['text']}")
                task_id = f"tts:{line['id']}"
                audio_tasks.append(task_id)
                tasks.append({"id": task_id, "kind": "tts", "depends_on": [], "status": "planned"})
            shot_text = template.substitute(
                shot_id=shot["id"], aspect_ratio=data["project"]["aspect_ratio"],
                visual_style=data["project"]["visual_style"], duration_ms=shot["duration_ms"],
                canon_facts="\n".join(f"- {x}" for x in data["project"]["canon_facts"]),
                cast="\n".join(cast) or "- 本镜头无人出场",
                location=shot["location"], time=shot["time"], framing=shot["framing"],
                action=shot["action"], emotion=shot["emotion"],
                state_before=json.dumps(shot["state_before"], ensure_ascii=False, indent=2),
                state_after=json.dumps(shot["state_after"], ensure_ascii=False, indent=2),
                required_facts="\n".join(f"- {x}" for x in required_facts),
                dialogue="\n".join(dialogue) or "- 无对白",
                negative_prompt=data["project"]["negative_prompt"],
            )
            (stage / "shots" / f"{shot['id']}.md").write_text(shot_text, encoding="utf-8")
            image_task, video_task = f"image:{shot['id']}", f"video:{shot['id']}"
            tasks.extend([
                {"id": image_task, "kind": "image", "depends_on": [], "status": "planned"},
                {"id": video_task, "kind": "video", "depends_on": [image_task], "status": "planned"},
                {"id": f"review:{shot['id']}", "kind": "human_review", "depends_on": [video_task] + audio_tasks, "status": "planned"},
            ])
            manifest_shots.append({"id": shot["id"], "has_dialogue": bool(shot["lines"]), "start_ms": offset, "duration_ms": shot["duration_ms"]})
            offset += shot["duration_ms"]
        tasks.append({"id": "edit:episode", "kind": "edit", "depends_on": [f"review:{s['id']}" for s in data["shots"]], "status": "planned"})
        write_json(stage / "episode.snapshot.json", data)
        write_json(stage / "voice_plan.json", voice_plan)
        write_json(stage / "tasks.json", tasks)
        (stage / "subtitles.preview.srt").write_text("\n".join(subtitles), encoding="utf-8")
        files = {x.relative_to(stage).as_posix(): digest(x) for x in sorted(stage.rglob("*")) if x.is_file()}
        manifest = {
            "manifest_version": "0.1", "tool_version": __version__, "status": "planning_only",
            "project_id": data["project"]["id"], "source_sha256": input_hashes["episode"],
            "input_hashes": input_hashes,
            "template_sha256": digest_bytes(template_bytes), "planned_duration_ms": offset,
            "shots": manifest_shots, "files": files,
            "limitations": ["未调用模型，未生成音视频", "字幕为计划时间，须由实测音频重新对齐", "文本检查不能证明成片质量"],
        }
        write_json(stage / "manifest.json", manifest)
        stage.rename(destination)
    return manifest


def init_episode(destination):
    destination = Path(destination)
    # Exclusive creation prevents accidentally replacing an existing project.
    with destination.open("x", encoding="utf-8") as stream:
        stream.write((ROOT / "examples" / "midnight_letter" / "episode.json").read_text(encoding="utf-8"))
