"""Framework-agnostic orchestration and an optional Strands adapter factory."""
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from gate.decider import Decider
from gate.gate import InterjectionGate
from gate.schema import QUESTION, Context, Decision


class Responder(Protocol):
    def generate(self, decision: Decision, context: Context) -> str: ...


@dataclass(frozen=True)
class HandlerResult:
    decision: Decision
    allowed: bool
    reason: str
    response: str | None
    bedrock_called: bool


class InterjectionHandler:
    def __init__(
        self,
        decider: Decider,
        gate: InterjectionGate,
        responder: Responder | None = None,
    ):
        self.decider = decider
        self.gate = gate
        self.responder = responder
        self.bedrock_calls = 0

    def handle(self, context: Context) -> HandlerResult:
        decision = self.decider.decide(QUESTION, context)
        gate_result = self.gate.evaluate(decision, context.now)
        response = None
        called = gate_result.allowed and self.responder is not None
        if called:
            self.bedrock_calls += 1
            response = self.responder.generate(decision, context)
        return HandlerResult(
            decision=decision,
            allowed=gate_result.allowed,
            reason=gate_result.reason,
            response=response,
            bedrock_called=called,
        )

    def check(self, context: Context) -> tuple[Decision, bool, str]:
        result = self.handle(context)
        return result.decision, result.allowed, result.reason


def make_strands_intervention_handler(
    core: InterjectionHandler,
    context_provider: Callable[[Any], Context | None],
):
    """Create a real Strands InterventionHandler without requiring Strands for replays.

    The provider translates a Strands lifecycle event into this project's current Context.
    The returned handler injects generated advice before the model call only when the gate passes.
    """
    try:
        from strands.interventions import Guide, InterventionHandler as StrandsHandler, Proceed
    except ImportError as exc:
        raise RuntimeError(
            "Install strands-agents to attach the gate to a Strands Agent"
        ) from exc

    class StrandsInterjectionHandler(StrandsHandler):
        name = "interjection-gate"

        def before_model_call(self, event):
            context = context_provider(event)
            if context is None:
                return Proceed()
            result = core.handle(context)
            if not result.allowed or not result.response:
                return Proceed()
            return Guide(feedback=result.response)

    return StrandsInterjectionHandler()
