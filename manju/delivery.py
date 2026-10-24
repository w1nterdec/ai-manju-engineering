"""Portable handoff manifests and fail-closed production delivery packages."""
import csv
import html
import json
from pathlib import Path
import shutil
import tempfile

from .assets import identity_report, lineage
from .io import digest, digest_bytes, inside, read_json
from .media import probe, quality_report
from .review import load_bundle
from .safeio import atomic_json, redact


def handoff(bundle, output, alignment=None):
    bundle, output = Path(bundle), Path(output)
    manifest = load_bundle(bundle)
    if output.exists():
        raise ValueError("剪辑交接目录已存在")
    aligned = read_json(Path(alignment) / "alignment.json") if alignment else None
    if aligned and aligned["manifest_sha256"] != digest(bundle / "manifest.json"):
        raise ValueError("对齐记录不属于本构建")
    timeline = aligned["timeline"] if aligned else [{"shot_id": shot["id"], "start_ms": shot["start_ms"], "duration_ms": shot["duration_ms"]} for shot in manifest["shots"]]
    output.mkdir(parents=True)
    with (output / "timeline.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["shot_id", "start_ms", "duration_ms", "end_ms"])
        for shot in timeline:
            writer.writerow([shot["shot_id"], shot["start_ms"], shot["duration_ms"], shot["start_ms"] + shot["duration_ms"]])
    subtitle = Path(alignment) / "subtitles.measured.srt" if aligned else bundle / "subtitles.preview.srt"
    shutil.copyfile(subtitle, output / "subtitles.srt")
    result = {"handoff_version": "1.0", "manifest_sha256": digest(bundle / "manifest.json"), "timeline": timeline, "timing_basis": "measured_audio" if aligned else "planned_preview", "notice": "通用 JSON/CSV/SRT 交接，不是特定剪辑软件工程文件；需在目标软件核对导入与重定时。"}
    atomic_json(output / "handoff.json", result)
    return result


def _provenance(bundle, review_path, provenance_path, final, rights):
    record = read_json(provenance_path)
    if not isinstance(record, dict) or record.get("provenance_version") != "1.0" or redact(record) != record:
        raise ValueError("需提供不含凭据的 provenance_version 1.0 实际制作记录")
    if record.get("manifest_sha256") != digest(Path(bundle) / "manifest.json"):
        raise ValueError("制作来源记录与构建不匹配")
    review = read_json(review_path)
    supplied = record.get("shots")
    if not isinstance(supplied, dict) or set(supplied) != {shot["shot_id"] for shot in review["shots"]}:
        raise ValueError("制作来源须完整覆盖实际审核镜头")
    approved_assets = {asset["asset_id"] for asset in rights["assets"]}
    for shot in review["shots"]:
        source = supplied[shot["shot_id"]]
        if not isinstance(source, dict) or not all(isinstance(source.get(key), str) and source[key].strip() for key in ("provider", "model", "prompt_sha256")) or not isinstance(source.get("parameters"), dict):
            raise ValueError("逐镜头来源缺少实际 provider/model/parameters/prompt_sha256")
        if source.get("source_prompt_sha256") != digest(Path(bundle) / "shots" / f"{shot['shot_id']}.md"):
            raise ValueError("制作记录未关联批准的镜头说明")
        actual_prompt = source.get("prompt")
        if not isinstance(actual_prompt, str) or not actual_prompt.strip() or digest_bytes(actual_prompt.encode("utf-8")) != source["prompt_sha256"]:
            raise ValueError("需保留实际提交的提示词及其正确摘要")
        asset_ids = source.get("input_asset_ids")
        if not isinstance(asset_ids, list) or not asset_ids or not set(asset_ids) <= approved_assets:
            raise ValueError("实际制作来源须引用已通过授权检查的素材")
        for artifact in shot["artifacts"]:
            if source.get(f"{artifact['kind']}_sha256") != artifact["sha256"]:
                raise ValueError("来源记录与实际审核媒体摘要不同")
    final_record = record.get("final")
    if not isinstance(final_record, dict) or final_record.get("sha256") != digest(final) or not all(isinstance(final_record.get(key), str) and final_record[key].strip() for key in ("editor", "tool")):
        raise ValueError("最终成片缺少对应文件摘要、剪辑负责人或工具记录")
    return record


def package(bundle, output, config, *, run=None, demo=False, review=None, final=None, alignment=None, provenance=None, include_costs=False):
    bundle, output = Path(bundle), Path(output)
    manifest = load_bundle(bundle)
    if output.exists():
        raise ValueError("交付目录已存在，禁止覆盖旧交付版本")
    rights = identity_report(read_json(bundle / "episode.snapshot.json"), config, production=not demo)
    quality = quality_report(bundle, review, config, run)
    source_record = None
    if not demo:
        if not all((review, final, alignment, provenance)):
            raise ValueError("生产打包缺少 --review、--final、--alignment 或 --provenance")
        if not rights["passed"]:
            raise ValueError("授权记录门禁失败：" + "; ".join(rights["problems"]))
        if not quality["production_ready"]:
            raise ValueError("实际媒体的技术检查和人工复核未全部通过；mock 不可生产交付")
        aligned = read_json(Path(alignment) / "alignment.json")
        if aligned.get("mock") or aligned.get("manifest_sha256") != digest(bundle / "manifest.json"):
            raise ValueError("对齐结果仍为 mock 或属于旧构建")
        measured = probe(final)
        if measured["status"] != "measured" or not any(stream["codec_type"] == "video" for stream in measured["streams"]) or abs(measured["duration_ms"] - aligned["duration_ms"]) > config.get("media_spec", {}).get("duration_tolerance_ms", 250):
            raise ValueError("最终成片尚未通过实测或与实际时间轴不符")
        label = config.get("ai_label")
        if not isinstance(label, dict) or not all(isinstance(label.get(key), str) and label[key].strip() for key in ("platform", "disclosure", "verified_by", "as_of", "source_url")):
            raise ValueError("缺少经使用者核实的 AI 内容标识元数据")
        source_record = _provenance(bundle, review, provenance, final, rights)
    elif run is None:
        raise ValueError("演示包须提供 mock --run")
    trace = None
    if run:
        trace = lineage(bundle, run, "edit:episode")
        if any(row is None or row["state"] != "succeeded" for row in trace["results"].values()):
            raise ValueError("运行尚未完整结束，不能打包")
        status = read_json(Path(run) / "status.json")
        if demo and not status.get("mock"):
            raise ValueError("演示模式仅接受 mock 运行")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".package-", dir=output.parent) as temporary:
        stage = Path(temporary) / "package"
        stage.mkdir()
        handoff(bundle, stage / "handoff", alignment)
        for name in ("manifest.json", "episode.snapshot.json", "voice_plan.json", "tasks.json"):
            destination = stage / "source" / name
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(bundle / name, destination)
        shutil.copytree(bundle / "shots", stage / "source/shots")
        atomic_json(stage / "quality.json", quality)
        atomic_json(stage / "rights-summary.json", rights)
        atomic_json(stage / "ai-label.json", {"mode": "demo" if demo else "production", "label": config.get("ai_label"), "notice": "以所在地区及投放平台最新要求为准，由使用者核实；本记录不是法律结论。"})
        if source_record:
            atomic_json(stage / "provenance.json", source_record)
        if review:
            media_index = []
            for shot in read_json(review)["shots"]:
                for artifact in shot["artifacts"]:
                    path = inside(bundle, artifact["path"])
                    if not path.is_file() or digest(path) != artifact["sha256"]:
                        raise ValueError("打包时实际审核媒体发生变化")
                    relative = f"reviewed-media/{artifact['sha256']}{path.suffix.lower()}"
                    destination = stage / relative
                    destination.parent.mkdir(exist_ok=True)
                    shutil.copyfile(path, destination)
                    media_index.append({"shot_id": shot["shot_id"], "kind": artifact["kind"], "path": relative, "sha256": artifact["sha256"]})
            atomic_json(stage / "reviewed-media-index.json", media_index)
            shutil.copyfile(review, stage / "human-review.json")
        if trace:
            atomic_json(stage / "lineage.json", trace)
            for task in trace["results"].values():
                result = json.loads(task["result"])
                for key in ("path", "media_path"):
                    if key in result:
                        path = inside(Path(run) / "artifacts", result[key])
                        destination = stage / "media" / path.name
                        destination.parent.mkdir(exist_ok=True)
                        shutil.copyfile(path, destination)
            shutil.copyfile(Path(run) / "events.json", stage / "rework-events.json")
            if include_costs:
                shutil.copyfile(Path(run) / "cost-report.json", stage / "costs.json")
        if final:
            (stage / "final").mkdir()
            shutil.copyfile(final, stage / "final" / (digest(final) + Path(final).suffix.lower()))
        mode = "MOCK DEMO — 不得作为成片或客户验收" if demo else "生产交付记录包 — 仍须客户验收"
        files = sorted(path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_file())
        page = "<!doctype html><meta charset='utf-8'><title>交付记录</title><h1>" + html.escape(mode) + "</h1><p>授权与 AI 标识仅为记录检查，以最新地区和平台要求为准。</p><ul>" + "".join(f"<li>{html.escape(name)}</li>" for name in files) + "</ul><p>成本默认不附；修改与任务事件见 rework-events.json（如有）。</p>"
        (stage / "report.html").write_text(page, encoding="utf-8")
        index = {path.relative_to(stage).as_posix(): digest(path) for path in sorted(stage.rglob("*")) if path.is_file()}
        result = {"package_version": "1.0", "mode": "demo" if demo else "production", "production_ready": not demo, "source_manifest_sha256": digest(bundle / "manifest.json"), "files": index, "notice": mode}
        atomic_json(stage / "package-manifest.json", result)
        stage.rename(output)
    return result


def verify_package(directory):
    directory = Path(directory)
    manifest = read_json(directory / "package-manifest.json")
    if not isinstance(manifest, dict) or manifest.get("package_version") != "1.0" or manifest.get("mode") not in ("demo", "production") or not isinstance(manifest.get("files"), dict) or not manifest["files"]:
        raise ValueError("不支持或不完整的交付清单")
    problems = []
    for name, expected in manifest["files"].items():
        path = inside(directory, name)
        if not path.is_file() or digest(path) != expected:
            problems.append(name)
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()} - {"package-manifest.json"}
    if actual != manifest["files"].keys():
        problems.append("清单外新增或遗漏文件")
    return {"passed": not problems, "mode": manifest["mode"], "problems": problems, "notice": "仅完整性校验；摘要不提供来源身份签名或法律保证。"}
