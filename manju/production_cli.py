"""Additive command surface for versioned offline production workflows."""
import json
from pathlib import Path

from .adapters import adapter_contract, load_config, registry


def add_commands(commands):
    providers = commands.add_parser("providers", help="查看已注册的离线能力层与限制")
    providers.set_defaults(handler=lambda args: emit(registry().describe()))
    contract = commands.add_parser("adapter-test", help="执行离线适配器契约套件")
    contract.add_argument("--out", required=True)
    contract.set_defaults(handler=adapter_test)
    config = commands.add_parser("config-check", help="校验生产侧配置")
    config.add_argument("config")
    config.set_defaults(handler=lambda args: emit({"passed": bool(load_config(args.config)), "scope": "offline configuration"}))


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def adapter_test(args):
    directory = Path(args.out)
    directory.mkdir(parents=True, exist_ok=True)
    return emit({"mock": True, "layers": adapter_contract(registry().get("mock"), directory)})
