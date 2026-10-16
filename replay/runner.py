"""Replay a recorded log through rules -> decider -> gate and print one line per tick."""
import argparse
import json
import os

from adapters.base import load_jsonl
from gate.bedrock import BedrockResponder
from gate.context import ContextBuilder
from gate.decider import HttpDecider
from gate.gate import GateConfig, InterjectionGate
from gate.handler import InterjectionHandler, Responder
from gate.rules import should_skip


def run(
    path: str,
    threshold: float,
    verbose: bool = True,
    decider_url: str | None = None,
    responder: Responder | None = None,
) -> dict:
    ctx = ContextBuilder()
    decider_username = os.environ.get("DECIDER_USERNAME")
    decider_password = os.environ.get("DECIDER_PASSWORD")
    if bool(decider_username) != bool(decider_password):
        raise ValueError("Set both DECIDER_USERNAME and DECIDER_PASSWORD, or neither")
    decider_auth = (decider_username, decider_password) if decider_username else None
    decider = HttpDecider(
        decider_url or os.environ.get("DECIDER_URL", "http://localhost:8000"),
        auth=decider_auth,
    )
    handler = InterjectionHandler(
        decider, InterjectionGate(GateConfig(threshold=threshold)), responder=responder
    )
    counts = {"checks": 0, "rule_skipped": 0, "decider_calls": 0, "bedrock_calls": 0}
    ticks = []
    for event in load_jsonl(path):
        counts["checks"] += 1
        ctx.update(event)
        if should_skip(event):
            counts["rule_skipped"] += 1
            record = {
                "tick": event.ts,
                "event": event.kind,
                "payload": event.payload,
                "skipped_by_rule": True,
                "decision": None,
                "confidence": None,
                "gate": {"allowed": False, "reason": "rule_skipped"},
                "bedrock_called": False,
                "bedrock_text": None,
            }
            ticks.append(record)
            if verbose:
                print(json.dumps(record, sort_keys=True))
            continue
        result = handler.handle(ctx.snapshot(event.ts))
        counts["decider_calls"] += 1
        if result.allowed:
            ctx.mark_spoke(event.ts)
        if result.bedrock_called:
            counts["bedrock_calls"] += 1
        record = {
            "tick": event.ts,
            "event": event.kind,
            "payload": event.payload,
            "skipped_by_rule": False,
            "decision": {
                "speak": result.decision.speak,
                "kind": result.decision.kind,
                "confidence": result.decision.confidence,
            },
            "confidence": result.decision.confidence,
            "gate": {"allowed": result.allowed, "reason": result.reason},
            "bedrock_called": result.bedrock_called,
            "bedrock_text": result.response,
        }
        ticks.append(record)
        if verbose:
            print(json.dumps(record, sort_keys=True))
    counts["ticks"] = ticks
    return counts


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("log")
    p.add_argument("--threshold", type=float, default=0.7)
    p.add_argument("--decider-url", default=os.environ.get("DECIDER_URL", "http://localhost:8000"),
                   help="Strands Decider server base URL (default: DECIDER_URL or http://localhost:8000)")
    p.add_argument("--bedrock-model-id", help="Enable Bedrock responses; this makes billable AWS calls")
    p.add_argument("--region", help="AWS region for Bedrock (otherwise use the AWS SDK default)")
    a = p.parse_args()
    responder = BedrockResponder(a.bedrock_model_id, region=a.region) if a.bedrock_model_id else None
    c = run(a.log, a.threshold, decider_url=a.decider_url, responder=responder)
    print(f"\n{c['checks']} checks, {c['rule_skipped']} rule-skipped, "
          f"{c['decider_calls']} Decider calls, {c['bedrock_calls']} Bedrock calls")
