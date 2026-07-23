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

from vesper.registry import AgentRegistry
from vesper.sqlite_storage import SQLiteVesperDatabase
from vesper.exceptions import VesperError, NoChangeDetectedError, ResourceNameNotFoundError, ResourceVersionNotFoundError

app = typer.Typer(
    rich_markup_mode="rich",
    help="""
    [bold white]Vesper[/bold white] is an infrastructure tool to manage AI agents in production. 
    
    Manage your AI agent fleets, stateful memory scopes, declarative YAML routing, FinOps tracking,
    and runtime security guardrails.
    """,
    epilog="Run [bold white]vesper init[/bold white] to set up your environment."
)

console = Console()


def get_vesper_home() -> str:
    """Returns the Vesper root directory, respecting the VESPER_HOME env var."""
    return os.path.expanduser(os.environ.get("VESPER_HOME", "~/.vesper"))


def ensure_initialized():
    """Guardrail to prevent commands from running if Vesper isn't set up."""
    config_path = os.path.join(get_vesper_home(), "config.json")
    
    if not os.path.exists(config_path):
        print("[bold red]Error:[/bold red] Vesper is not initialized.")
        print("Run [bold white]vesper init[/bold white] to set up the database and folders.")
        raise typer.Exit(code=1)


def get_registry() -> AgentRegistry:
    """Reads the config file and instantiates the correct database adapter."""
    ensure_initialized()
    
    config_path = os.path.join(get_vesper_home(), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        
    backend = config.get("backend")
    
    if backend == "local":
        db_path = config.get("db_path", os.path.join(get_vesper_home(), "registry.db"))
        db = SQLiteVesperDatabase(db_path)
    elif backend == "cloud":
        # db_uri = config.get("db_uri")
        # db = PostgresVesperDatabase(db_uri)
        print("[bold red]Error:[/bold red] Cloud backend is not yet fully implemented.")
        raise typer.Exit(code=1)
    else:
        print(f"[bold red]Error:[/bold red] Unknown backend type '{backend}' in config.json")
        raise typer.Exit(code=1)
        
    return AgentRegistry(db)


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
            version = importlib.metadata.version("vesper")
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
        app_version = importlib.metadata.version("vesper")
    except importlib.metadata.PackageNotFoundError:
        app_version = "unknown-local"
        
    banner = f"""[bold white]
██╗   ██╗███████╗███████╗██████╗ ███████╗██████╗ 
██║   ██║██╔════╝██╔════╝██╔══██╗██╔════╝██╔══██╗
██║   ██║█████╗  ███████╗██████╔╝█████╗  ██████╔╝
╚██╗ ██╔╝██╔══╝  ╚════██║██╔═══╝ ██╔══╝  ██╔══██╗
 ╚████╔╝ ███████╗███████║██║     ███████╗██║  ██║
  ╚═══╝  ╚══════╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝[/bold white]
[dim]v{app_version} | Production Orchestration for AI Agent Fleets[/dim]
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
    file: str = typer.Option(..., "--file", "-f", help="Path to the agent or fleet YAML file")
):
    """Validates an agent or fleet YAML specification."""
    try:
        registry = get_registry()
        print(f"[dim]Validating {file}...[/dim]")
        
        manifest = registry.validate_manifest(file)
        
        print(f"[green]✓ Successfully validated {manifest.kind}: {manifest.name}[/green]")
        
    except (VesperError, FileNotFoundError) as e:
        print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(name="apply")
def apply(
    file: str = typer.Option(..., "--file", "-f", help="Path to the agent or fleet YAML file")
):
    """Validates and applies the agent or fleet to the registry."""
    try:
        registry = get_registry()
        print(f"[dim]Validating {file}...[/dim]")
        
        manifest, new_id, version = registry.apply_manifest(file)
        
        print(f"[green]✓ Successfully applied {manifest.kind}: {manifest.name} (v{version})[/green]")
        print(f"[dim]Deployed ID: {new_id}[/dim]")
        
    except NoChangeDetectedError as e:
        print(f"[dim]⚠ {e}[/dim]")
    except (VesperError, FileNotFoundError) as e:
        print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)

@app.command(name="list")
@app.command(name="ls", hidden=True)
def list_resources():
    """Lists all active resources (agents and fleets)."""
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
    """Displays history of a resource (agent or agent-fleet)"""
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
        print(f"[bold red]{e}[/bold red]")
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
        print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)
    
if __name__ == "__main__":
    app()