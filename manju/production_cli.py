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


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))
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
