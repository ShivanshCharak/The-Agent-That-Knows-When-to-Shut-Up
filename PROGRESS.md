# PROGRESS

## Phase 0: Recon (in progress)

Run `python scripts/phase0_check.py`, then fill in "Facts confirmed" below.

- [ ] Read hackathon repo README and examples
- [ ] Typed-question format recorded below
- [x] Decider model answers a hard-coded question in a Colab GPU runtime
- [x] Strands `InterventionHandler` API read; wiring approach noted
- [ ] Bedrock test call succeeds (region, model ID, credentials)

### Facts confirmed
- Typed-question format: the upstream Strands Decider uses a `state` plus a `questions` mapping. A yes/no question is `{ "type": "noul", "instructions": "..." }`; its answer has `type: "noul"` and `noul` is P(true). `choice` and `score` are also supported. A `noul` answer supplies a probability, not a separate confidence value, so the planned `confidence` field needs an explicit derivation or a different question type.
- Decider call signature / endpoint: upstream package CLI is `strands-decider ask <model-id> --state ... --noul ...`; the local HTTP interface is `POST /v1/systemone` with JSON `{ "state": ..., "questions": { "<key>": { "type": "noul", "instructions": "..." } } }`. Response contains `answers.<key>.noul`, usage, and latency. No Python client signature is confirmed yet.
- How to serve Decider locally: upstream instructions use `strands-decider serve <model-id> --port 8000`; send typed requests to `http://localhost:8000/v1/systemone`. The project checkout has no upstream examples or installed Decider package, so this has not been run here.
- Strands InterventionHandler attach point: current Python docs show a subclass of `strands.interventions.InterventionHandler` overriding lifecycle methods and an agent configured with `Agent(..., interventions=[handler])`. This is the handler attachment path for Phase 3.
- Bedrock region / model ID: not confirmed. `AWS_REGION`, `BEDROCK_MODEL_ID`, and `DECIDER_URL` are unset. AWS CLI had region `local`; a read-only STS identity check using `us-west-2` returned `InvalidClientTokenId`.
- Environment check: Python 3.12.3 passes. `boto3`, `requests`, and `python-dotenv` are installed in the workspace environment. `strands` is not installed. The Decider CLI check initially skipped because `DECIDER_URL` is unset; `strands-decider==0.1.0` is now installed in `/tmp/strands-decider-env`. `python scripts/phase0_check.py` reported skips for model and cloud calls before that installation.
- Installation attempt: `strands-decider==0.1.0` and CPU-only `torch==2.7.1` are installed in `/tmp/strands-decider-env`. No Bedrock call was attempted at the user's request. A normal sandbox hardware check could not see the GPU; an approved host check later confirmed an NVIDIA GeForce GTX 1650 with 4 GiB VRAM (about 3.7 GiB free). The installed PyTorch build is CPU-only. The user ran the local CLI on CPU; it downloaded the 4.55 GB model weights and was then killed with exit 137 while loading. The OS recorded three OOM kills in `user.slice`. The Hugging Face cache is about 7.0 GB, so the next attempt need not redownload the model. Current host memory check after the failed attempt: 7.1 GiB RAM total, about 3.6 GiB available, and 3.4 of 4 GiB swap used.
- Colab GPU inference: the exact CLI command completed on a Tesla T4 (`torch.cuda.is_available() == True`). It returned `answers.noul_0.noul = 0.582` for the fixed question, with 91 input tokens and 1 output token. The model weights downloaded and loaded successfully. Optional `causal_conv1d` and `flash-linear-attention` kernels were absent, so Transformers used slower reference PyTorch implementations.

### Deviations from the plan
- The checked out GitHub repository currently contains only a title README; the current source tree is a local, uncommitted project skeleton. Upstream Strands Decider documentation was used to record the wire format, but the local model call and Bedrock call remain unverified.
- The plan's `confidence` output is not directly returned by a `noul` question. Resolve this before implementing the Decider adapter in Phase 1.
- Bedrock access test is deferred at the user's request to avoid a potentially billable inference call.
- Decider package and model download succeeded, but local inference remains unverified because the process was OOM-killed on CPU. The visible GPU has 4 GiB VRAM, below the 4.55 GB model weight file, and the installed PyTorch build is CPU-only. A dummy endpoint would not satisfy the local model acceptance check.
- The fixed-question model inference is now verified on Colab's Tesla T4 GPU. This does not expose the model to the local Ubuntu project; integration will require running project code in the same Colab runtime or providing a network endpoint. Bedrock remains deferred by user choice.

## Phase 1: Core decision loop (complete)

- [x] Normalized `Event` moved to `adapters/base.py`
- [x] Context tracks recent events, last failure age, editing/traceback state, repeat count, and time since last interjection
- [x] Configurable gate for threshold, rolling interrupt budget, and cooldown
- [x] Replay uses the Strands Decider HTTP endpoint; deterministic mock mode has been removed
- [x] A 30-event hand-written coding replay is present
- [x] Tests cover gate threshold, cooldown, budget, Decider wire mapping, and replay determinism
- [x] Hand-written 30-event coding log replays end to end with repeatable outcomes

### Phase 1 decisions
- The HTTP adapter sends a `noul` question for whether to interject and a `choice` question for `correct | suggest | ask` in the same `/v1/systemone` request.
- The `noul` answer is P(interject), so it drives both the boolean decision (`>= 0.5`) and the existing urge/confidence value. The gate's configurable threshold still controls whether that decision is allowed through.
- Bedrock call count stays zero in Phase 1; the gate only records that it would pass an interjection.

### Phase 1 blocker for live integration
- The model was confirmed in Colab's runtime, but this project runs on the Ubuntu host. The adapter is implemented and covered with mocked HTTP responses; the live server call still requires running the project in the Colab runtime or exposing an endpoint deliberately.

### Phase 1 verification
- `python -m unittest discover -s tests -v`: 8 tests passed.
- Sample replay: 30 checks, 2 rule-skipped, 28 Decider calls, 0 Bedrock calls.
- The live HTTP adapter has not yet been exercised against Colab; it can be tested when both the project and server run in the Colab runtime.

### Phase boundary decision
- The Phase 0 Bedrock acceptance check remains deferred because the user chose to avoid potentially billable inference. The user explicitly asked to continue, so Phase 1 proceeded with the local model smoke test verified on Colab and Bedrock excluded.

## Phase 2: Scenarios and rule layer (complete)

- [x] Six recorded coding scenarios cover traceback reading, repeated errors, long idle, rapid edits, first try fix, and unnoticed risky change.
- [x] `file_open` is skipped by deterministic rules; events are still retained in the context window.
- [x] Replays report rule-skipped events, Decider calls, and Bedrock calls separately.
- [x] Scenario labels verify the expected speak/kind outcomes and required context events.

### Phase 2 verification
- `python -m unittest discover -s tests -v`: 9 tests passed.
- Each of the six scenario replays prints separate check, skipped, Decider, and Bedrock counts.
- Label coverage confirms the `file_open` event remains available in context and none of the labeled target or dependency events are filtered out.

## Phase 3: Bedrock and Strands handler (complete; live Bedrock deferred)

- [x] Kind-specific Bedrock response prompts and a Converse API client are implemented.
- [x] Bedrock is called only after a gate pass when an explicit responder is configured.
- [x] Optional Strands `InterventionHandler` adapter injects the response as `Guide` feedback before a model call.
- [x] Replay log lines include tick, decision, kind, confidence, gate outcome, Bedrock call flag, and response text when generated.
- [x] Tests mock the responder/SDK, including an assertion that gate failure never calls Bedrock.
- [x] Fake-responder replay confirms text appears only on gate-pass ticks.
- [x] Attach the handler to a real minimal Strands `Agent`; verify a passing gate returns `Guide` feedback without invoking the agent model.
- [ ] Live Bedrock generation (deferred: user asked to avoid potentially billable calls).

### Phase 3 API reference
- Strands Python `InterventionHandler` lifecycle and `Guide` action: https://strandsagents.com/docs/user-guide/sdk/agents/interventions/ (read 2026-10-15).
- `python -m unittest discover -s tests -v`: 14 tests passed; no AWS Bedrock requests were made.
- Installed `strands-agents==1.61.0` into `/tmp/strands-decider-env`. A real `Agent(interventions=[handler])` registered the handler, and its lifecycle callback returned `Guide` text after a passing gate. The model itself was not invoked, so there was no Bedrock call.
- Live Bedrock generation remains unverified by choice; mock-responder replay tests verify that generation happens only on allowed gate ticks.

## Phase 4: UI (complete; Bedrock remains opt-in)

- [x] Streamlit dashboard shows the recorded event stream and gate decisions.
- [x] Urge meter and chart show the model's P(interject) score on every Decider tick.
- [x] Chattiness slider reruns the same replay at the selected threshold.
- [x] Counters show checks, rule skips, Decider calls, Bedrock calls, and allowed interjections.
- [x] Three-threshold comparison shows counts and per-tick outcomes for the same log.
- [x] Optional Bedrock form displays generated text; submission is explicit and may incur AWS charges.

### Phase 4 verification
- Streamlit AppTest rendered the dashboard and changing the threshold from 0.70 to 0.90 changed interjections from 3 to 2 on the sample log.
- Dashboard and comparison use the replay runner's returned records and counters; no Bedrock call was made during UI verification.
- Installed `streamlit==1.66.0` in `/tmp/strands-decider-env` for local UI verification.

## Phase 5: Benchmark (in progress; live judge calls deferred)

- [x] Hand-labeled 46 moments in `bench/labels.jsonl` before running this benchmark harness.
- [x] Bedrock judge returns a structured speak/kind decision plus token usage and latency.
- [x] Benchmark compares Decider and judge against human labels, calculates agreement/accuracy/latency, estimates cost when rates are supplied, and lists disagreements by log/tick.
- [x] Successful runs save `bench/results.json` and render `bench/accuracy.svg`.
- [ ] Run against the live Decider endpoint and Bedrock judge.

### Phase 5 verification and boundary
- `python -m unittest discover -s tests -v`: 17 tests passed; the Bedrock judge test uses a fake client.
- No live Decider or Bedrock requests were made. The benchmark needs 46 Bedrock judge calls, which may be billable; the user previously asked to avoid such calls.
- Results and chart are intentionally not populated with mock outputs. The live benchmark remains pending, so Phase 5 is not committed or marked complete.
