"""Local Interactive Web Dashboard (agentgit ui).

Starts a zero-dependency local web dashboard powered by Python's built-in
http.server to browse snapshots, inspect visual diffs, and replay task trajectories.

Usage::

    from agentgit.ui import start_ui
    start_ui(project_path=".", port=8585)
"""

from __future__ import annotations

import json
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from agentgit.diff import create_diff
from agentgit.storage import AgentGitStore

_HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AgentGit Dashboard</title>
  <style>
    :root {
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #3fb950;
      --green-bg: rgba(63, 185, 80, 0.15);
      --red: #f85149;
      --red-bg: rgba(248, 81, 73, 0.15);
      --yellow: #d29922;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 0;
    }
    header {
      background: var(--card);
      border-bottom: 1px solid var(--border);
      padding: 16px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .logo {
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }
    .tabs {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 8px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 15px;
      font-weight: 600;
      padding: 8px 16px;
      cursor: pointer;
      border-radius: 6px;
      transition: all 0.2s;
    }
    .tab-btn.active, .tab-btn:hover {
      background: var(--border);
      color: #fff;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 24px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      padding: 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }
    th {
      color: var(--text-muted);
      font-weight: 600;
    }
    .badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
    }
    .badge-green { background: var(--green-bg); color: var(--green); }
    .badge-red { background: var(--red-bg); color: var(--red); }
    .badge-neutral { background: rgba(139, 148, 158, 0.15); color: var(--text-muted); }
    select, button {
      background: var(--bg);
      border: 1px solid var(--border);
      color: #fff;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 14px;
      cursor: pointer;
    }
    .controls {
      display: flex;
      gap: 16px;
      align-items: center;
      margin-bottom: 16px;
    }
    pre {
      background: var(--bg);
      border: 1px solid var(--border);
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <header>
    <div class="logo">🧬 AgentGit Dashboard</div>
    <div id="agent-info" style="color: var(--text-muted); font-size: 14px;"></div>
  </header>

  <div class="container">
    <div class="tabs">
      <button class="tab-btn active" onclick="showTab('snapshots')">📸 Snapshots</button>
      <button class="tab-btn" onclick="showTab('diff')">⚖️ Behavioral Diff</button>
      <button class="tab-btn" onclick="showTab('tasks')">🔍 Task Explorer</button>
    </div>

    <!-- Snapshots Tab -->
    <div id="tab-snapshots">
      <div class="card">
        <h3 style="margin-top: 0;">Recorded Behavioral Snapshots</h3>
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th>Date</th>
              <th>Tasks</th>
              <th>Completion</th>
              <th>Avg Latency</th>
              <th>Avg Cost</th>
              <th>Error Rate</th>
            </tr>
          </thead>
          <tbody id="snapshots-body">
            <tr><td colspan="7" style="text-align: center;">Loading snapshots...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Diff Tab -->
    <div id="tab-diff" style="display: none;">
      <div class="card">
        <h3 style="margin-top: 0;">Compare Behavioral Snapshots</h3>
        <div class="controls">
          <label>Base Version: <select id="diff-base"></select></label>
          <label>Compare Version: <select id="diff-target"></select></label>
          <button onclick="runDiff()">Compare</button>
        </div>
        <div id="diff-output"></div>
      </div>
    </div>

    <!-- Task Explorer Tab -->
    <div id="tab-tasks" style="display: none;">
      <div class="card">
        <h3 style="margin-top: 0;">Task Trajectory Explorer</h3>
        <div class="controls">
          <label>Version: <select id="tasks-version" onchange="loadTasks()"></select></label>
        </div>
        <div id="tasks-list"></div>
      </div>
    </div>
  </div>

  <script>
    let snapshotsData = [];

    function showTab(tab) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('tab-snapshots').style.display = tab === 'snapshots' ? 'block' : 'none';
      document.getElementById('tab-diff').style.display = tab === 'diff' ? 'block' : 'none';
      document.getElementById('tab-tasks').style.display = tab === 'tasks' ? 'block' : 'none';
      if (tab === 'diff') populateDiffSelects();
      if (tab === 'tasks') populateTasksSelect();
    }

    async function init() {
      const res = await fetch('/api/snapshots');
      snapshotsData = await res.json();
      renderSnapshots();
    }

    function renderSnapshots() {
      const tbody = document.getElementById('snapshots-body');
      if (!snapshotsData.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No snapshots recorded yet. Run <code>agentgit snapshot &lt;version&gt;</code></td></tr>';
        return;
      }
      tbody.innerHTML = snapshotsData.map(s => `
        <tr>
          <td><strong><code>${s.version}</code></strong></td>
          <td>${s.timestamp.slice(0, 19)}</td>
          <td>${s.num_tasks}</td>
          <td><span class="badge badge-green">${(s.metrics.task_completion_rate * 100).toFixed(0)}%</span></td>
          <td>${s.metrics.avg_latency_ms.toFixed(0)} ms</td>
          <td>$${s.metrics.avg_cost_per_task.toFixed(4)}</td>
          <td>${(s.metrics.error_rate * 100).toFixed(0)}%</td>
        </tr>
      `).join('');
    }

    function populateDiffSelects() {
      const base = document.getElementById('diff-base');
      const target = document.getElementById('diff-target');
      const options = snapshotsData.map(s => `<option value="${s.version}">${s.version}</option>`).join('');
      base.innerHTML = options;
      target.innerHTML = options;
      if (snapshotsData.length > 1) target.selectedIndex = 1;
    }

    function populateTasksSelect() {
      const sel = document.getElementById('tasks-version');
      sel.innerHTML = snapshotsData.map(s => `<option value="${s.version}">${s.version}</option>`).join('');
      loadTasks();
    }

    async function runDiff() {
      const a = document.getElementById('diff-base').value;
      const b = document.getElementById('diff-target').value;
      const res = await fetch(`/api/diff?a=${a}&b=${b}`);
      const d = await res.json();

      const rows = d.changes.map(c => `
        <tr>
          <td><strong>${c.description}</strong></td>
          <td>${c.old_value}</td>
          <td>${c.new_value}</td>
          <td><span class="badge ${c.status === 'improved' ? 'badge-green' : c.status === 'regressed' ? 'badge-red' : 'badge-neutral'}">${c.delta_pct > 0 ? '+' : ''}${c.delta_pct}%</span></td>
        </tr>
      `).join('');

      document.getElementById('diff-output').innerHTML = `
        <div style="margin-top: 16px;">
          <p><strong>Verdict:</strong> ${d.verdict}</p>
          <table>
            <thead>
              <tr><th>Metric</th><th>${d.from_version}</th><th>${d.to_version}</th><th>Change</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
    }

    async function loadTasks() {
      const v = document.getElementById('tasks-version').value;
      const snap = snapshotsData.find(s => s.version === v);
      if (!snap || !snap.task_results.length) {
        document.getElementById('tasks-list').innerHTML = '<p style="color: var(--text-muted);">No task details recorded in this snapshot.</p>';
        return;
      }
      document.getElementById('tasks-list').innerHTML = snap.task_results.map((t, idx) => `
        <div class="card" style="margin-bottom: 12px; padding: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>Task #${idx + 1}</strong>
            <span class="badge ${t.success ? 'badge-green' : 'badge-red'}">${t.success ? 'PASSED' : 'FAILED'}</span>
          </div>
          <p><strong>Input:</strong> ${JSON.stringify(t.task_input)}</p>
          <p><strong>Output:</strong> ${JSON.stringify(t.output)}</p>
          <div style="font-size: 13px; color: var(--text-muted);">
            Steps: ${t.steps} • Latency: ${t.latency_ms.toFixed(0)} ms • Cost: $${t.cost_usd.toFixed(4)}
          </div>
        </div>
      `).join('');
    }

    init();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    """Handler for AgentGit Web Dashboard."""

    store: AgentGitStore

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_HTML_PAGE.encode("utf-8"))
            return

        if path == "/api/snapshots":
            snapshots = self.store.list()
            data = [s.model_dump() for s in snapshots]
            self._send_json(data)
            return

        if path == "/api/diff":
            a = params.get("a", [""])[0]
            b = params.get("b", [""])[0]
            if not a or not b:
                self.send_error(400, "Missing 'a' or 'b' query parameters")
                return
            snap_a = self.store.load(a)
            snap_b = self.store.load(b)
            diff = create_diff(snap_a, snap_b)
            self._send_json(diff.model_dump())
            return

        self.send_error(404, "Not Found")

    def _send_json(self, data: object) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        # Silence routine access logs
        return


def start_ui(project_path: str = ".", port: int = 8585, open_browser: bool = True) -> None:
    """Start the local AgentGit interactive dashboard server."""
    store = AgentGitStore(project_path)

    handler = type("ConfiguredHandler", (DashboardHandler,), {"store": store})
    server = HTTPServer(("127.0.0.1", port), handler)

    url = f"http://127.0.0.1:{port}"
    from agentgit.report import console
    console.print(f"\n[bold green]🧬 AgentGit Web Dashboard running at:[/bold green] [cyan]{url}[/cyan]")
    console.print("   Press [bold]Ctrl+C[/bold] to stop.\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")
    finally:
        server.server_close()
