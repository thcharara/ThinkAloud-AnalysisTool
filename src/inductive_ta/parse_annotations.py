from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import yaml
from rich.console import Console
from rich.progress import track
import typer

from .annot_schema import Episode, MicroUnit, Sequence
from .codebook import load_codebook
from .utils import find_scenes, load_config


@dataclass
class _CodebookIndex:
    operations: set[str]
    features: set[str]
    polarities: set[str]
    evidence_types: set[str]
    abstractions: set[str]
    confidences: set[str]
    errors: set[str]


def _index_codebook(cb: dict) -> _CodebookIndex:
    tiers = cb.get("tiers", {})
    ops = set(tiers.get("A_Operations", {}).keys())
    b = tiers.get("B_Content", {})
    # Flatten B1 features (keys may be nested dicts)
    features: set[str] = set()
    family = b.get("B1_FeatureFamily", {})
    for key in family.keys():
        features.add(key)
    pol = set((b.get("B2_Polarity", {}) or {}).keys())
    ev = set((b.get("B3_EvidenceType", {}) or {}).keys())
    ab = set((b.get("B4_Abstraction", {}) or {}).keys())
    conf = set((b.get("B5_Confidence", {}) or {}).keys())
    err = set((b.get("B6_ErrorType", {}) or {}).keys())
    return _CodebookIndex(ops, features, pol, ev, ab, conf, err)


ATTR_RX = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\"(.*?)\"")
TAG_RX = re.compile(
    r"<(?P<tag>[A-Z_]+)(?P<attrs>[^>]*)>(?P<content>.*?)</(?P=tag)>",
    re.DOTALL,
)
EP_BLOCK_RX = re.compile(r"```episode\s*(?P<body>.*?)```", re.DOTALL | re.IGNORECASE)


def _iter_tagged(text: str) -> Iterator[Tuple[str, Dict[str, str], str, int, int]]:
    for m in TAG_RX.finditer(text):
        tag = m.group("tag")
        attrs_raw = m.group("attrs") or ""
        content = m.group("content").strip()
        attrs: Dict[str, str] = {}
        for am in ATTR_RX.finditer(attrs_raw):
            key = am.group(1)
            val = am.group(2)
            attrs[key] = val
        yield tag, attrs, content, m.start(), m.end()


def _parse_episode_blocks(text: str, participant: str, scene: int) -> List[Episode]:
    out: List[Episode] = []
    for m in EP_BLOCK_RX.finditer(text):
        body = m.group("body").strip()
        try:
            data = yaml.safe_load(body) or {}
        except Exception:
            data = {"summary": body}
        episode_id = str(data.get("episode") or data.get("ep") or "EP?")
        ep = Episode(
            participant=participant,
            scene=scene,
            episode=episode_id,
            strategy_search_mode=(data.get("strategy", {}) or {}).get("search_mode"),
            strategy_hypothesis_management=(data.get("strategy", {}) or {}).get(
                "hypothesis_management"
            ),
            strategy_evidence_policy=(data.get("strategy", {}) or {}).get(
                "evidence_policy"
            ),
            complexity=data.get("complexity"),
            cross_scene_shift=data.get("cross_scene_shift"),
            hypothesis_verbatim=data.get("hypothesis_verbatim") or data.get(
                "hypothesis"
            ),
            feature_bundle=(
                ",".join(data.get("feature_bundle", []))
                if isinstance(data.get("feature_bundle"), list)
                else data.get("feature_bundle")
            ),
            evidence_cited=data.get("evidence_cited"),
            confidence=data.get("confidence"),
            outcome=data.get("outcome"),
            summary=data.get("summary"),
        )
        out.append(ep)
    return out


def parse_annotations(path: Path, idx: _CodebookIndex, cfg: dict) -> Tuple[List[MicroUnit], List[Episode]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    scene_rx = re.compile(
        cfg["markers"]["scene_header_regex"], re.IGNORECASE | re.MULTILINE
    )
    scenes = find_scenes(text, scene_rx)
    if not scenes:
        # Treat whole document as scene 1
        scenes = [(1, 0, len(text))]
    participant = path.stem

    micro: List[MicroUnit] = []
    episodes: List[Episode] = []

    for scene_num, start, end in scenes:
        chunk = text[start:end]
        # Episode YAML blocks first (optional)
        episodes.extend(_parse_episode_blocks(chunk, participant, scene_num))

        for tag, attrs, content, abs_start, abs_end in _iter_tagged(text):
            if abs_start < start or abs_start >= end:
                continue
            unit = MicroUnit(
                participant_id=participant,
                scene=scene_num,
                tag=tag,
                text=content,
                ep=attrs.get("ep") or attrs.get("episode"),
                feature=attrs.get("feature"),
                polarity=attrs.get("polarity"),
                evidence=attrs.get("evidence"),
                abstraction=attrs.get("abstraction"),
                confidence=attrs.get("confidence"),
                error=attrs.get("error"),
                truth_alignment=attrs.get("truth_alignment"),
                file=str(path),
                char_start=abs_start,
                char_end=abs_end,
            )
            micro.append(unit)

    return micro, episodes


def _write_csv(path: Path, rows: Iterable[dict], header: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_annotations(annotations_dir: Path, exports_dir: Path, codebook_path: str) -> Tuple[int, int]:
    cfg = load_config()
    cb = load_codebook(codebook_path)
    idx = _index_codebook(cb)

    exports_dir.mkdir(parents=True, exist_ok=True)
    micro_rows: List[dict] = []
    episode_rows: List[dict] = []
    seq_rows: List[dict] = []

    md_files = sorted(annotations_dir.glob("P*.md"))
    con = Console()
    if not md_files:
        con.print(f"[yellow]No annotated files found in {annotations_dir} (expected Pxx.md)[/yellow]")

    for path in track(md_files, description="Exporting annotations"):
        micro, episodes = parse_annotations(path, idx, cfg)

        # micro rows
        for u in micro:
            row = u.model_dump()
            micro_rows.append(row)

        # episode rows
        for e in episodes:
            row = e.model_dump()
            episode_rows.append(row)

        # sequences by scene
        by_scene: Dict[int, List[MicroUnit]] = {}
        for u in micro:
            by_scene.setdefault(u.scene, []).append(u)
        for scene, lst in by_scene.items():
            ordered = sorted(lst, key=lambda x: (x.char_start or 0))
            seq = [u.tag for u in ordered]
            seq_rows.append({
                "participant": path.stem,
                "scene": scene,
                "sequence": ">".join(seq),
            })

    # Write files
    micro_path = exports_dir / "annot_micro.csv"
    ep_path = exports_dir / "annot_episodes.csv"
    seq_path = exports_dir / "annot_sequences.csv"

    micro_header = [
        "participant_id",
        "scene",
        "tag",
        "text",
        "ep",
        "feature",
        "polarity",
        "evidence",
        "abstraction",
        "confidence",
        "error",
        "truth_alignment",
        "file",
        "char_start",
        "char_end",
    ]
    _write_csv(micro_path, micro_rows, micro_header)

    ep_header = list({k for row in episode_rows for k in row.keys()})
    if ep_header:
        # order some important columns first
        prefer = [
            "participant",
            "scene",
            "episode",
            "summary",
            "hypothesis_verbatim",
            "feature_bundle",
            "evidence_cited",
            "confidence",
            "outcome",
            "strategy_search_mode",
            "strategy_hypothesis_management",
            "strategy_evidence_policy",
            "complexity",
            "cross_scene_shift",
        ]
        rest = [c for c in ep_header if c not in prefer]
        header = [c for c in prefer if c in ep_header] + rest
        _write_csv(ep_path, episode_rows, header)
    else:
        ep_path.write_text("", encoding="utf-8")

    _write_csv(seq_path, seq_rows, ["participant", "scene", "sequence"])

    return len(micro_rows), len(episode_rows)


app = typer.Typer()


@app.command()
def export(
    annotations: str = "02_annotations",
    exports: str = "05_exports",
    codebook: str = "codebook/codebook.yaml",
) -> None:
    annotations_dir = Path(annotations)
    exports_dir = Path(exports)
    micro_n, ep_n = export_annotations(annotations_dir, exports_dir, codebook)
    Console().print(
        f"[green]Wrote micro={micro_n} rows and episodes={ep_n} rows → {exports_dir}[/green]"
    )


if __name__ == "__main__":
    app()
