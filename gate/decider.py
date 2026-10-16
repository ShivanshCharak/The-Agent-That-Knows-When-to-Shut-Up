"""Decider clients for the deterministic mock and local HTTP model server."""

from dataclasses import asdict
import json
from typing import Protocol

import requests

from gate.schema import KIND_QUESTION, QUESTION, Context, Decision


class Decider(Protocol):
    def decide(self, question: str, context: Context) -> Decision: ...


class MockDecider:
    """Not a model. Rough rules, only for wiring and demos."""

    def decide(self, question: str, context: Context) -> Decision:
        s = context.state
        last = context.recent_events[-1].kind if context.recent_events else None
        if s.inspecting_error:
            return Decision(False, None, 0.1)
        if last == "risky_change":
            return Decision(True, "correct", 0.9)
        if s.repeat_count >= 3:
            return Decision(True, "correct", 0.9)
        if (
            s.secs_since_last_failure is not None
            and s.secs_since_last_failure > 30
            and not s.inspecting_error
        ):
            return Decision(True, "ask", 0.75)
        if last == "test_fail":
            return Decision(False, None, 0.4)
        return Decision(False, None, 0.1)


class HttpDecider:
    """Client for ``strands-decider serve``'s ``/v1/systemone`` endpoint."""

    def __init__(
        self, url: str, timeout_s: float = 120.0, auth: tuple[str, str] | None = None
    ):
        self.url = url.rstrip("/")
        self.timeout_s = timeout_s
        self.auth = auth

    def decide(
        self, question: str = QUESTION, context: Context | None = None
    ) -> Decision:
        if context is None:
            raise ValueError("context is required for an HTTP Decider request")

        state = json.dumps(asdict(context), sort_keys=True, separators=(",", ":"))
        payload = {
            "state": state,
            "questions": {
                "speak": {
                    "type": "noul",
                    "instructions": question,
                    "criteria": {
                        "true": "An interjection would help the developer now.",
                        "false": "The developer should be left uninterrupted now.",
                    },
                },
                "kind": {
                    "type": "choice",
                    "instructions": KIND_QUESTION,
                    "criteria": {
                        "correct": "Point out a likely mistake or risk.",
                        "suggest": "Offer a useful next step or idea.",
                        "ask": "Ask a brief clarifying question.",
                    },
                },
            },
        }

        response = requests.post(
            f"{self.url}/v1/systemone",
            json=payload,
            timeout=self.timeout_s,
            auth=self.auth,
        )
        response.raise_for_status()
        body = response.json()
        try:
            probability = float(body["answers"]["speak"]["noul"])
            kind = body["answers"]["kind"]["choice"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Decider response is missing a valid speak or kind answer"
            ) from exc
        if not 0.0 <= probability <= 1.0:
            raise ValueError(
                f"Decider returned invalid speak probability: {probability}"
            )
        if kind not in {"correct", "suggest", "ask"}:
            raise ValueError(f"Decider returned unsupported response kind: {kind!r}")

        # `noul` is P(true), so preserve it as the urge/confidence value used by
        # the gate and UI; it is not a separate model-provided confidence field.
        return Decision(
            speak=probability >= 0.5,
            kind=kind if probability >= 0.5 else None,
            confidence=probability,
        )
