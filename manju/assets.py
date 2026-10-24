"""Content-addressed local assets and recorded rights; no legal conclusions."""
from datetime import date
from pathlib import Path
import shutil

from .io import digest, inside, read_json
from .safeio import atomic_json, fingerprint, redact, run_lock

KINDS = {"identity", "scene", "prop", "voice", "style", "product"}


class AssetStore:
    def __init__(self, directory):
        self.root = Path(directory)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)
        (self.root / "records").mkdir(exist_ok=True)

    def _blob(self, path):
        sha = digest(path)
        destination = self.root / "blobs" / sha
        if destination.exists():
            if digest(destination) != sha:
                raise ValueError("内容寻址素材已被破坏")
        else:
            with Path(path).open("rb") as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target)
        return sha

    def get(self, asset_id):
        if not isinstance(asset_id, str) or len(asset_id) != 64 or any(c not in "0123456789abcdef" for c in asset_id):
            raise ValueError("素材 ID 必须为 SHA-256")
        record = read_json(self.root / "records" / f"{asset_id}.json")
        body = {key: value for key, value in record.items() if key != "asset_id"}
        if fingerprint(body) != asset_id:
            raise ValueError("素材记录摘要不匹配")
        path = inside(self.root, f"blobs/{record['content_sha256']}")
        if not path.is_file() or digest(path) != record["content_sha256"]:
            raise ValueError("素材内容缺失或摘要不匹配")
        return record

    def _record(self, body):
        asset_id = fingerprint(body)
        record = {**body, "asset_id": asset_id}
        path = self.root / "records" / f"{asset_id}.json"
        if not path.exists():
            atomic_json(path, record)
        return record

    def add(self, path, kind, metadata, evidence=None):
        if kind not in KINDS or not isinstance(metadata, dict) or redact(metadata) != metadata:
            raise ValueError("素材类型或元数据不合法，禁止保存凭据")
        if not isinstance(metadata.get("source"), str) or not metadata["source"].strip():
            raise ValueError("须记录素材来源")
        license_record = metadata.get("license", {})
        if not isinstance(license_record, dict):
            raise ValueError("license 须为授权记录对象")
        with run_lock(self.root):
            sha = self._blob(path)
            proof = self._blob(evidence) if evidence else None
            body = {"asset_version": "1.0", "content_sha256": sha, "kind": kind, "source": metadata["source"], "license": license_record, "evidence_sha256": proof, "mock": bool(metadata.get("mock", False)), "approval": None, "parent_id": None}
            return self._record(body)

    def approve(self, asset_id, reviewer, note):
        if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(note, str) or not note.strip():
            raise ValueError("批准需实际审核人和说明")
        with run_lock(self.root):
            record = self.get(asset_id)
            body = {key: value for key, value in record.items() if key != "asset_id"}
            body["parent_id"] = asset_id
            body["approval"] = {"reviewer": reviewer, "note": note}
            return self._record(body)

    def check(self, asset_id, *, scope="commercial_delivery", as_of=None, allow_mock=False):
        record = self.get(asset_id)
        problems = []
        as_of = date.fromisoformat(as_of) if as_of else date.today()
        if record["mock"] and not allow_mock:
            problems.append("mock 素材或凭据不能用于生产交付")
        if not record.get("approval"):
            problems.append("素材尚未批准")
        license_record = record.get("license", {})
        scopes = license_record.get("scope")
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes) or scope not in scopes:
            problems.append(f"缺少所需使用范围记录：{scope}")
        if not isinstance(license_record.get("restrictions"), list):
            problems.append("须显式记录 restrictions，空列表表示已记录无附加限制")
        if "expires" not in license_record:
            problems.append("须记录授权期限，null 表示记录为无指定期限，需使用者核实")
        elif license_record["expires"] is not None:
            try:
                if date.fromisoformat(license_record["expires"]) < as_of:
                    problems.append("授权记录已过期")
            except (TypeError, ValueError):
                problems.append("授权期限格式无效")
        proof = record.get("evidence_sha256")
        if not isinstance(proof, str):
            problems.append("缺少授权凭据文件")
        else:
            path = inside(self.root, f"blobs/{proof}")
            if not path.is_file() or digest(path) != proof:
                problems.append("授权凭据缺失或摘要不匹配")
        return {"asset_id": asset_id, "passed": not problems, "problems": problems, "as_of": as_of.isoformat(), "notice": "仅检查记录与完整性；以所在地区和投放平台最新要求为准，由使用者自行核实。"}


def identity_report(episode, config, *, production=False):
    used = {cid for shot in episode["shots"] for cid in shot["character_ids"]}
    used.update(line["speaker_id"] for beat in episode["beats"] for line in beat["lines"])
    entries, problems = [], []
    store = AssetStore(config["asset_store"]) if config.get("asset_store") else None
    bindings = config.get("identities", {})
    if not isinstance(bindings, dict):
        raise ValueError("identities 须为角色引用对象")
    for cid in sorted(used):
        binding = bindings.get(cid)
        if not isinstance(binding, dict) or not isinstance(binding.get("asset_ids"), list) or not binding["asset_ids"]:
            problems.append(f"{cid} 缺少身份/音色资产引用")
            continue
        if binding.get("training_state") not in ("ready", "not_required"):
            problems.append(f"{cid} 身份资产训练状态未就绪")
        for asset_id in binding["asset_ids"]:
            if store is None:
                problems.append("缺少 asset_store")
                continue
            try:
                record = store.get(asset_id)
                entries.append(record)
                if production:
                    checked = store.check(asset_id, scope=config.get("required_rights_scope", "commercial_delivery"), as_of=config.get("rights_as_of"))
                    problems.extend(f"{cid}: {issue}" for issue in checked["problems"])
                elif not record.get("approval"):
                    problems.append(f"{cid} 素材未批准")
            except (OSError, ValueError) as exc:
                problems.append(f"{cid}: {exc}")
    for asset_id in config.get("additional_assets", []):
        if store is None:
            problems.append("额外素材缺少 asset_store")
            continue
        try:
            entries.append(store.get(asset_id))
            if production:
                problems.extend(store.check(asset_id, as_of=config.get("rights_as_of"))["problems"])
        except (OSError, ValueError) as exc:
            problems.append(str(exc))
    return {"rights_version": "1.0", "passed": not problems, "problems": problems, "assets": entries, "scope": "production rights records" if production else "identity approval records"}


def lineage(bundle, run, task_id):
    from .review import load_bundle
    load_bundle(bundle)
    plan = read_json(Path(run) / "plan.json")
    if plan["manifest_sha256"] != digest(Path(bundle) / "manifest.json"):
        raise ValueError("运行与构建版本不匹配")
    tasks = {task["id"]: task for task in plan["tasks"]}
    if task_id not in tasks:
        raise ValueError("未知任务 ID")
    selected = {}

    def visit(key):
        if key in selected:
            return
        selected[key] = tasks[key]
        for dependency in tasks[key]["depends_on"]:
            visit(dependency)

    visit(task_id)
    status = read_json(Path(run) / "status.json")
    if status["plan_id"] != plan["plan_id"]:
        raise ValueError("运行状态与计划不匹配")
    return {"lineage_version": "1.0", "manifest_sha256": digest(Path(bundle) / "manifest.json"), "plan_id": plan["plan_id"], "task_id": task_id, "tasks": selected, "results": {key: status["tasks"].get(key) for key in selected}}
