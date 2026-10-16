# VS Code bridge

Start from the repository root with the project virtual environment active:

```bash
DECIDER_URL=http://localhost:8000 python -m vscode_bridge.server
```

The service binds only to `127.0.0.1:8765`. `GET /health` reports mode and threshold. `POST /event` accepts normalized events with the current file context and returns the Decider decision and gate result. File content is capped at 12,000 characters. The service does not log file contents.

The bridge always uses the Strands Decider HTTP API. The default `DECIDER_URL` is `http://localhost:8000`. For a Colab-hosted Decider, set `DECIDER_URL`, `DECIDER_USERNAME`, and `DECIDER_PASSWORD`. The auth values are sent as HTTP Basic Auth; use HTTPS when the endpoint is remote. For configuration and use from VS Code, see [the extension guide](../vscode-extension/README.md).
