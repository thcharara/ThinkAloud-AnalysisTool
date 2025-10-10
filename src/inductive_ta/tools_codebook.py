from pathlib import Path
from rich.console import Console
import typer
from .codebook import load_codebook, validate_codebook, render_cheatsheet

app = typer.Typer()
con = Console()

@app.command()
def validate(path: str = "codebook/codebook.yaml") -> None:
    cb = load_codebook(path)
    errs = validate_codebook(cb)
    if errs:
        con.print("[red]Codebook validation failed:[/red]")
        for e in errs: con.print(f"- {e}")
        raise typer.Exit(code=1)
    con.print("[green]Codebook OK[/green]")

@app.command()
def cheatsheet(path: str = "codebook/codebook.yaml",
               out: str = "memos/Codebook-CheatSheet.md") -> None:
    cb = load_codebook(path)
    text = render_cheatsheet(cb)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(text, encoding="utf-8")
    con.print(f"[green]Wrote cheat sheet → {out}[/green]")

if __name__ == "__main__":
    app()
