"""Beautiful terminal reports using Rich.

Produces the polished, colourful output that goes in the README GIF.
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
# Diff report
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
