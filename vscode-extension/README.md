# VS Code extension

The extension watches the active editor, saves, and error diagnostics. It sends the active file (up to the configured character limit), language, selection, and diagnostics to the local Python bridge. The bridge runs Decider and the existing threshold/cooldown/interrupt-budget gate. A Bedrock response is generated only when `BEDROCK_MODEL_ID` is explicitly configured and the gate passes.

The extension does not provide inline completions. It shows a short notification only for an allowed interjection.

The **Interjection Gate** activity-bar view shows whether monitoring and the local bridge are available, the configured threshold, and a recent event feed with model scores and gate outcomes. It records file names and decision details only; source contents are not shown in the dashboard. Open it from the eye icon or run **Interjection Gate: Open Dashboard** from the Command Palette.

## Run from VS Code

1. Open this repository folder in VS Code.
2. (Optional) Select the project interpreter with **Python: Select Interpreter** and choose `.venv/bin/python` (`.venv\Scripts\python.exe` on Windows).
3. In an integrated terminal at the repository root, start the local bridge:

   ```bash
   source .venv/bin/activate
   DECIDER_URL=http://localhost:8000 python -m vscode_bridge.server
   ```

   On Windows PowerShell, activate with `\.venv\Scripts\Activate.ps1`, then run `python -m vscode_bridge.server`. Set `DECIDER_URL` and optional HTTP Basic Auth credentials if the Decider is not at the default local URL.

4. Press **F5** from the repository window. VS Code opens an Extension Development Host with the extension active.
5. In the new window, open any source file. The status bar shows **Gate On**. Opening a file sends its current buffer to the local bridge; saving or an error-diagnostic change sends a relevant event.

## Send demo events

In the Extension Development Host, open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and run **Interjection Gate: Run Demo**. The demo sends three error events through the configured HTTP Decider. The resulting notification depends on the model decision and gate state. AWS Bedrock is contacted only when `BEDROCK_MODEL_ID` is configured and the gate passes.

Run **Interjection Gate: Toggle Monitoring** to pause/resume event sharing. **Interjection Gate: Check Active File** sends a single active-file context check.

Close the Extension Development Host when finished. Stop the bridge in its terminal with `Ctrl+C`.

## Use Strands Decider 2B

You already ran Strands Decider 2B on Colab. The existing notebook uses `strands-decider ask` for a one-time question; it does not start a persistent HTTP server. The extension bridge needs a server URL it can reach from your computer. `localhost:8000` only works if the Decider server is running on the same computer as VS Code.

The Colab notebook now has cells to start the model server and publish it through a password-protected ngrok HTTPS tunnel:

1. In Colab, open the notebook Secrets panel and add `NGROK_AUTHTOKEN`, `DECIDER_TUNNEL_USERNAME`, and `DECIDER_TUNNEL_PASSWORD`. Use at least 16 letters, digits, underscores, or hyphens for each tunnel credential, and grant the notebook access to them.
2. Select a GPU runtime, then run the install, GPU check, and one-shot smoke-test cells.
3. Run **Start the model server**, wait for it to report port 8000, then run **Open a password-protected HTTPS tunnel**. Copy the printed URL. Keep the runtime and tunnel cell running.
4. In a local VS Code terminal at the repository root, configure the bridge with the URL and the same tunnel credentials:

```bash
source .venv/bin/activate
export INTERJECTION_THRESHOLD=0.7
export DECIDER_URL='https://YOUR_NGROK_HOST'
export DECIDER_USERNAME='YOUR_TUNNEL_USERNAME'
read -rsp 'Colab tunnel password: ' DECIDER_PASSWORD; echo
export DECIDER_PASSWORD
python -m vscode_bridge.server
```

5. Press **F5** in the VS Code repository window. The Extension Development Host will send saves and diagnostic changes to the local bridge, which forwards them to Colab. No Bedrock calls happen unless `BEDROCK_MODEL_ID` is set.

The current file context (up to 12,000 characters) travels from VS Code through the tunnel to your Colab runtime. Keep the tunnel password private and stop the server/tunnel when finished. The ngrok tunnel uses HTTPS and Basic Auth; ngrok's Python SDK supports forwarding localhost endpoints with traffic policies. [ngrok Python quickstart](https://ngrok.com/download/python), [ngrok Basic Auth](https://ngrok.com/docs/traffic-policy/actions/basic-auth/).

To enable generated response text, set `BEDROCK_MODEL_ID` (and `AWS_REGION` if needed) before starting the local bridge. Bedrock calls may incur charges when the gate passes.
