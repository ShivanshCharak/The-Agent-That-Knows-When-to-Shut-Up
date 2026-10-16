"""Local dashboard for HTTP-backed replay and opt-in Bedrock output."""
from pathlib import Path
import os
import sys

import pandas as pd
import streamlit as st

# Streamlit runs this file as a script under ``ui/``. Add the repository root
# explicitly so sibling packages such as ``gate`` and ``replay`` are importable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gate.bedrock import BedrockResponder
from replay.runner import run


LOG_DIR = ROOT / "replay" / "logs"
LOGS = sorted(
    (path for path in LOG_DIR.glob("*.jsonl") if path.name != "scenario_labels.jsonl"),
    key=lambda path: (path.name != "sample_coding.jsonl", path.name),
)


st.set_page_config(page_title="Interjection Gate", layout="wide")
st.title("The Agent That Knows When to Shut Up")
st.caption("Replay coding sessions, inspect the urge score, and see which interruptions pass the gate.")

if not LOGS:
    st.error("No replay logs found in replay/logs.")
    st.stop()

selected_name = st.selectbox("Coding replay", [path.name for path in LOGS])
selected_path = next(path for path in LOGS if path.name == selected_name)
threshold = st.slider("Chattiness threshold", 0.0, 1.0, 0.7, 0.05,
                      help="Lower values allow more interjections; higher values keep the agent quieter.")
decider_url = st.text_input(
    "Decider server URL", os.environ.get("DECIDER_URL", "http://localhost:8000")
)

try:
    report = run(str(selected_path), threshold, verbose=False, decider_url=decider_url)
except Exception as exc:  # Keep startup errors visible in the dashboard.
    st.error(f"Replay failed: {exc}")
    st.stop()

records = report["ticks"]
st.subheader("Live counters")
checks, skipped, calls, bedrock, interjections = st.columns(5)
checks.metric("Checks", report["checks"])
skipped.metric("Rule skipped", report["rule_skipped"])
calls.metric("Decider calls", report["decider_calls"])
bedrock.metric("Bedrock calls", report["bedrock_calls"])
interjections.metric("Interjections", sum(row["gate"]["allowed"] for row in records))

urge_rows = [
    {"tick": row["tick"], "urge": row["confidence"]}
    for row in records if row["confidence"] is not None
]
left, right = st.columns([1, 2])
with left:
    st.subheader("Urge to speak")
    if urge_rows:
        latest_urge = urge_rows[-1]["urge"]
        st.metric("Latest score", f"{latest_urge:.2f}")
        st.progress(max(0.0, min(1.0, latest_urge)))
        st.caption("The score is P(interject) returned by the Strands Decider.")
    else:
        st.info("All events in this replay were skipped by rules.")
with right:
    st.subheader("Urge over time")
    if urge_rows:
        st.line_chart(pd.DataFrame(urge_rows), x="tick", y="urge")

st.subheader("Event stream")
stream_rows = []
for row in records:
    decision = row["decision"] or {}
    stream_rows.append({
        "tick": row["tick"],
        "event": row["event"],
        "urge": row["confidence"],
        "speak": decision.get("speak"),
        "kind": decision.get("kind"),
        "gate": row["gate"]["reason"],
        "Bedrock": row["bedrock_called"],
    })
st.dataframe(pd.DataFrame(stream_rows), hide_index=True, width="stretch")

with st.expander("Compare three thresholds"):
    threshold_reports = {
        "Low (0.35)": run(str(selected_path), 0.35, verbose=False, decider_url=decider_url),
        "Medium (0.70)": run(str(selected_path), 0.70, verbose=False, decider_url=decider_url),
        "High (0.90)": run(str(selected_path), 0.90, verbose=False, decider_url=decider_url),
    }
    summary = []
    for label, value in threshold_reports.items():
        summary.append({
            "threshold": label,
            "checks": value["checks"],
            "rule skipped": value["rule_skipped"],
            "Decider calls": value["decider_calls"],
            "interjections": sum(item["gate"]["allowed"] for item in value["ticks"]),
        })
    st.dataframe(pd.DataFrame(summary), hide_index=True, width="stretch")
    by_tick = []
    for index, base_row in enumerate(threshold_reports["Medium (0.70)"]["ticks"]):
        by_tick.append({
            "tick": base_row["tick"],
            "event": base_row["event"],
            "low": threshold_reports["Low (0.35)"]["ticks"][index]["gate"]["allowed"],
            "medium": base_row["gate"]["allowed"],
            "high": threshold_reports["High (0.90)"]["ticks"][index]["gate"]["allowed"],
        })
    st.dataframe(pd.DataFrame(by_tick), hide_index=True, width="stretch")

st.subheader("Optional Bedrock response")
st.caption("This sends replay context to AWS Bedrock and may incur charges. It runs only when you submit the form below.")
with st.form("bedrock_run"):
    bedrock_model_id = st.text_input("Bedrock model ID", placeholder="Enter a model ID you can access")
    region = st.text_input("AWS region (optional)", placeholder="Uses your AWS SDK default if empty")
    generate = st.form_submit_button("Run this replay with Bedrock")

if generate:
    if not bedrock_model_id.strip():
        st.error("Enter a Bedrock model ID first.")
    else:
        try:
            responder = BedrockResponder(bedrock_model_id.strip(), region=region.strip() or None)
            bedrock_report = run(
                str(selected_path), threshold, verbose=False,
                decider_url=decider_url, responder=responder,
            )
            st.session_state["bedrock_run"] = {
                "log": selected_name,
                "threshold": threshold,
                "report": bedrock_report,
            }
        except Exception as exc:
            st.error(f"Bedrock replay failed: {exc}")

saved = st.session_state.get("bedrock_run")
if saved:
    st.caption(f"Saved Bedrock run: {saved['log']} at threshold {saved['threshold']:.2f}")
    st.metric("Bedrock calls in saved run", saved["report"]["bedrock_calls"])
    messages = [row for row in saved["report"]["ticks"] if row["bedrock_text"]]
    if messages:
        for row in messages:
            st.markdown(f"**Tick {row['tick']} · {row['decision']['kind']}**  \n{row['bedrock_text']}")
    else:
        st.info("No gate-pass ticks produced a Bedrock response in the saved run.")
