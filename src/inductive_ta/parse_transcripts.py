from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Set

from rich.console import Console
from rich.progress import track
import typer

from .models import ParseReport, Turn
from .utils import find_scenes, iter_turns, load_config, normalize_text

app = typer.Typer()
console = Console()


@app.command()
def run() -> None:
    """Parse transcripts into JSONL and CSV exports."""
    cfg = load_config()
    paths: Dict[str, str] = cfg.get("paths", {})  # type: ignore[assignment]
    transcripts_dir = Path(paths["transcripts_dir"])
    exports_dir = Path(paths["exports_dir"])
    exports_dir.mkdir(parents=True, exist_ok=True)

    if not transcripts_dir.exists():
        console.print(f"[red]Transcripts directory not found: {transcripts_dir}[/red]")
        raise typer.Exit(code=1)

    scene_regex = re.compile(
        cfg["markers"]["scene_header_regex"], re.IGNORECASE | re.MULTILINE
    )
    tags: List[str] = cfg["markers"].get("tags", [])
    expected_scenes = cfg.get("scenes", [])

    jsonl_path = exports_dir / "corpus.jsonl"
    summary_rows: List[Dict[str, object]] = []
    participant_ids: Set[str] = set()
    turns_count: Dict[str, int] = {tag: 0 for tag in tags}
    total_turns = 0

    with jsonl_path.open("w", encoding="utf-8") as out:
        transcript_files = sorted(transcripts_dir.glob("P*.txt"))
        if not transcript_files:
            console.print(f"[yellow]No transcript files found in {transcripts_dir}[/yellow]")
        for transcript_path in track(transcript_files, description="Parsing transcripts"):
            participant_id = transcript_path.stem
            participant_ids.add(participant_id)
            raw_text = transcript_path.read_text(encoding="utf-8", errors="replace")
            normalized = normalize_text(raw_text, cfg)
            scenes = find_scenes(normalized, scene_regex)
            scenes = list(scenes)

            if not scenes:
                console.print(f"[yellow]No scenes found in {transcript_path}[/yellow]")
                continue

            # Handle transcripts missing the first header by treating the preamble as scene 1.
            if expected_scenes:
                existing_numbers = {scene_num for scene_num, *_ in scenes}
                first_expected = expected_scenes[0]
                if first_expected not in existing_numbers:
                    first_start = scenes[0][1]
                    preamble = normalized[:first_start].strip()
                    if preamble:
                        scenes.insert(0, (first_expected, 0, first_start))

            for scene_num, start, end in scenes:
                scene_text = normalized[start:end]
                offset = start
                turn_index = 0
                for tag, line, char_start, char_end in iter_turns(scene_text, tags, base_offset=offset):
                    turns_count.setdefault(tag, 0)
                    turn = Turn(
                        participant_id=participant_id,
                        scene=scene_num,
                        turn_index=turn_index,
                        tag=tag,
                        raw_text=line.strip(),
                        char_start=char_start,
                        char_end=char_end,
                    )
                    out.write(turn.model_dump_json() + "\n")
                    total_turns += 1
                    turns_count[tag] += 1
                    turn_index += 1

                summary_rows.append(
                    {
                        "participant_id": participant_id,
                        "scene": scene_num,
                        "turns": turn_index,
                    }
                )

    summary_path = exports_dir / "corpus_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as summary_file:
        fieldnames = ["participant_id", "scene", "turns"]
        writer = csv.DictWriter(summary_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    report = ParseReport(
        participants=len(participant_ids),
        scenes=len(summary_rows),
        turns=total_turns,
        reading_turns=turns_count.get("[READING]", 0),
        thinking_turns=turns_count.get("[THINKING]", 0),
        typing_turns=turns_count.get("[TYPING]", 0),
    )
    (exports_dir / "parse_report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    console.print(f"[green]Parsed {report.turns} turns across {report.scenes} scenes[/green]")


if __name__ == "__main__":
    app()