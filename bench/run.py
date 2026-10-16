"""Compare the local Decider and Bedrock judge against hand-labeled moments."""
import argparse
import json
from pathlib import Path
import statistics
import time

from adapters.base import load_jsonl
from bench.judge import BedrockJudge
from gate.context import ContextBuilder
from gate.decider import HttpDecider


ROOT = Path(__file__).resolve().parents[1]


def contexts_for(log_id: str, log_dir: Path) -> dict[int, object]:
    path = log_dir / f"{log_id}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"No replay log for log_id={log_id!r}: {path}")
    builder = ContextBuilder()
    contexts = {}
    for tick, event in enumerate(load_jsonl(str(path)), start=1):
        builder.update(event)
        contexts[tick] = builder.snapshot(event.ts)
    return contexts


def _classification_metrics(gold: list[dict], predictions: list[dict]) -> dict:
    n = len(gold)
    speak_correct = sum(g["should_speak"] == p["should_speak"] for g, p in zip(gold, predictions))
    joint_correct = sum(
        g["should_speak"] == p["should_speak"] and g["kind"] == p["kind"]
        for g, p in zip(gold, predictions)
    )
    positives = [
        (g, p) for g, p in zip(gold, predictions) if g["should_speak"]
    ]
    kind_correct = sum(g["kind"] == p["kind"] for g, p in positives)
    latencies = [p["latency_ms"] for p in predictions]
    return {
        "speak_accuracy": speak_correct / n if n else None,
        "joint_accuracy": joint_correct / n if n else None,
        "kind_accuracy_on_labeled_positive": kind_correct / len(positives) if positives else None,
        "mean_latency_ms": statistics.mean(latencies) if latencies else None,
        "median_latency_ms": statistics.median(latencies) if latencies else None,
    }


def _write_svg(path: Path, values: dict[str, float | None]) -> None:
    width, height, baseline = 540, 300, 235
    colors = ["#2463eb", "#7c3aed", "#059669"]
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="30" font-family="sans-serif" font-size="18" font-weight="600">Benchmark accuracy</text>',
        f'<line x1="40" y1="{baseline}" x2="{width - 24}" y2="{baseline}" stroke="#777"/>',
    ]
    for idx, (label, value) in enumerate(values.items()):
        x = 70 + idx * 160
        score = max(0.0, min(1.0, value or 0.0))
        bar_h = score * 170
        elements.append(
            f'<rect x="{x}" y="{baseline - bar_h:.1f}" width="72" height="{bar_h:.1f}" rx="5" fill="{colors[idx]}"/>'
        )
        elements.append(
            f'<text x="{x + 36}" y="{baseline - bar_h - 10:.1f}" text-anchor="middle" font-family="sans-serif" font-size="13">{score:.1%}</text>'
        )
        elements.append(
            f'<text x="{x + 36}" y="{baseline + 24}" text-anchor="middle" font-family="sans-serif" font-size="12">{label}</text>'
        )
    elements.append("</svg>")
    path.write_text("\n".join(elements))


def run(
    labels_path: Path,
    decider_url: str,
    judge_model_id: str,
    region: str | None = None,
    input_cost_per_million: float | None = None,
    output_cost_per_million: float | None = None,
    output_path: Path | None = None,
) -> dict:
    labels = [json.loads(line) for line in labels_path.read_text().splitlines() if line.strip()]
    if not 40 <= len(labels) <= 60:
        raise ValueError(f"Expected 40 to 60 hand-labeled moments; got {len(labels)}")
    decider = HttpDecider(decider_url)
    judge = BedrockJudge(judge_model_id, region=region)
    context_cache: dict[str, dict[int, object]] = {}
    decider_predictions, judge_predictions = [], []
    judge_input_tokens = judge_output_tokens = 0
    records = []

    for label in labels:
        log_id, tick = label["log_id"], int(label["tick"])
        if log_id not in context_cache:
            context_cache[log_id] = contexts_for(log_id, ROOT / "replay" / "logs")
        contexts = context_cache[log_id]
        if tick not in contexts:
            raise ValueError(f"Label points outside {log_id}.jsonl: tick={tick}")
        context = contexts[tick]

        started = time.perf_counter()
        decision = decider.decide(context=context)
        decider_latency = (time.perf_counter() - started) * 1000
        decider_prediction = {
            "should_speak": decision.speak,
            "kind": decision.kind if decision.speak else None,
            "latency_ms": decider_latency,
        }
        judge_result = judge.decide(context)
        judge_prediction = {
            "should_speak": judge_result.should_speak,
            "kind": judge_result.kind,
            "latency_ms": judge_result.latency_ms,
        }
        judge_input_tokens += judge_result.input_tokens
        judge_output_tokens += judge_result.output_tokens
        decider_predictions.append(decider_prediction)
        judge_predictions.append(judge_prediction)
        records.append({
            "log_id": log_id,
            "tick": tick,
            "human": {"should_speak": label["should_speak"], "kind": label["kind"]},
            "decider": decider_prediction,
            "bedrock_judge": judge_prediction,
            "decider_matches_human": (
                decision.speak == label["should_speak"]
                and (not label["should_speak"] or decision.kind == label["kind"])
            ),
            "judge_matches_human": (
                judge_result.should_speak == label["should_speak"]
                and (not label["should_speak"] or judge_result.kind == label["kind"])
            ),
        })

    decider_metrics = _classification_metrics(labels, decider_predictions)
    judge_metrics = _classification_metrics(labels, judge_predictions)
    agreement = sum(
        human["should_speak"] == judge_prediction["should_speak"]
        for human, judge_prediction in zip(decider_predictions, judge_predictions)
    ) / len(labels)
    bedrock_cost_per_1000 = None
    if input_cost_per_million is not None and output_cost_per_million is not None:
        total_cost = (
            judge_input_tokens * input_cost_per_million
            + judge_output_tokens * output_cost_per_million
        ) / 1_000_000
        bedrock_cost_per_1000 = total_cost / len(labels) * 1000

    result = {
        "labels": len(labels),
        "judge_model_id": judge_model_id,
        "decider_endpoint": decider_url,
        "agreement_decider_vs_judge_speak": agreement,
        "decider": {**decider_metrics, "api_cost_per_1000_usd": 0.0},
        "bedrock_judge": {
            **judge_metrics,
            "input_tokens": judge_input_tokens,
            "output_tokens": judge_output_tokens,
            "cost_per_1000_usd": bedrock_cost_per_1000,
        },
        "failures": [
            row for row in records
            if not row["decider_matches_human"] or not row["judge_matches_human"]
        ],
        "records": records,
        "cost_note": (
            "Decider API inference cost is $0 because it uses local open weights; Colab compute "
            "charges are excluded. Bedrock cost is null unless input and output rates are supplied."
        ),
    }
    output_path = output_path or ROOT / "bench" / "results.json"
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    _write_svg(output_path.parent / "accuracy.svg", {
        "Decider": decider_metrics["speak_accuracy"],
        "Bedrock judge": judge_metrics["speak_accuracy"],
        "Agreement": agreement,
    })
    print("Metric                 Decider     Bedrock judge")
    print(f"Speak accuracy         {decider_metrics['speak_accuracy']:.1%}       {judge_metrics['speak_accuracy']:.1%}")
    print(f"Joint accuracy         {decider_metrics['joint_accuracy']:.1%}       {judge_metrics['joint_accuracy']:.1%}")
    print(f"Mean latency (ms)      {decider_metrics['mean_latency_ms']:.1f}        {judge_metrics['mean_latency_ms']:.1f}")
    print(f"Agreement (speak)      {agreement:.1%}")
    print(f"Judge cost / 1000      {bedrock_cost_per_1000 if bedrock_cost_per_1000 is not None else 'rates required'}")
    print(f"Saved: {output_path} and {output_path.parent / 'accuracy.svg'}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=ROOT / "bench" / "labels.jsonl")
    parser.add_argument("--decider-url", required=True)
    parser.add_argument("--judge-model-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--input-cost-per-million", type=float)
    parser.add_argument("--output-cost-per-million", type=float)
    parser.add_argument("--output", type=Path, default=ROOT / "bench" / "results.json")
    args = parser.parse_args()
    run(
        args.labels,
        args.decider_url,
        args.judge_model_id,
        region=args.region,
        input_cost_per_million=args.input_cost_per_million,
        output_cost_per_million=args.output_cost_per_million,
        output_path=args.output,
    )
