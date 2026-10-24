"""Versioned capability registry; all bundled providers are explicitly offline mocks."""
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Tuple
import wave

from .io import digest, read_json
from .safeio import atomic_json, fingerprint, redact

LAYERS = ("text", "image", "video", "identity", "tts", "asr", "avatar", "edit")


@dataclass(frozen=True)
class CapabilitySpec:
    layers: Tuple[str, ...]
    max_duration_ms: int
    resolutions: Tuple[str, ...]
    identity_modes: Tuple[str, ...]
    has_audio: bool
    pricing_unit: str
    offline: bool
    aggregate: bool = False
    revision: str = "mock-v2-pcm"

    def require(self, kind, parameters):
        if kind not in self.layers:
            raise ValueError(f"不支持能力层：{kind}")
        duration = parameters.get("duration_ms", 0)
        if type(duration) is not int or duration < 0 or duration > self.max_duration_ms:
            raise ValueError("时长超过适配器支持范围")
        if parameters.get("resolution", "preview") not in self.resolutions:
            raise ValueError("不支持所请求分辨率")
        if parameters.get("identity_mode") and parameters["identity_mode"] not in self.identity_modes:
            raise ValueError("不支持所请求身份引用方式")


@dataclass(frozen=True)
class WorkRequest:
    task_id: str
    kind: str
    model: str
    idempotency_key: str
    parameters: Mapping


class MockProvider:
    capabilities = CapabilitySpec(LAYERS, 3600000, ("preview", "720p", "1080p"), ("references", "platform_id"), True, "item", True)

    def generate(self, request, directory):
        self.capabilities.require(request.kind, request.parameters)
        if not request.model.startswith("mock-"):
            raise ValueError("MockProvider 只接受明确标注的 mock-* 模型")
        metadata = {
            "artifact_version": "1.0", "mock": True, "kind": request.kind,
            "model": request.model, "task_id": request.task_id,
            "idempotency_key": request.idempotency_key,
            "parameters": redact(dict(request.parameters)),
            "notice": "确定性占位说明，不是生成成片、ASR 转写、身份训练或人工批准",
        }
        output = Path(directory) / f"{request.idempotency_key}.json"
        if output.exists():
            if read_json(output) != metadata:
                raise ValueError("幂等键冲突：已有产物内容不同")
        else:
            atomic_json(output, metadata)
        result = {"mock": True, "job_id": f"mock-{request.idempotency_key}", "model": request.model, "path": output.name, "sha256": digest(output), "parameters": metadata["parameters"]}
        if request.kind == "tts":
            audio = output.with_suffix(".wav")
            if not audio.exists():
                duration_ms = request.parameters.get("duration_ms", 1000)
                with wave.open(str(audio), "wb") as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(8000)
                    remaining = duration_ms * 8
                    while remaining:
                        frames = min(remaining, 8000)
                        stream.writeframesraw(b"\0\0" * frames)
                        remaining -= frames
            result.update(media_path=audio.name, media_sha256=digest(audio), notice="mock 静音 WAV，仅供实测时间轴测试，不是配音")
        return result


class AggregateMockProvider(MockProvider):
    capabilities = CapabilitySpec(LAYERS, 3600000, ("preview", "720p", "1080p"), ("references", "platform_id"), True, "item", True, True)


class ProviderRegistry:
    def __init__(self):
        self._providers = {}

    def register(self, name, provider):
        if not isinstance(name, str) or not name or name in self._providers:
            raise ValueError("provider 名称为空或重复")
        if not isinstance(getattr(provider, "capabilities", None), CapabilitySpec) or not callable(getattr(provider, "generate", None)):
            raise ValueError("适配器必须提供能力声明与 generate 方法")
        self._providers[name] = provider

    def get(self, name):
        if name not in self._providers:
            raise ValueError(f"provider 未注册：{name}；本发行版只内置离线 mock")
        return self._providers[name]

    def describe(self):
        return {name: asdict(provider.capabilities) for name, provider in sorted(self._providers.items())}


def registry():
    result = ProviderRegistry()
    result.register("mock", MockProvider())
    result.register("mock-aggregate", AggregateMockProvider())
    return result


def load_config(path=None):
    data = read_json(path) if path else read_json(Path(__file__).resolve().parents[1] / "configs" / "mock.json")
    if not isinstance(data, dict) or data.get("production_version") != "1.0":
        raise ValueError("production_version 必须为 1.0")
    if redact(data) != data:
        raise ValueError("配置不能包含密钥字段或凭据；密钥只能从环境变量读取")
    routes = data.get("routes")
    if not isinstance(routes, dict) or not isinstance(routes.get("defaults"), dict) or not isinstance(routes.get("shots", {}), dict):
        raise ValueError("routes 须包含 defaults 与可选 shots 对象")
    for kind in LAYERS:
        route_for(data, kind)
    from .costs import money, provenance
    provenance(data.get("pricing"))
    if not isinstance(data["pricing"].get("currency"), str) or not data["pricing"]["currency"]:
        raise ValueError("pricing.currency 必须为非空字符串")
    if not isinstance(data["pricing"].get("rates"), dict) or not data["pricing"]["rates"]:
        raise ValueError("pricing.rates 必须为非空对象")
    if not isinstance(data.get("budgets"), dict) or not {"project", "episode", "shot", "batch"} <= data["budgets"].keys():
        raise ValueError("须显式配置四级预算")
    for value in data["budgets"].values():
        money(value)
    return data


def route_for(config, kind, shot_id=None):
    route = config["routes"].get("shots", {}).get(shot_id, {}).get(kind, config["routes"]["defaults"].get(kind))
    if not isinstance(route, list) or not route:
        raise ValueError(f"缺少能力层路由：{kind}")
    for entry in route:
        if not isinstance(entry, dict) or not {"provider", "model"} <= entry.keys() or entry.keys() - {"provider", "model", "parameters"} or not all(isinstance(entry[k], str) and entry[k] for k in ("provider", "model")):
            raise ValueError("每个路由须包含非空 provider 与 model")
        parameters = entry.get("parameters", {})
        if not isinstance(parameters, dict) or set(parameters) & {"shot", "voice", "project", "duration_ms"}:
            raise ValueError("路由参数不得覆盖剧本、台词或计划时长")
    return route


def adapter_contract(provider, directory):
    """Reusable offline conformance suite for adapters; never exercises network adapters."""
    if not provider.capabilities.offline:
        raise ValueError("离线契约套件不调用真实服务")
    results = []
    for kind in provider.capabilities.layers:
        key = fingerprint({"contract": "1.0", "kind": kind})
        request = WorkRequest(f"contract:{kind}", kind, f"mock-{kind}", key, {"duration_ms": 1000})
        first = provider.generate(request, directory)
        second = provider.generate(request, directory)
        if first != second or not first.get("mock") or digest(Path(directory) / first["path"]) != first["sha256"]:
            raise ValueError("适配器确定性/摘要/占位标识契约失败")
        results.append(kind)
    return results
