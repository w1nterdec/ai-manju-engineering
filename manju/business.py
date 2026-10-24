"""Config-driven business profiles, parameterized costs and metadata-only exports."""
import copy
import csv
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from .adapters import load_config
from .build import ROOT, compile_episode
from .costs import money
from .execution import Engine
from .io import digest, inside, read_json
from .planning import make_plan
from .safeio import atomic_json, fingerprint, redact, run_lock


def load_profile(name):
    path = Path(name)
    if not path.is_file():
        if not isinstance(name, str) or any(c not in "abcdefghijklmnopqrstuvwxyz_" for c in name):
            raise ValueError("未知画像名称")
        path = ROOT / "configs/profiles" / f"{name}.json"
    data = read_json(path)
    required = {"profile_version", "id", "deliverables", "required_checks", "metrics", "include_labor", "templates"}
    if not isinstance(data, dict) or set(data) != required or data["profile_version"] != "1.0" or not isinstance(data["id"], str) or not data["id"]:
        raise ValueError("业务画像契约无效")
    for key in ("deliverables", "required_checks"):
        if not isinstance(data[key], list) or not data[key] or not all(isinstance(item, str) and item for item in data[key]):
            raise ValueError(f"画像 {key} 须为非空字符串数组")
    if type(data["include_labor"]) is not bool or not isinstance(data["templates"], dict) or not isinstance(data["metrics"], list):
        raise ValueError("画像模板、指标或人工成本开关无效")
    for name in data["templates"]:
        inside(Path.cwd(), name)
        if Path(name).name != name or not name.endswith(".json"):
            raise ValueError("模板名须为当前目录 JSON 文件")
    for metric in data["metrics"]:
        if not isinstance(metric, dict) or set(metric) != {"id", "denominator", "multiplier"} or metric["denominator"] not in ("accepted_seconds", "units", "episodes", "skus", "variants"):
            raise ValueError("画像成本指标无效")
        money(metric["multiplier"])
    return data


def new_project(name, output):
    profile, output = load_profile(name), Path(output)
    if output.exists():
        raise ValueError("项目目录已存在")
    config = load_config()
    config.update(business_profile=profile["id"], business_profile_config=profile, scope={"project": output.name, "batch": "default"})
    output.mkdir(parents=True)
    atomic_json(output / "profile.json", profile)
    atomic_json(output / "production.json", config)
    atomic_json(output / "project.json", {"project_version": "1.0", "business_profile": profile["id"], "episodes": ["episode.json"], "status": "mock_template", "deliverables": profile["deliverables"]})
    atomic_json(output / "delivery-checklist.json", {"checks_version": "1.0", "final_sha256": None, "checks": {key: {"status": "pending", "reviewer": None, "note": None} for key in profile["required_checks"]}})
    for filename, value in profile["templates"].items():
        atomic_json(output / filename, value)
    atomic_json(output / "episode.json", read_json(ROOT / "examples/midnight_letter/episode.json"))
    return {"profile": profile["id"], "out": str(output), "mock": True}


def unit_cost(profile, parameters):
    if not isinstance(parameters, dict) or redact(parameters) != parameters:
        raise ValueError("成本参数无效或包含凭据")
    if not isinstance(parameters.get("currency"), str) or not parameters["currency"].strip():
        raise ValueError("必须显式填写币种")
    cost = money(parameters.get("production_cost"))
    if profile["include_labor"]:
        cost += money(parameters.get("human_hours")) * money(parameters.get("hourly_cost"))
    buffer = money(parameters.get("rework_buffer"))
    margin = money(parameters.get("margin"))
    if buffer > 1 or margin >= 1:
        raise ValueError("返工缓冲须在 0..1，利润率须在 0..1（不含 1）")
    cost *= 1 + buffer
    price_value = cost / (1 - margin)
    metrics = {}
    for metric in profile["metrics"]:
        denominator = money(parameters.get(metric["denominator"]))
        if not denominator:
            raise ValueError("单位成本分母必须大于 0")
        metrics[metric["id"]] = str(cost * money(metric["multiplier"]) / denominator)
    return {"cost_model_version": "1.0", "profile": profile["id"], "currency": parameters.get("currency"), "parameters_sha256": fingerprint(parameters), "cost_with_buffer": str(cost), "calculated_quote": str(price_value), "unit_metrics": metrics, "example": bool(parameters.get("example", False)), "notice": "完全按使用者参数计算；不是市场价格、收入预测或盈利保证。"}


def business_checks(config, path, final):
    profile = config.get("business_profile_config") or load_profile(config.get("business_profile", "series_drama"))
    if path is None:
        raise ValueError("生产交付缺少画像特有检查记录 --business-checks")
    record = read_json(path)
    if not isinstance(record, dict) or record.get("checks_version") != "1.0" or record.get("final_sha256") != digest(final) or not isinstance(record.get("checks"), dict):
        raise ValueError("画像检查记录与最终成片不匹配")
    for key in profile["required_checks"]:
        check = record["checks"].get(key)
        if not isinstance(check, dict) or check.get("status") != "pass" or not all(isinstance(check.get(field), str) and check[field].strip() for field in ("reviewer", "note")):
            raise ValueError(f"画像检查未通过：{key}")
    return {"profile": profile, "record": record}


def batch(project, input_path, output, execute=False, auto_review_mock=False):
    project, input_path, output = Path(project), Path(input_path), Path(output)
    if output.exists():
        raise ValueError("批次输出已存在；请使用新版本，单项运行可独立恢复")
    config = load_config(project / "production.json")
    if input_path.suffix.lower() == ".csv":
        with input_path.open(encoding="utf-8-sig", newline="") as stream:
            items = list(csv.DictReader(stream))
    else:
        data = read_json(input_path)
        items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("批次输入须包含非空 items 或 CSV 数据行")
    output.mkdir(parents=True)
    jobs = []
    seen = set()
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict) or redact(item) != item or not all(isinstance(item.get(key), str) and item[key].strip() for key in ("sku", "product_name", "selling_point")):
                raise ValueError("商品项须包含 sku/product_name/selling_point，且不得包含凭据")
            hooks = item.get("hooks", [item.get("hook", "了解这款商品")])
            if not isinstance(hooks, list) or not hooks or not all(isinstance(hook, str) and hook.strip() for hook in hooks):
                raise ValueError("hooks 须为非空字符串列表")
            for hook in hooks:
                variant = fingerprint({"item": item, "hook": hook})
                if variant in seen:
                    raise ValueError("重复的商品/钩子变体")
                seen.add(variant)
                job = output / variant[:16]
                job.mkdir()
                episode = read_json(project / "episode.json")
                episode["project"].update(id="AD_" + variant[:16].upper(), title=item["product_name"])
                episode["characters"] = [episode["characters"][0]]
                episode["pronunciation_lexicon"] = [entry for entry in episode["pronunciation_lexicon"] if entry["term"] == episode["characters"][0]["name"]]
                episode["project"]["canon_facts"] = ["只表达输入商品资料，不自动补充性能、功效或承诺。"]
                episode["beats"] = [{"id": "B001", "summary": item["product_name"], "required_facts": [item["product_name"], item["selling_point"]], "lines": [{"id": "L001", "speaker_id": episode["characters"][0]["id"], "text": hook + "。" + item["selling_point"]}]}]
                shot = episode["shots"][0]
                shot.update(beat_ids=["B001"], character_ids=[], framing="商品展示，固定机位", action="展示用户提供的商品参考；不得改变 SKU 或擅加卖点。", emotion="清晰克制", location="商品展示场景", state_before={"product.sku": item["sku"]}, state_after={"product.sku": item["sku"]}, lines=[{"line_id": "L001", "delivery": "voiceover", "start_ms": 500, "end_ms": 7500}])
                episode["initial_state"] = {"product.sku": item["sku"]}
                episode["shots"] = [shot]
                atomic_json(job / "episode.json", episode)
                job_config = copy.deepcopy(config)
                job_config["budget_account"] = str((output / ".manju/costs.sqlite3").resolve())
                job_config.setdefault("scope", {})["batch"] = digest(input_path)
                if item.get("product_asset_id"):
                    job_config.setdefault("additional_assets", []).append(item["product_asset_id"])
                atomic_json(job / "production.json", job_config)
                creative = {"variant_version": "1.0", "parent_input_sha256": digest(input_path), "variant_id": variant, "sku": item["sku"], "product_name": item["product_name"], "selling_point": item["selling_point"], "hook": hook, "product_asset_id": item.get("product_asset_id"), "mock": True}
                atomic_json(job / "variant.json", creative)
                compile_episode(job / "episode.json", job / "bundle")
                status = "planned"
                if execute:
                    engine = Engine(job / "run", job_config)
                    try:
                        result = engine.run(make_plan(job / "bundle", job_config), auto_review_mock=auto_review_mock)
                        status = "failed" if any(row["state"] == "failed" for row in result["tasks"].values()) else ("succeeded" if all(row["state"] == "succeeded" for row in result["tasks"].values()) else "needs_review")
                    finally:
                        engine.close()
                jobs.append({"index": index, "variant_id": variant, "sku": item["sku"], "directory": job.name, "status": status})
                atomic_json(output / "batch.json", {"batch_version": "1.0", "mock": True, "jobs": jobs})
        except (OSError, ValueError) as exc:
            jobs.append({"index": index, "status": "failed", "error": str(exc)})
    result = {"batch_version": "1.0", "mock": True, "input_sha256": digest(input_path), "jobs": jobs}
    atomic_json(output / "batch.json", result)
    return result


def export_shoppable(path, output):
    data = read_json(path)
    if not isinstance(data, dict) or data.get("metadata_version") != "1.0" or not isinstance(data.get("items"), list) or not data["items"]:
        raise ValueError("metadata_version 1.0 须含非空 items")
    duration = data.get("duration_ms")
    if type(duration) is not int or duration <= 0:
        raise ValueError("须提供成片时长 duration_ms")
    if redact(data) != data:
        raise ValueError("元数据不得包含凭据")
    for item in data["items"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key].strip() for key in ("sku", "url")):
            raise ValueError("缺少 SKU 或链接")
        parsed = urlsplit(item["url"])
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("商品链接须为无凭据 HTTPS URL")
        if type(item.get("start_ms")) is not int or type(item.get("end_ms")) is not int or not 0 <= item["start_ms"] < item["end_ms"] <= duration:
            raise ValueError("商品时间点须落在成片范围内")
    if Path(output).exists():
        raise ValueError("元数据导出文件已存在")
    atomic_json(output, {**data, "input_sha256": digest(path), "notice": "仅导出元数据，未连接店铺或平台 API，不保证平台可直接导入。"})
    return data


def add_revision(project, requester, description):
    if not requester.strip() or not description.strip():
        raise ValueError("修改请求人和说明不能为空")
    project = Path(project)
    with run_lock(project):
        path = project / "revision-log.json"
        record = read_json(path)
        events = record.get("events")
        if not isinstance(events, list):
            raise ValueError("修改记录契约无效")
        events.append({"round": len(events) + 1, "requester": requester, "description": description})
        atomic_json(path, record)
    return record
