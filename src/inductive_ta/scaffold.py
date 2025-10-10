from __future__ import annotations

from pathlib import Path
from rich.console import Console
import typer

from .utils import load_config


TEMPLATE_HEADER = """<!--
Annotate micro-units by wrapping spans with Tier A tags, e.g.:

  <HYPOTHESIZE ep="EP1" feature="COLOR_Blue SIZE_Small" polarity="Presence" evidence="PositiveCases" confidence="Hedged">
    I think the rule is the presence of a small blue cone.
  </HYPOTHESIZE>

Add an optional episode summary after the textual episode using:

```episode
participant: {pid}
scene: {scene}
episode: EP1
strategy:
  search_mode: BreadthFirst
  hypothesis_management: SingleTrack
  evidence_policy: ConfirmOnly
complexity: Atomic
summary: one-sentence summary of the episode
```

Do not edit the raw content other than adding tags and episode blocks.
-->
"""


def _md_path_for(txt_path: Path, out_dir: Path) -> Path:
    return out_dir / (txt_path.stem + ".md")


def init_annotations(out_dir: Path) -> int:
    cfg = load_config()
    transcripts = Path(cfg["paths"]["transcripts_dir"])  # type: ignore[index]
    out_dir.mkdir(parents=True, exist_ok=True)
    created = 0

    for txt in sorted(transcripts.glob("P*.txt")):
        md = _md_path_for(txt, out_dir)
        if md.exists():
            continue
        raw = txt.read_text(encoding="utf-8", errors="replace")
        header = TEMPLATE_HEADER.format(pid=txt.stem, scene="${1|1,2,3,4,5|}")
        md.write_text(header + "\n\n" + raw, encoding="utf-8")
        created += 1
    return created


app = typer.Typer()


@app.command()
def init(out: str = "02_annotations") -> None:
    n = init_annotations(Path(out))
    Console().print(f"[green]Created {n} annotation files in {out}[/green]")


if __name__ == "__main__":
    app()

