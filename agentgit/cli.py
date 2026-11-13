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
    print_ci_report,
    print_diff_report,
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
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    cli()
