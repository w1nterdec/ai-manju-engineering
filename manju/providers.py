"""Extension contracts only. No paid calls or fabricated media results."""

from dataclasses import dataclass
from typing import FrozenSet, Mapping, Optional, Protocol, Tuple


@dataclass(frozen=True)
class Capabilities:
    task_kinds: FrozenSet[str]
    controls: FrozenSet[str]  # e.g. image_reference, pronunciation_lexicon, seed

    def require(self, kind: str, controls: FrozenSet[str]) -> None:
        if kind not in self.task_kinds or not controls <= self.controls:
            raise ValueError("适配器不支持请求的任务或控制项；不得静默丢弃约束")


@dataclass(frozen=True)
class GenerationRequest:
    task_id: str
    kind: str
    model: str
    idempotency_key: str
    input_hashes: Tuple[str, ...]
    parameters: Mapping[str, object]
    required_controls: FrozenSet[str]


@dataclass(frozen=True)
class GenerationResult:
    provider_job_id: str
    artifact_paths: Tuple[str, ...]
    actual_model: str
    actual_parameters: Mapping[str, object]
    cost_amount: Optional[str]  # decimal string; None means unknown, not free
    cost_currency: Optional[str]  # never aggregate costs across currencies


class Provider(Protocol):
    capabilities: Capabilities

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Implementations must capability-check, bound retries and record actual inputs."""
        ...
