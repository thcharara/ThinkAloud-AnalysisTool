from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Utility commands for the Inductive Think-Aloud project.")
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))


@app.command()
def parse() -> None:
    """Parse transcripts into processed exports."""
    console.print("[cyan]Running transcript parser...[/cyan]")
    from inductive_ta.parse_transcripts import run as parse_run

    parse_run()
    console.print("[green]Transcript parsing completed.[/green]")


@app.command()
def init_annotations(out: str = "02_annotations") -> None:
    """Create editable Markdown copies of transcripts for annotation."""
    console.print("[cyan]Scaffolding annotation files...[/cyan]")
    from inductive_ta.scaffold import init_annotations as do_init

    n = do_init(Path(out))
    console.print(f"[green]Created {n} files in {out}[/green]")


@app.command()
def export_annotations() -> None:
    """Parse annotated Markdown and export CSVs for analysis."""
    console.print("[cyan]Exporting annotations to CSV...[/cyan]")
    from inductive_ta.parse_annotations import export as export_cmd

    export_cmd()


@app.command()
def queries() -> None:
    """Run quick aggregate queries over exports."""
    console.print("[cyan]Running aggregate queries...[/cyan]")
    from inductive_ta.queries import run_all
    run_all(Path("05_exports"))
    console.print("[green]Queries complete.[/green]")


@app.command()
def ui(
    host: str = "127.0.0.1",
    port: int = 5001,
    debug: bool = False,
    check_only: bool = False,
) -> None:
    """Launch the interactive coding UI."""
    from inductive_ta.ui import create_app

    flask_app = create_app()

    if check_only:
        console.print("[cyan]Running self-check for UI routes...[/cyan]")
        client = flask_app.test_client()
        index_resp = client.get("/")
        participant_resp = client.get("/participant/P01")
        if index_resp.status_code != 200:
            console.print("[red]Index route check failed[/red]")
            raise typer.Exit(code=1)
        if participant_resp.status_code != 200:
            console.print("[red]Participant route check failed[/red]")
            raise typer.Exit(code=1)
        console.print("[green]UI routes loaded successfully. You can now run without --check-only.[/green]")
        raise typer.Exit(code=0)

    console.print(f"[cyan]Starting UI on http://{host}:{port} ...[/cyan]")

    import socket
    import errno

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))
        probe.close()
    except OSError as exc:
        if exc.errno == errno.EPERM:
            console.print(
                "[red]Unable to bind to the port due to operating-system restrictions (permission denied).[/red]"
            )
            console.print(
                "[yellow]If you are running inside a restricted environment, rerun with --check-only to verify the UI, or run on your local machine/VS Code outside the sandbox.[/yellow]"
            )
            raise typer.Exit(code=1)
        if exc.errno == errno.EADDRINUSE:
            console.print(
                f"[red]Port {port} is already in use. Choose another port with --port.[/red]"
            )
            raise typer.Exit(code=1)
        raise

    flask_app.run(host=host, port=port, debug=debug, use_reloader=False)


@app.command()
def clean() -> None:
    """Remove generated exports and figures."""
    targets = [Path("05_exports"), Path("06_figures")]
    removed = 0

    for target in targets:
        if not target.exists():
            console.print(f"[yellow]Directory not found: {target}[/yellow]")
            continue

        for child in target.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                removed += 1
            except OSError as exc:
                console.print(f"[red]Failed to remove {child}: {exc}[/red]")

    if removed:
        console.print(f"[green]Removed {removed} items from exports/figures directories.[/green]")
    else:
        console.print("[cyan]Nothing to clean.[/cyan]")


@app.command()
def purge_turns() -> None:
    """Remove automatically-generated turn exports to enforce inline-only workflow."""
    path = Path("05_exports/corpus_enriched.jsonl")
    if path.exists():
        path.unlink()
        console.print("[green]Removed 05_exports/corpus_enriched.jsonl[/green]")
    else:
        console.print("[cyan]No corpus_enriched.jsonl found; nothing to purge.[/cyan]")


if __name__ == "__main__":
    app()
