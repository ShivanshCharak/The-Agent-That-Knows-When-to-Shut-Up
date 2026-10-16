const vscode = require("vscode");

const ERROR_SEVERITY = vscode.DiagnosticSeverity.Error;
const MAX_ACTIVITY = 40;

class DashboardProvider {
  constructor(context, getState, toggleMonitoring, checkActiveFile, runDemo) {
    this.context = context;
    this.getState = getState;
    this.toggleMonitoring = toggleMonitoring;
    this.checkActiveFile = checkActiveFile;
    this.runDemo = runDemo;
    this.view = undefined;
  }

  resolveWebviewView(view) {
    this.view = view;
    view.webview.options = { enableScripts: true };
    view.webview.html = this.html(view.webview);
    view.webview.onDidReceiveMessage(async message => {
      if (message?.type === "toggle") await this.toggleMonitoring();
      if (message?.type === "check") await this.checkActiveFile();
      if (message?.type === "demo") await this.runDemo();
    }, undefined, this.context.subscriptions);
    this.update();
  }

  update() {
    this.view?.webview.postMessage({ type: "state", state: this.getState() });
  }

  html(webview) {
    const nonce = [...Array(24)].map(() => Math.random().toString(36)[2] || "0").join("");
    const icon = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, "media", "eye.svg"));
    return `<!doctype html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource}; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
<title>Interjection Gate</title>
<style nonce="${nonce}">
:root{color-scheme:light dark}*{box-sizing:border-box}body{padding:0 16px 18px;color:var(--vscode-foreground);font:13px var(--vscode-font-family);background:var(--vscode-sideBar-background)}
.brand{display:flex;align-items:center;gap:10px;padding:17px 0 12px}.brand img{width:24px;height:24px}.brand h1{font-size:16px;margin:0}.sub{color:var(--vscode-descriptionForeground);margin:0 0 15px;line-height:1.45}
.card{border:1px solid var(--vscode-panel-border);background:var(--vscode-editor-background);border-radius:8px;padding:12px;margin:10px 0}.row{display:flex;justify-content:space-between;align-items:center;gap:8px}.label{color:var(--vscode-descriptionForeground);font-size:11px;text-transform:uppercase;letter-spacing:.06em}.value{font-weight:600}.good{color:var(--vscode-testing-iconPassed)}.bad{color:var(--vscode-errorForeground)}.muted{color:var(--vscode-descriptionForeground)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.stat{padding:10px 7px;border-radius:6px;background:var(--vscode-sideBar-background);text-align:center}.stat strong{display:block;font-size:18px;margin-bottom:3px}.stat span{font-size:10px;color:var(--vscode-descriptionForeground)}
.buttons{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:12px 0}.buttons button{padding:7px 5px;color:var(--vscode-button-foreground);background:var(--vscode-button-background);border:0;border-radius:4px;cursor:pointer}.buttons button:hover{background:var(--vscode-button-hoverBackground)}.buttons .secondary{color:var(--vscode-button-secondaryForeground);background:var(--vscode-button-secondaryBackground)}
.section{display:flex;align-items:center;justify-content:space-between;margin:18px 0 8px}.section h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin:0}.event{padding:10px 0;border-top:1px solid var(--vscode-panel-border)}.event-title{font-weight:600}.event-meta{font-size:11px;color:var(--vscode-descriptionForeground);margin-top:4px;word-break:break-word}.pill{font-size:10px;border-radius:10px;padding:2px 7px;background:var(--vscode-badge-background);color:var(--vscode-badge-foreground)}.empty{padding:14px 2px;color:var(--vscode-descriptionForeground);line-height:1.5}
</style></head><body>
<header class="brand"><img src="${icon}" alt=""><h1>Interjection Gate</h1></header>
<p class="sub">See what the extension notices and why it speaks or stays quiet.</p>
<section class="card"><div class="row"><span class="label">Monitoring</span><span id="monitoring" class="value">Loading…</span></div>
<div class="row" style="margin-top:12px"><span class="label">Local bridge</span><span id="bridge" class="value muted">Checking…</span></div>
<div class="row" style="margin-top:9px"><span class="label">Decider</span><span id="decider" class="value muted">Waiting for first check</span></div>
<div class="row" style="margin-top:9px"><span class="label">Threshold</span><span id="threshold" class="value">—</span></div></section>
<section class="card stats"><div class="stat"><strong id="events">0</strong><span>EVENTS</span></div><div class="stat"><strong id="allowed">0</strong><span>INTERJECTIONS</span></div><div class="stat"><strong id="quiet">0</strong><span>STAYED QUIET</span></div></section>
<div class="buttons"><button id="toggle">Pause monitoring</button><button class="secondary" id="check">Check active file</button><button class="secondary" id="demo" style="grid-column:1/-1">Run demo</button></div>
<div class="section"><h2>Recent activity</h2><span id="last" class="muted"></span></div><div id="activity" class="empty">No activity yet. Open or save a code file, or check the active file.</div>
<script nonce="${nonce}">
const vscode=acquireVsCodeApi();
document.getElementById('toggle').onclick=()=>vscode.postMessage({type:'toggle'});
document.getElementById('check').onclick=()=>vscode.postMessage({type:'check'});
document.getElementById('demo').onclick=()=>vscode.postMessage({type:'demo'});
function setStatus(id,text,ok){const e=document.getElementById(id);e.textContent=text;e.className='value '+(ok===true?'good':ok===false?'bad':'muted')}
function render(s){setStatus('monitoring',s.enabled?'On':'Paused',s.enabled);setStatus('bridge',s.bridge.status,s.bridge.ok);setStatus('decider',s.decider.status,s.decider.ok);document.getElementById('threshold').textContent=s.threshold.toFixed(2);document.getElementById('events').textContent=s.stats.events;document.getElementById('allowed').textContent=s.stats.allowed;document.getElementById('quiet').textContent=s.stats.quiet;document.getElementById('toggle').textContent=s.enabled?'Pause monitoring':'Resume monitoring';
const list=document.getElementById('activity');list.replaceChildren();document.getElementById('last').textContent=s.activity.length?new Date(s.activity[0].time).toLocaleTimeString():'';
if(!s.activity.length){list.className='empty';list.textContent='No activity yet. Open or save a code file, or check the active file.';return}list.className='';
for(const item of s.activity){const row=document.createElement('div');row.className='event';const top=document.createElement('div');top.className='row';const title=document.createElement('span');title.className='event-title';title.textContent=item.file||'Workspace event';const pill=document.createElement('span');pill.className='pill';pill.textContent=item.outcome;top.append(title,pill);const meta=document.createElement('div');meta.className='event-meta';meta.textContent=item.detail;const time=document.createElement('div');time.className='event-meta';time.textContent=new Date(item.time).toLocaleTimeString()+' · '+item.kind.replaceAll('_',' ');row.append(top,meta,time);list.append(row)}}
window.addEventListener('message',event=>{if(event.data.type==='state')render(event.data.state)});
</script></body></html>`;
  }
}

function activate(context) {
  let bridgeWarningShown = false;
  const diagnosticSignatures = new Map();
  const state = {
    enabled: true,
    threshold: vscode.workspace.getConfiguration("interjection").get("threshold", 0.7),
    bridge: { status: "Checking…", ok: null },
    decider: { status: "Waiting for first check", ok: null },
    stats: { events: 0, allowed: 0, quiet: 0 },
    activity: []
  };
  let dashboard;
  let status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  status.command = "interjection.openDashboard";
  context.subscriptions.push(status);

  const isEnabled = () => vscode.workspace.getConfiguration("interjection").get("enabled", true);
  state.enabled = isEnabled();
  function publish() { dashboard?.update(); }
  function record(kind, document, result, error) {
    const file = document ? vscode.workspace.asRelativePath(document.uri, false) : "Workspace event";
    let outcome = "Checked";
    let detail = "Event processed";
    if (error) {
      outcome = "Request failed";
      detail = error.message || String(error);
      state.decider = { status: "Request failed", ok: false };
    } else if (result?.skipped) {
      outcome = "Context updated";
      detail = "Saved to context; rules skipped a model call for this event";
    } else if (result?.decision) {
      const confidence = Number(result.decision.confidence || 0).toFixed(2);
      outcome = result.allowed ? "Interjection" : "Stayed quiet";
      detail = `Score ${confidence} · ${result.reason || (result.allowed ? "gate allowed" : "gate held back")}`;
      state.decider = { status: "Responding", ok: true };
      if (result.allowed) state.stats.allowed += 1;
      else state.stats.quiet += 1;
    }
    state.stats.events += 1;
    state.activity.unshift({ time: Date.now(), kind, file, outcome, detail });
    state.activity.length = Math.min(state.activity.length, MAX_ACTIVITY);
    publish();
  }
  async function checkBridge() {
    const endpoint = vscode.workspace.getConfiguration("interjection").get("endpoint", "http://127.0.0.1:8765").replace(/\/$/, "");
    try {
      const response = await fetch(`${endpoint}/health`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const health = await response.json();
      state.bridge = { status: health.ok ? "Connected" : "Unavailable", ok: Boolean(health.ok) };
      if (health.threshold !== undefined) state.threshold = Number(health.threshold);
      publish();
    } catch (_) {
      state.bridge = { status: "Disconnected", ok: false };
      publish();
    }
  }
  const refreshStatus = () => {
    state.enabled = isEnabled();
    status.text = state.enabled ? "$(eye) Gate On" : "$(eye-closed) Gate Paused";
    status.tooltip = "Open the Interjection Gate dashboard";
    status.show();
    publish();
  };
  refreshStatus();

  async function send(kind, document, extra = {}) {
    if (!isEnabled() || !document || document.uri.scheme !== "file") return null;
    const config = vscode.workspace.getConfiguration("interjection");
    const endpoint = config.get("endpoint", "http://127.0.0.1:8765").replace(/\/$/, "");
    const limit = config.get("fileContextLimit", 12000);
    const editor = vscode.window.activeTextEditor;
    const isActive = editor && editor.document.uri.toString() === document.uri.toString();
    const selection = isActive ? document.getText(editor.selection).slice(0, limit) : "";
    const diagnostics = vscode.languages.getDiagnostics(document.uri)
      .filter(item => item.severity === ERROR_SEVERITY)
      .map(item => ({
        message: item.message,
        code: item.code && (typeof item.code === "object" ? item.code.value : item.code),
        line: item.range.start.line + 1
      }));
    const payload = {
      file: vscode.workspace.asRelativePath(document.uri, false),
      language: document.languageId,
      content: document.getText().slice(0, limit),
      selection,
      diagnostics,
      ...extra
    };

    try {
      const response = await fetch(`${endpoint}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, ts: Date.now() / 1000, payload })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      bridgeWarningShown = false;
      state.bridge = { status: "Connected", ok: true };
      record(kind, document, result);
      if (result.allowed) {
        if (result.response) {
          vscode.window.showInformationMessage(`Interjection Gate: ${result.response}`);
        } else {
          vscode.window.showInformationMessage(
            `Interjection Gate would ${result.decision.kind} (score ${result.decision.confidence.toFixed(2)}). Configure Bedrock for a generated response.`
          );
        }
      }
      return result;
    } catch (error) {
      if (error.message && /^HTTP \d+$/.test(error.message)) {
        state.bridge = { status: "Connected", ok: true };
        state.decider = { status: "Request failed", ok: false };
      }
      record(kind, document, null, error);
      if (!bridgeWarningShown) {
        bridgeWarningShown = true;
        vscode.window.showWarningMessage(`Interjection request failed. Check the local bridge and Decider endpoint (${error.message})`);
      }
      return null;
    }
  }

  context.subscriptions.push(vscode.commands.registerCommand("interjection.toggle", async () => {
    const config = vscode.workspace.getConfiguration("interjection");
    await config.update("enabled", !isEnabled(), vscode.ConfigurationTarget.Global);
    refreshStatus();
    vscode.window.showInformationMessage(`Interjection Gate ${isEnabled() ? "enabled" : "paused"}.`);
  }));

  dashboard = new DashboardProvider(context, () => ({
    ...state,
    enabled: isEnabled(),
    activity: state.activity.map(item => ({ ...item }))
  }),
  async () => vscode.commands.executeCommand("interjection.toggle"),
  async () => vscode.commands.executeCommand("interjection.checkActiveFile"),
  async () => vscode.commands.executeCommand("interjection.runDemo"));
  context.subscriptions.push(vscode.window.registerWebviewViewProvider("interjection.dashboard", dashboard));
  context.subscriptions.push(vscode.commands.registerCommand("interjection.openDashboard", async () => {
    await vscode.commands.executeCommand("workbench.view.extension.interjection");
  }));
  const healthTimer = setInterval(checkBridge, 10000);
  context.subscriptions.push({ dispose: () => clearInterval(healthTimer) });
  checkBridge();

  context.subscriptions.push(vscode.commands.registerCommand("interjection.checkActiveFile", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return vscode.window.showInformationMessage("Open a file first.");
    const result = await send("edit", editor.document, { source: "manual_check" });
    if (result && !result.allowed) {
      vscode.window.showInformationMessage(`Gate stayed quiet (${result.reason}, score ${result.decision.confidence.toFixed(2)}).`);
    }
  }));

  context.subscriptions.push(vscode.commands.registerCommand("interjection.runDemo", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return vscode.window.showInformationMessage("Open a file first.");
    for (let i = 0; i < 3; i += 1) {
      await send("test_fail", editor.document, { error: "demo-repeated-error", source: "demo" });
    }
  }));

  context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(editor => {
    if (editor) send("file_open", editor.document, { source: "active_editor" });
  }));

  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(document => {
    const errors = vscode.languages.getDiagnostics(document.uri)
      .filter(item => item.severity === ERROR_SEVERITY);
    if (errors.length) {
      const message = errors.map(item => `${item.code || "error"}: ${item.message}`).join(" | ").slice(0, 1000);
      send("test_fail", document, { error: message, source: "editor_diagnostics" });
    } else {
      send("edit", document, { source: "save" });
    }
  }));

  context.subscriptions.push(vscode.languages.onDidChangeDiagnostics(event => {
    const editor = vscode.window.activeTextEditor;
    if (!editor || !event.uris.some(uri => uri.toString() === editor.document.uri.toString())) return;
    const document = editor.document;
    const errors = vscode.languages.getDiagnostics(document.uri)
      .filter(item => item.severity === ERROR_SEVERITY);
    const signature = errors.map(item => `${item.code || "error"}: ${item.message}`).join(" | ").slice(0, 1000);
    const previous = diagnosticSignatures.get(document.uri.toString()) || "";
    if (signature === previous) return;
    diagnosticSignatures.set(document.uri.toString(), signature);
    if (signature) {
      send("test_fail", document, { error: signature, source: "editor_diagnostics" });
    } else if (previous) {
      send("test_pass", document, { source: "diagnostics_cleared" });
    }
  }));

  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(event => {
    if (event.affectsConfiguration("interjection.enabled")) refreshStatus();
    if (event.affectsConfiguration("interjection.endpoint")) checkBridge();
  }));

  const editor = vscode.window.activeTextEditor;
  if (editor) send("file_open", editor.document, { source: "startup" });
}

function deactivate() {}

module.exports = { activate, deactivate };
