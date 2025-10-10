from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from rich.console import Console
import csv as _csv


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _split_features(value: str | None) -> List[str]:
    if not value:
        return []
    # split by spaces or commas
    parts: List[str] = []
    for token in value.replace(",", " ").split():
        parts.append(token.strip())
    return [p for p in parts if p]


def feature_attention_by_scene(micro_csv: Path, out_csv: Path) -> int:
    rows = _read_csv(micro_csv)
    counts: Dict[tuple, int] = defaultdict(int)
    for r in rows:
        if r.get("tag") != "HYPOTHESIZE":
            continue
        scene = r.get("scene") or "0"
        for feat in _split_features(r.get("feature")):
            # map to family if token contains underscore
            family = feat.split("_")[0]
            counts[(scene, family)] += 1

    # write
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["scene", "feature_family", "count"])
        writer.writeheader()
        for (scene, fam), c in sorted(counts.items(), key=lambda x: (int(x[0][0]), x[0][1])):
            writer.writerow({"scene": scene, "feature_family": fam, "count": c})
    return len(counts)


def operation_sequences_summary(seq_csv: Path, out_csv: Path) -> None:
    rows = _read_csv(seq_csv)
    lens = [len((r.get("sequence") or "").split(">")) for r in rows]
    if not lens:
        out_csv.write_text("", encoding="utf-8")
        return
    stats = {
        "n": len(lens),
        "min": min(lens),
        "max": max(lens),
        "avg": sum(lens) / len(lens),
    }
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stats.keys()))
        writer.writeheader()
        writer.writerow(stats)


def run_all(exports_dir: Path) -> None:
    con = Console()
    micro_csv = exports_dir / "annot_micro.csv"
    seq_csv = exports_dir / "annot_sequences.csv"
    fam_out = exports_dir / "feature_attention_by_scene.csv"
    seq_out = exports_dir / "operation_sequences_summary.csv"
    n = feature_attention_by_scene(micro_csv, fam_out)
    operation_sequences_summary(seq_csv, seq_out)
    con.print(f"[green]Wrote {n} feature-family rows → {fam_out}")

    # Optional: evidence policy by accuracy if metadata exists
    perf = Path("04_metadata/PartcipantPerformance.csv")
    if perf.exists():
        rows = _read_csv(micro_csv)
        # Map negative evidence usage per (P, Scene)
        neg_map: Dict[tuple, bool] = {}
        for r in rows:
            if r.get("tag") != "TEST_SEEK_EVIDENCE":
                continue
            key = (r.get("participant_id"), r.get("scene"))
            if (r.get("evidence") or "").lower().startswith("negative"):
                neg_map[key] = True
            else:
                neg_map.setdefault(key, False)
        perf_rows = _read_csv(perf)
        out_path = exports_dir / "evidence_policy_by_accuracy.csv"
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = _csv.writer(f)
            writer.writerow(["participant_id", "scene", "used_negative_evidence", "correct"])
            for pr in perf_rows:
                key = (pr.get("participant_id"), pr.get("Scene"))
                used_neg = neg_map.get(key, False)
                correct = pr.get("Correct (0/1)")
                writer.writerow([key[0], key[1], int(used_neg), correct])
        con.print(f"[green]Wrote evidence-policy by accuracy → {out_path}")
