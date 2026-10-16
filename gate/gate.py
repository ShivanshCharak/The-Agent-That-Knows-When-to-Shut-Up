"""Interjection gate: threshold, interrupt budget, cooldown."""
from dataclasses import dataclass

from gate.schema import Decision


@dataclass
class GateConfig:
    threshold: float = 0.7
    budget_max: int = 3
    budget_window_s: float = 600.0
    cooldown_s: float = 60.0


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str  # pass | silent_decision | below_threshold | budget_exhausted | cooldown


class InterjectionGate:
    def __init__(self, config: GateConfig | None = None):
        self.config = config or GateConfig()
        self._spoken: list[float] = []

    def evaluate(self, decision: Decision, now: float) -> GateResult:
        c = self.config
        if not decision.speak:
            return GateResult(False, "silent_decision")
        if decision.confidence < c.threshold:
            return GateResult(False, "below_threshold")
        if self._spoken and now - self._spoken[-1] < c.cooldown_s:
            return GateResult(False, "cooldown")
        recent = [t for t in self._spoken if now - t < c.budget_window_s]
        if len(recent) >= c.budget_max:
            return GateResult(False, "budget_exhausted")
        self._spoken.append(now)
        return GateResult(True, "pass")
