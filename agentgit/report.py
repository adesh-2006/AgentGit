"""Beautiful terminal and exportable reports using Rich, Markdown, and HTML.

Produces the polished terminal output, GitHub Pull Request markdown tables,
and interactive standalone HTML reports.
"""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentgit.diff import BehavioralDiff, ChangeStatus
from agentgit.snapshot import BehavioralSnapshot

console = Console()

# ---------------------------------------------------------------------------
# Metric display helpers
# ---------------------------------------------------------------------------

_METRIC_FMT = {
    "task_completion_rate": ("Task Completion", lambda v: f"{v:.0%}"),
    "avg_steps_per_task": ("Avg Steps / Task", lambda v: f"{v:.1f}"),
    "avg_latency_ms": ("Avg Latency", lambda v: f"{v:,.0f} ms"),
    "avg_tokens_per_task": ("Avg Tokens / Task", lambda v: f"{v:,.0f}"),
    "avg_cost_per_task": ("Avg Cost / Task", lambda v: f"${v:.4f}"),
    "total_cost_usd": ("Total Cost", lambda v: f"${v:.4f}"),
    "error_rate": ("Error Rate", lambda v: f"{v:.0%}"),
}


# ---------------------------------------------------------------------------
# Snapshot report
# ---------------------------------------------------------------------------

def print_snapshot_report(snapshot: BehavioralSnapshot) -> None:
    """Print a rich snapshot summary to the terminal."""
    m = snapshot.metrics

    table = Table(
        title="",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        title_style="bold",
    )
    table.add_column("Metric", style="white", min_width=20)
    table.add_column("Value", style="bold", justify="right", min_width=15)

    for field, (label, fmt) in _METRIC_FMT.items():
        val = getattr(m, field, 0)
        table.add_row(label, fmt(val))

    # Tool usage
    if m.tool_usage:
        table.add_section()
        table.add_row("[bold]Tool Usage[/bold]", "")
        for tool, count in sorted(m.tool_usage.items(), key=lambda x: -x[1]):
            table.add_row(f"  {tool}", str(count))

    header = Text.assemble(
        ("AgentGit Snapshot: ", "bold white"),
        (snapshot.version, "bold green"),
        ("  •  ", "dim"),
        (f"{snapshot.num_tasks} tasks", "cyan"),
        ("  •  ", "dim"),
        (snapshot.agent_name, "yellow"),
    )

    console.print()
    console.print(Panel(table, title=header, border_style="blue", padding=(1, 2)))
    console.print()


# ---------------------------------------------------------------------------
# Diff report (Terminal)
# ---------------------------------------------------------------------------

def print_diff_report(d: BehavioralDiff) -> None:
    """Print a rich behavioral diff to the terminal."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Metric", style="white", min_width=20)
    table.add_column(d.from_version, justify="right", min_width=12)
    table.add_column(d.to_version, justify="right", min_width=12)
    table.add_column("Change", justify="right", min_width=12)
    table.add_column("Status", justify="center", min_width=8)

    for c in d.changes:
        label, fmt = _METRIC_FMT.get(c.metric, (c.metric, lambda v: f"{v:.4f}"))
        old_s = fmt(c.old_value)
        new_s = fmt(c.new_value)

        if c.status == ChangeStatus.IMPROVED:
            arrow = "↑" if c.delta > 0 else "↓"
            change_s = f"[green]{arrow} {abs(c.delta_pct):.1f}%[/green]"
            status_s = "[bold green]✅[/bold green]"
        elif c.status == ChangeStatus.REGRESSED:
            arrow = "↑" if c.delta > 0 else "↓"
            change_s = f"[red]{arrow} {abs(c.delta_pct):.1f}%[/red]"
            status_s = "[bold red]⚠️[/bold red]"
        else:
            change_s = "[dim]—[/dim]"
            status_s = "[dim]➖[/dim]"

        table.add_row(label, old_s, new_s, change_s, status_s)

    # Tool changes
    if d.tool_changes:
        table.add_section()
        table.add_row("[bold]Tool Usage[/bold]", "", "", "", "")
        for tc in d.tool_changes:
            arrow = "↑" if tc.delta > 0 else "↓" if tc.delta < 0 else "—"
            delta_s = f"{arrow} {abs(tc.delta_pct):.0f}%" if tc.delta else "—"
            table.add_row(
                f"  {tc.tool}",
                str(tc.old_count),
                str(tc.new_count),
                delta_s,
                "",
            )

    header = Text.assemble(
        ("AgentGit Diff: ", "bold white"),
        (d.from_version, "bold yellow"),
        (" → ", "dim"),
        (d.to_version, "bold green"),
    )

    console.print()
    console.print(Panel(table, title=header, border_style="blue", padding=(1, 2)))

    # Verdict
    verdict_style = "green" if d.regressions == 0 else ("red" if d.improvements == 0 else "yellow")
    console.print(
        Panel(
            f"[bold]{d.verdict}[/bold]",
            border_style=verdict_style,
            padding=(0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Markdown Diff (GitHub PR comments)
# ---------------------------------------------------------------------------

def diff_to_markdown(d: BehavioralDiff) -> str:
    """Format a behavioral diff as GitHub Flavored Markdown."""
    lines: List[str] = [
        f"### 🧬 AgentGit Behavioral Diff: `{d.from_version}` → `{d.to_version}`",
        "",
        "| Metric | `" + d.from_version + "` | `" + d.to_version + "` | Change | Status |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for c in d.changes:
        label, fmt = _METRIC_FMT.get(c.metric, (c.metric, lambda v: f"{v:.4f}"))
        old_s = fmt(c.old_value)
        new_s = fmt(c.new_value)

        if c.status == ChangeStatus.IMPROVED:
            arrow = "↑" if c.delta > 0 else "↓"
            change_s = f"**{arrow} {abs(c.delta_pct):.1f}%**"
            status_s = "✅ Improved"
        elif c.status == ChangeStatus.REGRESSED:
            arrow = "↑" if c.delta > 0 else "↓"
            change_s = f"**{arrow} {abs(c.delta_pct):.1f}%**"
            status_s = "⚠️ Regressed"
        else:
            change_s = "—"
            status_s = "➖ Neutral"

        lines.append(f"| **{label}** | {old_s} | {new_s} | {change_s} | {status_s} |")

    if d.tool_changes:
        lines.extend([
            "",
            "#### 🛠️ Tool Usage Changes",
            "",
            "| Tool | `" + d.from_version + "` | `" + d.to_version + "` | Delta |",
            "| :--- | :---: | :---: | :---: |",
        ])
        for tc in d.tool_changes:
            arrow = "↑" if tc.delta > 0 else "↓" if tc.delta < 0 else "—"
            delta_s = f"{arrow} {abs(tc.delta_pct):.0f}%" if tc.delta else "—"
            lines.append(f"| `{tc.tool}` | {tc.old_count} | {tc.new_count} | {delta_s} |")

    lines.extend([
        "",
        f"> **Verdict:** {d.verdict}",
        "",
        "<sub>Report generated by <a href='https://github.com/adesh-2006/AgentGit'>AgentGit</a> • Git for AI Agent Behavior</sub>",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML Diff Report (Standalone Dark Mode Dashboard)
# ---------------------------------------------------------------------------

def diff_to_html(d: BehavioralDiff) -> str:
    """Generate a responsive, standalone dark-mode HTML report."""
    rows = []
    for c in d.changes:
        label, fmt = _METRIC_FMT.get(c.metric, (c.metric, lambda v: f"{v:.4f}"))
        old_s = fmt(c.old_value)
        new_s = fmt(c.new_value)

        if c.status == ChangeStatus.IMPROVED:
            badge_class = "badge-improved"
            status_text = "✅ Improved"
            arrow = "↑" if c.delta > 0 else "↓"
            change_text = f"{arrow} {abs(c.delta_pct):.1f}%"
        elif c.status == ChangeStatus.REGRESSED:
            badge_class = "badge-regressed"
            status_text = "⚠️ Regressed"
            arrow = "↑" if c.delta > 0 else "↓"
            change_text = f"{arrow} {abs(c.delta_pct):.1f}%"
        else:
            badge_class = "badge-neutral"
            status_text = "➖ Neutral"
            change_text = "—"

        rows.append(f"""
        <tr>
          <td><strong>{label}</strong></td>
          <td class="num">{old_s}</td>
          <td class="num">{new_s}</td>
          <td class="num"><span class="{badge_class}">{change_text}</span></td>
          <td><span class="{badge_class}">{status_text}</span></td>
        </tr>""")

    tool_rows = []
    for tc in d.tool_changes:
        arrow = "↑" if tc.delta > 0 else "↓" if tc.delta < 0 else "—"
        delta_s = f"{arrow} {abs(tc.delta_pct):.0f}%" if tc.delta else "—"
        tool_rows.append(f"""
        <tr>
          <td><code>{tc.tool}</code></td>
          <td class="num">{tc.old_count}</td>
          <td class="num">{tc.new_count}</td>
          <td class="num">{delta_s}</td>
        </tr>""")

    tool_section = ""
    if tool_rows:
        tool_section = f"""
        <div class="card" style="margin-top: 24px;">
          <h3>🛠️ Tool Usage Breakdown</h3>
          <table>
            <thead>
              <tr>
                <th>Tool</th>
                <th class="num">{d.from_version}</th>
                <th class="num">{d.to_version}</th>
                <th class="num">Delta</th>
              </tr>
            </thead>
            <tbody>
              {"".join(tool_rows)}
            </tbody>
          </table>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AgentGit Diff: {d.from_version} → {d.to_version}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --green: #3fb950;
      --green-bg: rgba(63, 185, 80, 0.15);
      --red: #f85149;
      --red-bg: rgba(248, 81, 73, 0.15);
      --yellow: #d29922;
      --accent: #58a6ff;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 32px 16px;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
    }}
    .header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
      margin-bottom: 28px;
    }}
    .title h1 {{
      margin: 0;
      font-size: 24px;
      color: #fff;
    }}
    .title p {{
      margin: 6px 0 0 0;
      color: var(--text-muted);
      font-size: 14px;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }}
    .kpi-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }}
    .kpi-num {{
      font-size: 28px;
      font-weight: 700;
      margin-top: 4px;
    }}
    .improved {{ color: var(--green); }}
    .regressed {{ color: var(--red); }}
    .neutral {{ color: var(--text-muted); }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    th {{
      color: var(--text-muted);
      font-weight: 600;
    }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .badge-improved {{
      background: var(--green-bg);
      color: var(--green);
      padding: 4px 8px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 12px;
    }}
    .badge-regressed {{
      background: var(--red-bg);
      color: var(--red);
      padding: 4px 8px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 12px;
    }}
    .badge-neutral {{
      color: var(--text-muted);
      font-size: 12px;
    }}
    .verdict-box {{
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--card);
      margin-top: 24px;
      font-size: 15px;
      line-height: 1.5;
    }}
    footer {{
      margin-top: 40px;
      text-align: center;
      color: var(--text-muted);
      font-size: 13px;
    }}
    footer a {{ color: var(--accent); text-decoration: none; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">
        <h1>🧬 AgentGit Behavioral Diff</h1>
        <p>Comparing snapshot <strong>{d.from_version}</strong> → <strong>{d.to_version}</strong></p>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi-card">
        <div style="color: var(--text-muted); font-size: 13px;">Improved</div>
        <div class="kpi-num improved">{d.improvements}</div>
      </div>
      <div class="kpi-card">
        <div style="color: var(--text-muted); font-size: 13px;">Regressed</div>
        <div class="kpi-num regressed">{d.regressions}</div>
      </div>
      <div class="kpi-card">
        <div style="color: var(--text-muted); font-size: 13px;">Neutral</div>
        <div class="kpi-num neutral">{d.neutral}</div>
      </div>
    </div>

    <div class="card">
      <h3 style="margin-top: 0;">Performance & Behavioral Metrics</h3>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th class="num">{d.from_version}</th>
            <th class="num">{d.to_version}</th>
            <th class="num">Change</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows)}
        </tbody>
      </table>
    </div>

    {tool_section}

    <div class="verdict-box">
      <strong>Verdict:</strong> {d.verdict}
    </div>

    <footer>
      Generated with <a href="https://github.com/adesh-2006/AgentGit" target="_blank">AgentGit</a> • Git for AI Agent Behavior
    </footer>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Snapshot list
# ---------------------------------------------------------------------------

def print_snapshot_list(snapshots: List[Dict[str, Any]]) -> None:
    """Print a table of snapshot summaries."""
    table = Table(
        title="AgentGit Snapshots",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("#", style="dim", justify="right")
    table.add_column("Version", style="bold green")
    table.add_column("Timestamp", style="white")
    table.add_column("Tasks", justify="right")
    table.add_column("Completion", justify="right")
    table.add_column("Error Rate", justify="right")
    table.add_column("Avg Cost", justify="right")

    for i, s in enumerate(snapshots, 1):
        table.add_row(
            str(i),
            s["version"],
            s["timestamp"][:19],
            str(s["num_tasks"]),
            s["completion"],
            s["error_rate"],
            s["avg_cost"],
        )

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# CI report
# ---------------------------------------------------------------------------

def print_ci_report(
    results: List[Dict[str, Any]],
    passed: bool,
    version: str,
) -> None:
    """Print CI check results."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Rule", style="white", min_width=30)
    table.add_column("Actual", justify="right")
    table.add_column("Result", justify="center")

    for r in results:
        if r["passed"]:
            result_s = "[bold green]PASS ✅[/bold green]"
        else:
            result_s = "[bold red]FAIL ❌[/bold red]"
        table.add_row(r["rule"], str(round(r["actual"], 4)), result_s)

    status = "[bold green]ALL CHECKS PASSED ✅[/bold green]" if passed else "[bold red]CHECKS FAILED ❌[/bold red]"

    header = Text.assemble(
        ("AgentGit CI Check: ", "bold white"),
        (version, "bold yellow"),
    )

    console.print()
    console.print(Panel(table, title=header, border_style="blue", padding=(1, 2)))
    console.print(Panel(status, border_style="green" if passed else "red", padding=(0, 2)))
    console.print()


# ---------------------------------------------------------------------------
# Blame report
# ---------------------------------------------------------------------------

def print_blame_report(b: Any) -> None:
    """Print behavioral attribution report."""
    table = Table(
        title=f"Behavioral Blame: {b.metric}",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Version", style="bold")
    table.add_column("Timestamp", style="dim")
    table.add_column("Value", justify="right")
    table.add_column("Delta", justify="right")
    table.add_column("Status", justify="center")

    for e in b.entries:
        status_s = "⚠️ Shift Point" if e.is_shift_point else ("✅ Improved" if e.status == ChangeStatus.IMPROVED else "—")
        row_style = "bold red" if e.is_shift_point else "white"
        table.add_row(
            f"[{row_style}]{e.version}[/{row_style}]",
            e.timestamp,
            str(e.value),
            f"{e.delta:+.4f}" if e.delta != 0 else "—",
            status_s,
        )

    console.print()
    console.print(table)
    console.print(Panel(f"[bold]{b.summary}[/bold]", border_style="yellow", padding=(0, 2)))
    console.print()


# ---------------------------------------------------------------------------
# Replay report
# ---------------------------------------------------------------------------

def print_replay_report(t: Any) -> None:
    """Print trajectory execution playback."""
    header = Text.assemble(
        ("AgentGit Task Replay: #", "bold white"),
        (str(t.task_index + 1), "bold yellow"),
        (" (", "dim"),
        (t.version, "bold green"),
        (")", "dim"),
    )

    table = Table(show_header=False, border_style="blue")
    table.add_column("Property", style="bold cyan", width=18)
    table.add_column("Value", style="white")

    table.add_row("Status", "[bold green]PASSED ✅[/bold green]" if t.success else "[bold red]FAILED ❌[/bold red]")
    table.add_row("Input", str(t.task_input))
    table.add_row("Output", str(t.output))
    table.add_row("Steps / Tools", f"{t.steps} steps — Tools: {', '.join(t.tools_called) if t.tools_called else 'None'}")
    table.add_row("Latency", f"{t.latency_ms:.0f} ms")
    table.add_row("Tokens", f"{t.tokens}")
    table.add_row("Cost", f"${t.cost_usd:.4f}")
    if t.error:
        table.add_row("Error", f"[bold red]{t.error}[/bold red]")

    console.print()
    console.print(Panel(table, title=header, border_style="blue", padding=(1, 2)))
    console.print()


# ---------------------------------------------------------------------------
# Matrix report
# ---------------------------------------------------------------------------

def print_matrix_report(m: Any) -> None:
    """Print multi-variant comparison matrix."""
    table = Table(
        title="Multi-Variant Benchmark Matrix",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Metric", style="white", min_width=22)
    for v in m.versions:
        table.add_column(v, justify="right", min_width=12)
    table.add_column("Winner", justify="center", style="bold green", min_width=12)

    for row in m.rows:
        row_vals = [str(row.values.get(v, "—")) for v in m.versions]
        table.add_row(row.display_name, *row_vals, row.best_version)

    summary_text = (
        f"[bold]Category Winners:[/bold]\n"
        f"  • Highest Completion: [bold green]{m.winner_completion}[/bold green]\n"
        f"  • Lowest Cost:       [bold green]{m.winner_cost}[/bold green]\n"
        f"  • Fastest Latency:   [bold green]{m.winner_speed}[/bold green]"
    )

    console.print()
    console.print(table)
    console.print(Panel(summary_text, border_style="green", padding=(0, 2)))
    console.print()


# ---------------------------------------------------------------------------
# Bisect report
# ---------------------------------------------------------------------------

def print_bisect_report(b: Any) -> None:
    """Print regression bisect results."""
    table = Table(
        title=f"Regression Bisect: {b.metric}",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Snapshot", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Status", justify="center")

    for s in b.steps:
        marker = "[bold red]🎯 First Regression[/bold red]" if s.is_regression_boundary else "—"
        table.add_row(s.version, str(s.value), marker)

    console.print()
    console.print(table)
    console.print(Panel(f"[bold]{b.explanation}[/bold]", border_style="red" if b.culprit_version else "green", padding=(0, 2)))
    console.print()
