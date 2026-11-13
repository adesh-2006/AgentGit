"""AgentGit CLI — ``agentgit`` command-line interface.

Commands::

    agentgit init          Initialise AgentGit in the current directory
    agentgit snapshot      Create a behavioral snapshot
    agentgit diff          Compare two snapshots
    agentgit list          List all snapshots
    agentgit show          Show a snapshot's details
    agentgit rollback      Set active version
    agentgit ci-check      Run CI rules against a snapshot
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from agentgit import __version__
from agentgit.ci import ci_check as _ci_check
from agentgit.ci import parse_rules
from agentgit.diff import create_diff
from agentgit.report import (
    console,
    diff_to_html,
    diff_to_markdown,
    print_bisect_report,
    print_blame_report,
    print_ci_report,
    print_cost_report,
    print_diff_report,
    print_drift_report,
    print_lint_report,
    print_matrix_report,
    print_replay_report,
    print_snapshot_list,
    print_snapshot_report,
)
from agentgit.storage import AgentGitStore


def _store(ctx: click.Context) -> AgentGitStore:
    return AgentGitStore(ctx.obj.get("project", "."))


@click.group()
@click.option("--project", "-p", default=".", help="Project root directory.")
@click.version_option(__version__, prog_name="agentgit")
@click.pass_context
def cli(ctx: click.Context, project: str) -> None:
    """AgentGit — Git for AI Agent Behavior.

    Version, diff, and rollback how your agent behaves.
    """
    ctx.ensure_object(dict)
    ctx.obj["project"] = project


# ------------------------------------------------------------------
# init
# ------------------------------------------------------------------

@cli.command()
@click.option("--name", "-n", default="my-agent", help="Agent name.")
@click.pass_context
def init(ctx: click.Context, name: str) -> None:
    """Initialise AgentGit in the current project."""
    store = AgentGitStore.init(ctx.obj["project"], name=name)
    console.print(f"\n[bold green]✅ AgentGit initialised[/bold green] for agent: [cyan]{name}[/cyan]")
    console.print(f"   Created [dim]{store.agdir}[/dim]\n")


# ------------------------------------------------------------------
# snapshot
# ------------------------------------------------------------------

@cli.command()
@click.argument("version")
@click.option("--tasks", "-t", type=click.Path(exists=True), help="JSON file with task inputs.")
@click.pass_context
def snapshot(ctx: click.Context, version: str, tasks: str | None) -> None:
    """Create a behavioral snapshot from recorded data or task file."""
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    if store.exists(version):
        console.print(f"[yellow]Warning:[/yellow] Snapshot '{version}' already exists. Overwriting.")

    if tasks:
        task_data = json.loads(Path(tasks).read_text(encoding="utf-8"))
    else:
        console.print(
            "[dim]No --tasks file provided. Creating an empty snapshot placeholder.[/dim]"
        )
        task_data = []

    # Build a minimal snapshot from task data when running CLI standalone
    from agentgit.snapshot import BehavioralSnapshot
    snap = BehavioralSnapshot(
        version=version,
        agent_name=store.get_config().get("agent_name", "agent"),
        num_tasks=len(task_data),
    )
    store.save(snap)
    console.print(f"\n[bold green]✅ Snapshot '{version}' saved[/bold green] ({len(task_data)} tasks)\n")
    print_snapshot_report(snap)


# ------------------------------------------------------------------
# diff
# ------------------------------------------------------------------

@cli.command("diff")
@click.argument("version_a")
@click.argument("version_b", required=False)
@click.option("--format", "fmt", type=click.Choice(["table", "json", "markdown", "html"]), default="table", help="Output format.")
@click.option("--output", "-o", type=click.Path(writable=True), default=None, help="Save diff output to file.")
@click.pass_context
def diff_cmd(ctx: click.Context, version_a: str, version_b: str | None, fmt: str, output: str | None) -> None:
    """Show behavioral diff between two snapshots."""
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    if version_b is None:
        current = store.get_current_version()
        if current is None or current == version_a:
            console.print("[red]Error:[/red] Need two versions to diff. Provide VERSION_B or have a current version.")
            raise SystemExit(1)
        version_b = current

    try:
        snap_a = store.load(version_a)
        snap_b = store.load(version_b)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    result = create_diff(snap_a, snap_b)

    if fmt == "json":
        rendered = result.model_dump_json(indent=2)
    elif fmt == "markdown":
        rendered = diff_to_markdown(result)
    elif fmt == "html":
        rendered = diff_to_html(result)
    else:
        rendered = None

    if output:
        out_path = Path(output)
        out_path.write_text(rendered if rendered is not None else diff_to_markdown(result), encoding="utf-8")
        console.print(f"[bold green]✅ Diff exported to {out_path}[/bold green]")
    elif rendered is not None:
        click.echo(rendered)
    else:
        print_diff_report(result)


# ------------------------------------------------------------------
# list
# ------------------------------------------------------------------

@cli.command("list")
@click.pass_context
def list_cmd(ctx: click.Context) -> None:
    """List all saved behavioral snapshots."""
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    summaries = store.list_summary()
    if not summaries:
        console.print("[dim]No snapshots yet. Create one with `agentgit snapshot <version>`[/dim]")
        return

    print_snapshot_list(summaries)


# ------------------------------------------------------------------
# show
# ------------------------------------------------------------------

@cli.command()
@click.argument("version")
@click.pass_context
def show(ctx: click.Context, version: str) -> None:
    """Show detailed report for a specific snapshot."""
    store = _store(ctx)
    try:
        snap = store.load(version)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    print_snapshot_report(snap)


# ------------------------------------------------------------------
# rollback
# ------------------------------------------------------------------

@cli.command()
@click.argument("version")
@click.pass_context
def rollback(ctx: click.Context, version: str) -> None:
    """Set the active version tag to a previous snapshot."""
    store = _store(ctx)
    if not store.exists(version):
        console.print(f"[red]Error:[/red] Snapshot '{version}' not found.")
        raise SystemExit(1)

    store.set_config("current_version", version)
    console.print(f"\n[bold green]✅ Rolled back to '{version}'[/bold green]\n")


# ------------------------------------------------------------------
# ci-check
# ------------------------------------------------------------------

@cli.command("ci-check")
@click.argument("version")
@click.option("--rules", "-r", required=True, help='Rules, e.g. "task_completion >= 0.85 AND error_rate < 0.10"')
@click.pass_context
def ci_check_cmd(ctx: click.Context, version: str, rules: str) -> None:
    """Run CI/CD behavioral checks against a snapshot."""
    store = _store(ctx)
    try:
        snap = store.load(version)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    try:
        parsed = parse_rules(rules)
    except ValueError as e:
        console.print(f"[red]Error parsing rules:[/red] {e}")
        raise SystemExit(1)

    passed, details = _ci_check(snap, parsed)
    print_ci_report(details, passed, version)

    if not passed:
        raise SystemExit(1)


# ------------------------------------------------------------------
# blame
# ------------------------------------------------------------------

@cli.command("blame")
@click.argument("metric")
@click.pass_context
def blame_cmd(ctx: click.Context, metric: str) -> None:
    """Identify which version introduced a regression in METRIC."""
    from agentgit.blame import blame_metric
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    report = blame_metric(store, metric)
    print_blame_report(report)


# ------------------------------------------------------------------
# replay
# ------------------------------------------------------------------

@cli.command("replay")
@click.argument("version")
@click.argument("task_index", type=int)
@click.pass_context
def replay_cmd(ctx: click.Context, version: str, task_index: int) -> None:
    """Inspect and replay the exact trajectory of task TASK_INDEX in VERSION."""
    from agentgit.replay import get_task_trace
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    try:
        # User provides 1-based index (e.g. 1 for first task)
        trace = get_task_trace(store, version, task_index - 1)
    except (FileNotFoundError, IndexError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    print_replay_report(trace)


# ------------------------------------------------------------------
# matrix
# ------------------------------------------------------------------

@cli.command("matrix")
@click.argument("versions", nargs=-1, required=True)
@click.pass_context
def matrix_cmd(ctx: click.Context, versions: tuple[str, ...]) -> None:
    """Compare 2 or more snapshots in a side-by-side benchmark matrix."""
    from agentgit.matrix import build_comparison_matrix
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    try:
        matrix = build_comparison_matrix(store, list(versions))
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    print_matrix_report(matrix)


# ------------------------------------------------------------------
# bisect
# ------------------------------------------------------------------

@cli.command("bisect")
@click.argument("good_version")
@click.argument("bad_version")
@click.option("--metric", "-m", default="error_rate", help="Metric to bisect (default: error_rate).")
@click.pass_context
def bisect_cmd(ctx: click.Context, good_version: str, bad_version: str, metric: str) -> None:
    """Pinpoint the exact snapshot where METRIC regressed between versions."""
    from agentgit.bisect import bisect_metric
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    try:
        res = bisect_metric(store, good_version, bad_version, metric)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    print_bisect_report(res)


# ------------------------------------------------------------------
# ui
# ------------------------------------------------------------------

@cli.command("ui")
@click.option("--port", "-p", default=8585, help="Port to run the dashboard on (default: 8585).")
@click.option("--no-browser", is_flag=True, default=False, help="Do not open the browser automatically.")
@click.pass_context
def ui_cmd(ctx: click.Context, port: int, no_browser: bool) -> None:
    """Launch the local zero-dependency AgentGit web dashboard."""
    from agentgit.ui import start_ui
    project = ctx.obj.get("project", ".")
    start_ui(project_path=project, port=port, open_browser=not no_browser)


# ------------------------------------------------------------------
# lint
# ------------------------------------------------------------------

@cli.command("lint")
@click.argument("prompt_file", type=click.Path(exists=True))
@click.pass_context
def lint_cmd(ctx: click.Context, prompt_file: str) -> None:
    """Run static contract & injection lint rules on PROMPT_FILE."""
    from agentgit.lint import lint_prompt
    content = Path(prompt_file).read_text(encoding="utf-8")
    report = lint_prompt(content, target_name=Path(prompt_file).name)
    print_lint_report(report)


# ------------------------------------------------------------------
# drift
# ------------------------------------------------------------------

@cli.command("drift")
@click.argument("version_a")
@click.argument("version_b")
@click.pass_context
def drift_cmd(ctx: click.Context, version_a: str, version_b: str) -> None:
    """Detect textual & semantic drift between two snapshot outputs."""
    from agentgit.drift import analyze_drift
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    try:
        report = analyze_drift(store, version_a, version_b)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    print_drift_report(report)


# ------------------------------------------------------------------
# cost-predict
# ------------------------------------------------------------------

@cli.command("cost-predict")
@click.argument("version")
@click.option("--dau", default=1000, help="Daily Active Users (default: 1000).")
@click.option("--requests", "-r", default=5, help="Requests per user per day (default: 5).")
@click.pass_context
def cost_predict_cmd(ctx: click.Context, version: str, dau: int, requests: int) -> None:
    """Simulate production token bills and model trade-offs for VERSION."""
    from agentgit.cost import predict_production_cost
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    try:
        forecast = predict_production_cost(store, version, dau=dau, requests_per_user=requests)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    print_cost_report(forecast)


# ------------------------------------------------------------------
# export
# ------------------------------------------------------------------

@cli.command("export")
@click.argument("version")
@click.option("--format", "-f", type=click.Choice(["csv", "jsonl", "json", "otel"]), default="csv", help="Output format.")
@click.option("--output", "-o", default=None, help="Output destination file path.")
@click.pass_context
def export_cmd(ctx: click.Context, version: str, format: str, output: str | None) -> None:
    """Export snapshot tasks and metrics to CSV, JSONL, JSON, or OpenTelemetry (OTel)."""
    store = _store(ctx)
    if not store.is_initialised:
        console.print("[red]Error:[/red] Not an AgentGit project. Run `agentgit init` first.")
        raise SystemExit(1)

    try:
        if format == "otel":
            from agentgit.otel import export_otel_json
            out_dest = output or f"{version}_otel.json"
            out_path = export_otel_json(store, version, out_dest)
        else:
            from agentgit.export import export_snapshot
            out_path = export_snapshot(store, version, format=format, output_path=output)  # type: ignore[arg-type]
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    console.print(f"[bold green]✅ Snapshot '{version}' exported to {out_path}[/bold green]")


# ------------------------------------------------------------------
# remote, push, pull
# ------------------------------------------------------------------

@cli.group("remote")
def remote_group() -> None:
    """Manage remote team snapshot registries."""
    pass


@remote_group.command("add")
@click.argument("name")
@click.argument("url")
@click.pass_context
def remote_add_cmd(ctx: click.Context, name: str, url: str) -> None:
    """Add a new remote team registry (directory, s3://, or http://)."""
    from agentgit.remote import add_remote
    store = _store(ctx)
    add_remote(store, name, url)
    console.print(f"[bold green]✅ Remote '{name}' added -> {url}[/bold green]")


@remote_group.command("list")
@click.pass_context
def remote_list_cmd(ctx: click.Context) -> None:
    """List all configured remote registries."""
    from agentgit.remote import get_remotes
    store = _store(ctx)
    remotes = get_remotes(store)
    if not remotes:
        console.print("[dim]No remotes configured. Use `agentgit remote add <name> <url>`[/dim]")
        return
    for name, url in remotes.items():
        console.print(f"[bold cyan]{name}[/bold cyan]\t{url}")


@cli.command("push")
@click.argument("remote")
@click.argument("version")
@click.pass_context
def push_cmd(ctx: click.Context, remote: str, version: str) -> None:
    """Push a snapshot to a remote team registry."""
    from agentgit.remote import push_snapshot
    store = _store(ctx)
    try:
        msg = push_snapshot(store, remote, version)
        console.print(f"[bold green]✅ {msg}[/bold green]")
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@cli.command("pull")
@click.argument("remote")
@click.argument("version")
@click.pass_context
def pull_cmd(ctx: click.Context, remote: str, version: str) -> None:
    """Pull a snapshot from a remote team registry."""
    from agentgit.remote import pull_snapshot
    store = _store(ctx)
    try:
        snap = pull_snapshot(store, remote, version)
        console.print(f"[bold green]✅ Pulled '{snap.version}' from remote '{remote}'[/bold green]")
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    cli()
