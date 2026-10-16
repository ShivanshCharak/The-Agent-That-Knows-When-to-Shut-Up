# Interjection gate

A small model (Decider) watches an event stream and answers whether a thoughtful teammate should
interject and, when useful, what kind of response to make. A gate (confidence threshold, interrupt
budget, cooldown) decides whether to act. Bedrock only generates text when the gate passes.

Status: Phases 1–4 complete; live Bedrock generation is deferred. See `PROGRESS.md`.

## Decision

The Decider answers this question for each session context: **“Would a thoughtful teammate
interject right now?”** It receives the current state (editing or inspecting an error, recent
failures and speech, and repeat counts) plus the recent event history. It returns whether to speak,
a confidence value, and—when it recommends speaking—the most useful response kind:

- **Correct:** Point out a likely mistake or risk.
- **Suggest:** Offer a useful next step or idea.
- **Ask:** Ask a brief clarifying question.

For example, given an event history ending in a failed test and state showing that the developer is
editing but not inspecting the error, the model might return `speak: true`, `kind: "suggest"`,
`confidence: 0.82`. This is an illustrative model response, not a fixed rule. The gate then uses the
decision and its threshold, interrupt budget, and cooldown to decide whether to act.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m replay.runner replay/logs/sample_coding.jsonl --threshold 0.7
```

Six short labeled coding scenarios are available under `replay/logs/`. Each replay reports checks,
events skipped by rules, Decider calls, and Bedrock calls separately. The scenario labels are in
`replay/logs/scenario_labels.jsonl`.

To attach the gate to a Strands agent, provide a function that converts that agent's lifecycle event
to the project's current context:

```python
from strands import Agent
from gate.handler import InterjectionHandler, make_strands_intervention_handler

core = InterjectionHandler(decider, gate, responder=bedrock_responder)
handler = make_strands_intervention_handler(core, context_provider)
agent = Agent(interventions=[handler])
agent("Continue debugging the failing test")
```

Supplying a `BedrockResponder` and running the agent can make billable AWS calls. The default replay
does not create one or contact Bedrock.

## Dashboard

Install dependencies and launch the interactive replay dashboard:

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

The dashboard sends each replay event to the configured Strands Decider HTTP server (default
`http://localhost:8000`). The Bedrock form sends context to AWS only when submitted; it may incur
charges.

## VS Code extension (MVP)

The extension watches the active editor, saves, and error diagnostics. It sends the current file
context to the local bridge, which applies the existing Decider and gate. It does not provide inline
code completions. Bedrock-generated text is opt-in and may incur charges.

1. Open this repository in VS Code and start the bridge in an integrated terminal:

   ```bash
   source .venv/bin/activate
   DECIDER_URL=http://localhost:8000 python -m vscode_bridge.server
   ```

2. Press **F5** to open an Extension Development Host.
3. In that window, run **Interjection Gate: Run Demo** from the Command Palette to send demo events
   through the HTTP Decider. This does not contact AWS unless Bedrock response generation is enabled.

See [vscode-extension/README.md](vscode-extension/README.md) for the Decider setup and commands.
Choose the project `.venv` interpreter in VS Code if prompted. Then use the Run and Debug panel and
select **Run Interjection Gate extension**, or press **F5** from the repository window.

## Benchmark

`bench/labels.jsonl` contains 46 hand-labeled replay moments. To compare the Colab-hosted Decider
with a Bedrock judge, run the command below inside the runtime where the Decider server is reachable:

```bash
python -m bench.run \
  --decider-url http://localhost:8000 \
  --judge-model-id YOUR_BEDROCK_MODEL_ID \
  --region YOUR_AWS_REGION \
  --input-cost-per-million YOUR_INPUT_RATE \
  --output-cost-per-million YOUR_OUTPUT_RATE
```

This sends 46 judge requests to Bedrock and may incur charges. Without token rates, Bedrock cost is
reported as unknown; Colab compute charges are not included. The run writes `bench/results.json` and
`bench/accuracy.svg`.

The replay runner uses the HTTP Decider at `http://localhost:8000` by default. Start the server and
run the replay:

```bash
pip install strands-decider==0.1.0
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --device cuda --port 8000
python -m replay.runner replay/logs/sample_coding.jsonl --threshold 0.7 \
  --decider-url http://localhost:8000
```

For a GPU-backed run in Colab, start the server in a notebook cell and run the project in that
same Colab runtime. A Colab `localhost` endpoint is not reachable from your Ubuntu machine by
default.

## Layout

- `gate/`: schema, context builder, rules, gate, handler, decider clients
- `adapters/`: normalized events (coding now, transcript later)
- `replay/`: recorded logs and the replay runner
- `bench/`: Decider vs Bedrock judge (Phase 5)
- `ui/`: urge meter, slider, counters (Phase 4)
- `scripts/phase0_check.py`: environment and API checks
