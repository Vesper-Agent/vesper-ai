import os
import sys
import time
import json
import shutil
import importlib.metadata
from typing import Optional, Annotated

import typer
from rich import print, box
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from vesper.config import get_vesper_home, load_env
from vesper.registry import AgentRegistry, get_registry as build_registry
from vesper.runtime import Agent
from vesper.memory import MemoryStore
from vesper.audit import AuditStore
from vesper.sqlite_storage import SQLiteVesperDatabase
from vesper.models import BudgetConfig
from vesper.exceptions import VesperError, NoChangeDetectedError, ResourceNameNotFoundError, ResourceVersionNotFoundError, BudgetExceededError

app = typer.Typer(
    rich_markup_mode="rich",
    help="""
    [bold white]Vesper[/bold white] is an infrastructure tool to manage AI agents in production.

    Declare agents in YAML, version them in a local registry, and run them with
    stateful memory scopes, multi-provider routing, and FinOps cost tracking.
    """,
    epilog="Run [bold white]vesper init[/bold white] to set up your environment."
)

console = Console()


def get_registry() -> AgentRegistry:
    """Reads the config file and instantiates the correct database adapter."""
    try:
        return build_registry()
    except VesperError as e:
        print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


def type_print_rich(text: str, delay: float = 0.002):
    """Renders Rich text markup completely, then animates the output character-by-character."""
    with console.capture() as capture:
        console.print(text)
    
    rendered_text = capture.get()
    
    for char in rendered_text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)


def version_callback(value: bool):
    """Prints the version and exits immediately if the flag is passed."""
    if value:
        try:
            version = importlib.metadata.version("vesper-ai")
        except importlib.metadata.PackageNotFoundError:
            version = "0.1.0-dev"
            
        print(f"Vesper Core Version: [bold white]{version}[/bold white]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", 
        callback=version_callback, 
        is_eager=True, 
        help="Show the application version and exit."
    ),
):
    """Vesper CLI root execution."""
    load_env()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())


@app.command(name="init")
def init_system(
    force: bool = typer.Option(
        False, 
        "--force", "-f", 
        help="Force re-initialization. Deletes existing configurations without prompting."
    ),
    cloud: bool = typer.Option(
        False,
        "--cloud",
        help="Initialize Vesper with a cloud PostgreSQL backend."
    ),
    local: bool = typer.Option(
        True,
        "--local",
        help="Initialize Vesper with a local SQLite backend."
    )
):
    """Initializes Vesper and sets up the local database."""
    
    if cloud:
        print("\n[bold white]Cloud Postgress Database[/bold white]")
        print("[dim]The PostgreSQL remote state adapter is currently in development.[/dim]")
        print("[dim]Use the default local backend for now: 'vesper init'[/dim]\n")
        raise typer.Exit()
    
    base_dir = get_vesper_home()
    
    if os.path.exists(base_dir):
        if not force:
            print(f"[bold red]WARNING:[/bold red] Vesper is already initialized at [dim]{base_dir}[/dim]")
            print("Re-initializing will permanently delete your agent history and saved state.")
            
            confirm = typer.confirm("Are you sure you want to delete everything and start over?")
            if not confirm:
                print("\n[dim]Aborted. Existing setup preserved.[/dim]")
                raise typer.Abort()
        
        print("\n[dim]Removing existing configuration...[/dim]")
        shutil.rmtree(base_dir)
        time.sleep(0.5) 

    try:
        app_version = importlib.metadata.version("vesper-ai")
    except importlib.metadata.PackageNotFoundError:
        app_version = "unknown-local"
        
    banner = f"""[bold white]
██╗   ██╗███████╗███████╗██████╗ ███████╗██████╗ 
██║   ██║██╔════╝██╔════╝██╔══██╗██╔════╝██╔══██╗
██║   ██║█████╗  ███████╗██████╔╝█████╗  ██████╔╝
╚██╗ ██╔╝██╔══╝  ╚════██║██╔═══╝ ██╔══╝  ██╔══██╗
 ╚████╔╝ ███████╗███████║██║     ███████╗██║  ██║
  ╚═══╝  ╚══════╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝[/bold white]
[dim]v{app_version} | Production Runtime for AI Agents[/dim]
"""
    type_print_rich(banner)
    
    subdirs = ["state", "audit"]
    
    print("\n[bold white]Setting up Vesper...[/bold white]")
    time.sleep(0.2)
    
    for folder in subdirs:
        target_path = os.path.join(base_dir, folder)
        os.makedirs(target_path, exist_ok=True)
        print(f"  [dim]→ Created folder: {target_path}[/dim]")
        
    config_path = os.path.join(base_dir, "config.json")
    db_path = os.path.join(base_dir, "registry.db")
    
    config_data = {
        "backend": "local",
        "db_path": db_path
    }
    
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=4)
    print(f"  [dim]→ Created config: {config_path}[/dim]")
    
    print(f"  [dim]→ Initialized database: {db_path}[/dim]")
    SQLiteVesperDatabase(db_path) 
    
    print("\n[green]✓ Vesper initialized successfully![/green]")
    print("[dim]Ready to go. Run 'vesper apply -f <spec.yaml>' to deploy your first agent.[/dim]\n")


@app.command(name="validate")
def validate(
    file: str = typer.Option(..., "--file", "-f", help="Path to the agent YAML manifest")
):
    """Validates an agent YAML manifest."""
    try:
        registry = get_registry()
        print(f"[dim]Validating {file}...[/dim]")
        
        manifest = registry.validate_manifest(file)
        
        print(f"[green]✓ Successfully validated {manifest.kind}: {manifest.name}[/green]")
        
    except (VesperError, FileNotFoundError) as e:
        print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(name="apply")
def apply(
    file: str = typer.Option(..., "--file", "-f", help="Path to the agent YAML manifest")
):
    """Validates and applies the agent to the registry."""
    try:
        registry = get_registry()
        print(f"[dim]Validating {file}...[/dim]")
        
        manifest, new_id, version = registry.apply_manifest(file)
        
        print(f"[green]✓ Successfully applied {manifest.kind}: {manifest.name} (v{version})[/green]")
        print(f"[dim]Deployed ID: {new_id}[/dim]")
        
    except NoChangeDetectedError as e:
        print(f"[dim]⚠ {e}[/dim]")
    except (VesperError, FileNotFoundError) as e:
        print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command(name="list")
@app.command(name="ls", hidden=True)
def list_resources():
    """Lists all active agents."""
    registry = get_registry()
    resources = registry.get_all_resources()
    
    if not resources:
        print("[dim]No resources deployed yet. Run 'vesper apply -f <spec.yaml>' to get started.[/dim]")
        return

    table = Table(
        box=box.MINIMAL, 
        header_style="bold white",
        pad_edge=False
    )
    
    table.add_column("Name", style="white")
    table.add_column("Kind", style="dim")
    table.add_column("Version")
    table.add_column("Status")
    
    for name, kind, version in resources:
        table.add_row(
            name, 
            kind, 
            f"v{version}", 
            "[bold green]● Active[/bold green]"
        )
        
    console.print(table)
 
@app.command(name="history")        
def show_history(name: str):
    """Displays the version history of an agent."""
    registry = get_registry()
    
    try:
        history = registry.get_history(name)
        
        print(f"History: [bold white]{name}[/bold white]")
        
        table = Table(
                box=box.MINIMAL, 
                header_style="bold white",
                pad_edge=False
            )
        
        table.add_column("Version", style="white")
        table.add_column("Manifest ID", style="dim")
        
        for version, id in history:
            table.add_row(f"v{version}", id)
        
        console.print(table)
            
    except ResourceNameNotFoundError as e:
        print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)
        
@app.command(name="show")
def show_config(
    name: str,
    version: Annotated[
        int | None,
        typer.Option("--version", "-v", help="Specify the version of the resource.")
    ] = None
):
    """Displays the actual configuration of the resource."""
    registry = get_registry()
    
    try:
        manifest = registry.get_resource_config(name, version)
        
        display_version = f" (v{version})" if version else " (Active)"
        print(f"\n[bold white]Configuration: {name}{display_version}[/bold white]")
        
        json_str = manifest.model_dump_json(indent=2)
        
        syntax = Syntax(
            json_str, 
            "json", 
            theme="ansi_dark", 
            background_color="default",
            word_wrap=True
        )
        console.print(syntax)
        print()
        
    except (ResourceNameNotFoundError, ResourceVersionNotFoundError) as e:
        print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)
    
@app.command(name="delete")
def delete_resource(
    name: Annotated[
        str | None, 
        typer.Argument(help="Name of the resource to delete.")
    ] = None,
    file: Annotated[
        str | None,
        typer.Option("--file", "-f", help="Specify the file path.")
    ] = None,
    confirmed: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt.")
    ] = False
):
    """Deletes a resource and its history from the database."""
    registry = get_registry()
    
    if not name and not file:
        print("[dim]Error: Either a resource name or a --file flag must be provided.[/dim]")
        raise typer.Exit(code=1)
    
    names_to_delete = []
    
    if name:
        names_to_delete.append(name)
    
    if file:
        try:
            manifest = registry.validate_manifest(file)
            if manifest.name not in names_to_delete:
                names_to_delete.append(manifest.name)
        except (VesperError, FileNotFoundError) as e:
            print(f"[bold red]{e}[/bold red]")
            raise typer.Exit(code=1)
            
    targets = ", ".join(names_to_delete)
    
    if not confirmed:
        confirm = typer.confirm(f"Are you sure you want to permanently delete '{targets}' and all history?")
        if not confirm:
            raise typer.Abort()
        
    for target in names_to_delete:
        try:
            registry.delete_resource(target)
            MemoryStore().delete(target)
            AuditStore().delete(target)
            print(f"[green]✓ Successfully deleted '{target}' and its history.[/green]")
        except ResourceNameNotFoundError as e:
            print(f"[bold red]Error: {e}[/bold red]")
            raise typer.Exit(code=1)


@app.command(name="run")
def run_agent(
    name: str,
    input: Annotated[Optional[str], typer.Option("--input", "-i", help="Input prompt for the agent.")] = None,
    input_file: Annotated[Optional[str], typer.Option("--input-file", help="Read the input prompt from a file.")] = None,
    session: Annotated[Optional[str], typer.Option("--session", "-s", help="Reuse a session id for stateful memory.")] = None,
    max_cost: Annotated[Optional[float], typer.Option("--max-cost", help="Override the manifest's maxCostPerRun for this run.")] = None
):
    """Runs a deployed agent against an input."""
    if input_file:
        with open(input_file) as f:
            prompt = f.read()
    elif input:
        prompt = input
    else:
        print("[bold red]Error:[/bold red] Provide --input or --input-file.")
        raise typer.Exit(code=1)

    try:
        agent = Agent.load(name)

        if max_cost is not None:
            if agent.manifest.budget is None:
                agent.manifest.budget = BudgetConfig(maxCostPerRun=max_cost)
            else:
                agent.manifest.budget.maxCostPerRun = max_cost

        result = agent.run(prompt, session=session)

    except BudgetExceededError as e:
        print(f"[bold red]✗ {e}[/bold red]")
        raise typer.Exit(code=1)
    except (VesperError, FileNotFoundError) as e:
        print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)

    console.print(result.content)

    if result.alerted:
        print("[yellow]⚠ alert: cost crossed the configured alert threshold[/yellow]")

    cost_str = f"${result.cost:.6f}" if result.cost is not None else "untracked"
    footer = f"cost {cost_str} · {result.prompt_tokens} in / {result.completion_tokens} out"
    if result.session_id:
        footer += f" · session {result.session_id}"
    print(f"[dim]{footer}[/dim]")


@app.command(name="runs")
def show_runs(name: str):
    """Displays the run history of an agent."""
    records = AuditStore().list(name)

    if not records:
        print(f"[dim]No runs recorded for '{name}' yet.[/dim]")
        return

    table = Table(box=box.MINIMAL, header_style="bold white", pad_edge=False)
    table.add_column("Run ID", style="dim")
    table.add_column("Status")
    table.add_column("Cost")
    table.add_column("Tokens")
    table.add_column("When", style="dim")

    for record in records:
        status = "[green]completed[/green]" if record.status == "completed" else "[red]failed[/red]"
        cost = f"${record.cost:.6f}" if record.cost is not None else "-"
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(record.created_at))
        table.add_row(record.run_id, status, cost, f"{record.prompt_tokens}/{record.completion_tokens}", when)

    console.print(table)


if __name__ == "__main__":
    app()