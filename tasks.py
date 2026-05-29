from __future__ import annotations

import shutil
import subprocess
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

    # Use demo_exports when config.yaml is absent; fall back to exports/ for research mode.
    exports_path = (
        PROJECT_ROOT / "exports"
        if (PROJECT_ROOT / "config" / "config.yaml").exists()
        else PROJECT_ROOT / "demo_exports"
    )
    run_all(exports_path)
    console.print("[green]Queries complete.[/green]")


@app.command()
def ui(
    config: str = "config/config_demo.yaml",
    host: str = "127.0.0.1",
    port: int = 5002,
    debug: bool = False,
) -> None:
    """Launch the interactive coding UI."""
    import errno
    import socket

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))
        probe.close()
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            console.print(f"[red]Port {port} is already in use.[/red]")
            raise typer.Exit(code=1)
        raise

    console.print(f"[cyan]Starting UI on http://{host}:{port} ...[/cyan]")
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "src" / "inductive_ta" / "ui" / "app_framework.py"),
        "--config", config,
        "--port", str(port),
    ]
    if debug:
        cmd.append("--debug")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    raise typer.Exit(code=result.returncode)


@app.command()
def clean() -> None:
    """Remove generated exports and figures."""
    targets = [PROJECT_ROOT / "demo_exports", PROJECT_ROOT / "exports"]
    removed = 0

    for target in targets:
        if not target.exists():
            continue

        for child in target.iterdir():
            if child.name == ".gitkeep":
                continue
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                removed += 1
            except OSError as exc:
                console.print(f"[red]Failed to remove {child}: {exc}[/red]")

    if removed:
        console.print(f"[green]Removed {removed} item(s) from exports directories.[/green]")
    else:
        console.print("[cyan]Nothing to clean.[/cyan]")


@app.command()
def purge_turns() -> None:
    """Remove automatically-generated turn exports to enforce inline-only workflow."""
    candidates = [
        PROJECT_ROOT / "demo_exports" / "corpus_enriched.jsonl",
        PROJECT_ROOT / "exports" / "corpus_enriched.jsonl",
    ]
    removed = False
    for path in candidates:
        if path.exists():
            path.unlink()
            console.print(f"[green]Removed {path.relative_to(PROJECT_ROOT)}[/green]")
            removed = True
    if not removed:
        console.print("[cyan]No corpus_enriched.jsonl found; nothing to purge.[/cyan]")


if __name__ == "__main__":
    app()
