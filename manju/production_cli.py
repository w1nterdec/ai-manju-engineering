"""Additive command surface for versioned offline production workflows."""
import json
from pathlib import Path

from .adapters import adapter_contract, load_config, registry
from .execution import Engine, approve
from .io import read_json
from .planning import make_plan
from .safeio import atomic_json


def add_commands(commands):
    providers = commands.add_parser("providers", help="查看已注册的离线能力层与限制")
    providers.set_defaults(handler=lambda args: emit(registry().describe()))
    contract = commands.add_parser("adapter-test", help="执行离线适配器契约套件")
    contract.add_argument("--out", required=True)
    contract.set_defaults(handler=adapter_test)
    config = commands.add_parser("config-check", help="校验生产侧配置")
    config.add_argument("config")
    config.set_defaults(handler=lambda args: emit({"passed": bool(load_config(args.config)), "scope": "offline configuration"}))
    plan = commands.add_parser("plan", help="生成确定性的逐任务执行预览")
    plan.add_argument("bundle")
    plan.add_argument("--config")
    plan.add_argument("--out", required=True)
    plan.add_argument("--estimate", action="store_true")
    plan.set_defaults(handler=plan_command)
    run = commands.add_parser("run", help="离线执行与恢复，不调用真实生成服务")
    run.add_argument("bundle")
    run.add_argument("--out", required=True)
    run.add_argument("--config")
    run.add_argument("--preview")
    run.add_argument("--auto-review-mock", action="store_true")
    run.add_argument("--allow-network", action="store_true")
    run.add_argument("--stop-after", type=int)
    run.add_argument("--retry-failed", action="store_true")
    run.add_argument("--resume", action="store_true")
    run.set_defaults(handler=run_command)
    status = commands.add_parser("status", help="读取持久任务状态")
    status.add_argument("directory")
    status.set_defaults(handler=status_command)
    cancel = commands.add_parser("cancel", help="停止新调度，在途任务完成后保存")
    cancel.add_argument("directory")
    cancel.set_defaults(handler=lambda args: (atomic_json(Path(args.directory) / "cancel.json", {"cancel": True}) or emit({"cancel_requested": True})))
    approval = commands.add_parser("approve-task", help="记录实际人工审核")
    approval.add_argument("directory")
    approval.add_argument("task_id")
    approval.add_argument("--reviewer", required=True)
    approval.add_argument("--note", required=True)
    approval.set_defaults(handler=lambda args: (approve(args.directory, args.task_id, args.reviewer, args.note) or emit({"recorded": True})))
    cost = commands.add_parser("cost-report", help="读取保留预留/释放/模拟实际值的成本台账")
    cost.add_argument("directory")
    cost.add_argument("--config")
    cost.set_defaults(handler=cost_command)
    asset = commands.add_parser("asset-add", help="导入本地素材与授权记录")
    asset.add_argument("file")
    asset.add_argument("--store", required=True)
    asset.add_argument("--kind", required=True)
    asset.add_argument("--metadata", required=True)
    asset.add_argument("--evidence")
    asset.set_defaults(handler=asset_add)
    asset_approval = commands.add_parser("asset-approve", help="新增不可变的素材批准版本")
    asset_approval.add_argument("asset_id")
    asset_approval.add_argument("--store", required=True)
    asset_approval.add_argument("--reviewer", required=True)
    asset_approval.add_argument("--note", required=True)
    asset_approval.set_defaults(handler=asset_approve)
    asset_check = commands.add_parser("asset-check", help="检查授权记录，不作法律结论")
    asset_check.add_argument("asset_id")
    asset_check.add_argument("--store", required=True)
    asset_check.add_argument("--as-of")
    asset_check.set_defaults(handler=asset_check_command)
    trace = commands.add_parser("lineage", help="回溯任务的剧本、参数、模型、资产与依赖")
    trace.add_argument("bundle")
    trace.add_argument("directory")
    trace.add_argument("task_id")
    trace.set_defaults(handler=lineage_command)
    probe_parser = commands.add_parser("probe", help="本地媒体探测，缺 ffprobe 时明确降级")
    probe_parser.add_argument("file")
    probe_parser.set_defaults(handler=probe_command)
    alignment = commands.add_parser("align", help="按实测逐句音频重新编排字幕时间轴")
    alignment.add_argument("bundle")
    alignment.add_argument("audio_map")
    alignment.add_argument("--out", required=True)
    alignment.set_defaults(handler=align_command)
    quality = commands.add_parser("quality-report", help="合并自动技术检查与人工记录，二者明确分开")
    quality.add_argument("bundle")
    quality.add_argument("--review")
    quality.add_argument("--run")
    quality.add_argument("--config")
    quality.add_argument("--alignment", help="按已经验证的实测时间线核对视频时长")
    quality.add_argument("--out", required=True)
    quality.set_defaults(handler=quality_command)
    audio_map = commands.add_parser("demo-audio-map", help="为 mock 静音 WAV 生成明确标记的测试映射")
    audio_map.add_argument("directory")
    audio_map.add_argument("--out", required=True)
    audio_map.set_defaults(handler=audio_map_command)
    handoff_parser = commands.add_parser("handoff", help="导出通用剪辑交接 CSV/JSON/SRT")
    handoff_parser.add_argument("bundle")
    handoff_parser.add_argument("--alignment")
    handoff_parser.add_argument("--out", required=True)
    handoff_parser.set_defaults(handler=handoff_command)
    packaging = commands.add_parser("package", help="生产交付包；仅 --demo 可接受 mock")
    packaging.add_argument("bundle")
    packaging.add_argument("--run")
    packaging.add_argument("--config")
    packaging.add_argument("--review")
    packaging.add_argument("--final")
    packaging.add_argument("--alignment")
    packaging.add_argument("--provenance")
    packaging.add_argument("--business-checks")
    packaging.add_argument("--demo", action="store_true")
    packaging.add_argument("--include-costs", action="store_true")
    packaging.add_argument("--out", required=True)
    packaging.set_defaults(handler=package_command)
    verification = commands.add_parser("verify-package", help="独立校验交付包文件摘要与完整性")
    verification.add_argument("directory")
    verification.set_defaults(handler=verify_package_command)
    new = commands.add_parser("new", help="按可校验业务画像创建项目")
    new.add_argument("--profile", required=True)
    new.add_argument("--out", required=True)
    new.set_defaults(handler=new_command)
    batch_parser = commands.add_parser("batch", help="离线广告商品/钩子批次，单项失败隔离")
    batch_parser.add_argument("project")
    batch_parser.add_argument("input")
    batch_parser.add_argument("--out", required=True)
    batch_parser.add_argument("--execute", action="store_true")
    batch_parser.add_argument("--auto-review-mock", action="store_true")
    batch_parser.set_defaults(handler=batch_command)
    quote = commands.add_parser("quote", help="按用户参数计算单位成本与报价辅助值")
    quote.add_argument("--profile", required=True)
    quote.add_argument("--inputs", required=True)
    quote.add_argument("--out", required=True)
    quote.set_defaults(handler=quote_command)
    shoppable = commands.add_parser("shoppable-export", help="仅导出 SKU/URL/时间点，不连接店铺")
    shoppable.add_argument("input")
    shoppable.add_argument("--out", required=True)
    shoppable.set_defaults(handler=shoppable_command)
    revision = commands.add_parser("revision-add", help="追加客户修改轮次记录")
    revision.add_argument("project")
    revision.add_argument("--requester", required=True)
    revision.add_argument("--description", required=True)
    revision.set_defaults(handler=revision_command)


def emit(value):
    from .safeio import redact
    print(json.dumps(redact(value), ensure_ascii=False, indent=2))
    return 0


def adapter_test(args):
    directory = Path(args.out)
    directory.mkdir(parents=True, exist_ok=True)
    return emit({"mock": True, "layers": adapter_contract(registry().get("mock"), directory)})


def plan_command(args):
    destination = Path(args.out)
    if destination.exists():
        raise ValueError("预览文件已存在，请选择新版本")
    plan = make_plan(args.bundle, load_config(args.config))
    atomic_json(destination, plan)
    return emit({"plan_id": plan["plan_id"], "mock": plan["mock"], "task_count": len(plan["tasks"]), "estimate": plan["estimate"] if args.estimate else None, "out": str(destination)})


def run_command(args):
    config = load_config(args.config)
    plan = make_plan(args.bundle, config)
    if args.preview and read_json(args.preview).get("plan_id") != plan["plan_id"]:
        raise ValueError("dry-run 预览已过期，请重新生成")
    if not plan["mock"]:
        raise ValueError("本版本无真实适配器；真实准入还需网络开关、预算与匹配 dry-run")
    if args.resume:
        (Path(args.out) / "cancel.json").unlink(missing_ok=True)
    engine = Engine(args.out, config)
    try:
        status = engine.run(plan, auto_review_mock=args.auto_review_mock, stop_after=args.stop_after, retry_failed=args.retry_failed)
        counts = {}
        for task in status["tasks"].values():
            counts[task["state"]] = counts.get(task["state"], 0) + 1
        emit({"mock": status["mock"], "states": counts, "directory": args.out})
        return int(any(row["state"] == "failed" for row in status["tasks"].values()))
    finally:
        engine.close()


def status_command(args):
    if not (Path(args.directory) / "run.sqlite3").is_file():
        raise ValueError("运行目录不存在")
    engine = Engine(args.directory, {})
    try:
        return emit(engine.state())
    finally:
        engine.close()


def cost_command(args):
    from .costs import CostLedger
    config = load_config(args.config)
    path = config.get("budget_account", Path(args.directory).parent / ".manju" / "costs.sqlite3")
    if not Path(path).is_file():
        raise ValueError("台账不存在")
    ledger = CostLedger(path, config)
    try:
        return emit(ledger.report())
    finally:
        ledger.close()


def asset_add(args):
    from .assets import AssetStore
    return emit(AssetStore(args.store).add(args.file, args.kind, read_json(args.metadata), args.evidence))


def asset_approve(args):
    from .assets import AssetStore
    return emit(AssetStore(args.store).approve(args.asset_id, args.reviewer, args.note))


def asset_check_command(args):
    from .assets import AssetStore
    result = AssetStore(args.store).check(args.asset_id, as_of=args.as_of)
    emit(result)
    return int(not result["passed"])


def lineage_command(args):
    from .assets import lineage
    return emit(lineage(args.bundle, args.directory, args.task_id))


def probe_command(args):
    from .media import probe
    result = probe(args.file)
    emit(result)
    return int(result["status"] != "measured")


def align_command(args):
    from .media import align
    result = align(args.bundle, args.audio_map, args.out)
    return emit({"mock": result["mock"], "duration_ms": result["duration_ms"], "out": args.out})


def quality_command(args):
    from .media import quality_report
    result = quality_report(args.bundle, args.review, load_config(args.config), args.run, alignment=args.alignment)
    if Path(args.out).exists():
        raise ValueError("质量报告已存在，选择新版本")
    atomic_json(args.out, result)
    return emit({"production_ready": result["production_ready"], "out": args.out})


def audio_map_command(args):
    import os
    from .io import inside
    destination = Path(args.out)
    if destination.exists():
        raise ValueError("音频映射已存在")
    status = read_json(Path(args.directory) / "status.json")
    lines = {}
    if not status.get("mock"):
        raise ValueError("此命令只允许 mock 静音 WAV")
    for task_id, task in status["tasks"].items():
        if task_id.startswith("tts:") and task["state"] == "succeeded":
            result = json.loads(task["result"])
            relative = os.path.relpath(Path(args.directory) / "artifacts" / result["media_path"], destination.parent).replace("\\", "/")
            inside(destination.parent, relative)
            lines[task_id.split(":", 1)[1]] = relative
    atomic_json(destination, {"audio_map_version": "1.0", "mock": True, "lines": lines})
    return emit({"mock": True, "lines": len(lines)})


def handoff_command(args):
    from .delivery import handoff
    result = handoff(args.bundle, args.out, args.alignment)
    return emit({"timing_basis": result["timing_basis"], "out": args.out})


def package_command(args):
    from .delivery import package
    result = package(args.bundle, args.out, load_config(args.config), run=args.run, demo=args.demo, review=args.review, final=args.final, alignment=args.alignment, provenance=args.provenance, include_costs=args.include_costs, profile_checks=args.business_checks)
    return emit({"mode": result["mode"], "production_ready": result["production_ready"], "out": args.out})


def verify_package_command(args):
    from .delivery import verify_package
    result = verify_package(args.directory)
    emit(result)
    return int(not result["passed"])


def new_command(args):
    from .business import new_project
    return emit(new_project(args.profile, args.out))


def batch_command(args):
    from .business import batch
    result = batch(args.project, args.input, args.out, args.execute, args.auto_review_mock)
    emit(result)
    return int(any(job["status"] == "failed" for job in result["jobs"]))


def quote_command(args):
    from .business import load_profile, unit_cost
    if Path(args.out).exists():
        raise ValueError("报价输出已存在")
    result = unit_cost(load_profile(args.profile), read_json(args.inputs))
    atomic_json(args.out, result)
    return emit(result)


def shoppable_command(args):
    from .business import export_shoppable
    return emit(export_shoppable(args.input, args.out))


def revision_command(args):
    from .business import add_revision
    return emit(add_revision(args.project, args.requester, args.description))
