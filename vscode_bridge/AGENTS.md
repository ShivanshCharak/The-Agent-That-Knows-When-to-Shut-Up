# Bridge implementation notes

- Keep the server loopback-only; the extension communicates with `127.0.0.1:8765`.
- Feed events through the shared `ContextBuilder`, `InterjectionHandler`, and `InterjectionGate` so IDE and replay behavior use the same policy.
- Serialize event handling around mutable context and gate state.
- Use the Strands Decider HTTP endpoint configured by `DECIDER_URL` (default `http://localhost:8000`). Only instantiate Bedrock when `BEDROCK_MODEL_ID` is explicitly set.
- Do not log request bodies or source text.
