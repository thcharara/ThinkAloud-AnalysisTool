from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml


def load_codebook(path: str = "codebook/codebook.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _sanitize_key(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", raw)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "CODE"


def _collect_codes(out: Dict[str, str], node: Any, prefix: str | None = None) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            label = str(key)
            new_prefix = f"{prefix}_{label}" if prefix else label
            if isinstance(value, (dict, list)):
                _collect_codes(out, value, new_prefix)
            else:
                out[_sanitize_key(new_prefix)] = str(value).strip() or label
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                label = item.strip()
                new_prefix = f"{prefix}_{label}" if prefix else label
                out[_sanitize_key(new_prefix)] = label
            elif isinstance(item, dict):
                _collect_codes(out, item, prefix)
    elif isinstance(node, str):
        label = node.strip()
        new_prefix = f"{prefix}_{label}" if prefix else label
        out[_sanitize_key(new_prefix)] = label


def _flatten_codes(cb: dict) -> Dict[str, str]:
    out: Dict[str, str] = {}
    tiers = cb.get("tiers", {})
    for tier_name, tier in tiers.items():
        _collect_codes(out, tier, tier_name)

    step_tags = cb.get("step_tags") or tiers.get("StepTags")
    if step_tags:
        _collect_codes(out, step_tags, "StepTags")

    return out


def validate_codebook(cb: dict) -> List[str]:
    errors: List[str] = []
    seen: set[str] = set()

    all_items = _flatten_codes(cb)
    key_rx = re.compile(r"^[A-Za-z0-9_]+$")
    for key, value in all_items.items():
        if key in seen:
            errors.append(f"Duplicate key: {key}")
        seen.add(key)
        if not key_rx.match(key):
            errors.append(f"Illegal key (only A–Z, 0–9, _): {key}")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Empty/missing description for: {key}")

    tiers = cb.get("tiers", {})
    for required in ["A_Operations", "B_Content", "C_Strategy"]:
        if required not in tiers:
            errors.append(f"Missing tier: {required}")

    if not (cb.get("step_tags") or tiers.get("StepTags")):
        errors.append("Missing: step tags")

    return errors


def _render_list(lines: List[str], entries: Any, indent: str = "") -> None:
    bullet = f"{indent}- "
    if isinstance(entries, dict):
        for key, value in entries.items():
            if isinstance(value, dict):
                lines.append(f"{bullet}**{key}**")
                _render_list(lines, value, indent + "  ")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        lines.append(f"{bullet}**{key}_{item}**")
                    else:
                        lines.append(f"{bullet}**{key}** — {item}")
            else:
                lines.append(f"{bullet}**{key}** — {value}")
    elif isinstance(entries, list):
        for item in entries:
            if isinstance(item, str):
                lines.append(f"{bullet}**{item}**")
            elif isinstance(item, dict):
                _render_list(lines, item, indent)
    elif isinstance(entries, str):
        lines.append(f"{bullet}**{entries}**")


def render_cheatsheet(cb: dict) -> str:
    lines: List[str] = []
    meta = cb.get("meta", {})
    name = meta.get("name") or cb.get("name") or "Codebook"
    version = meta.get("version") or cb.get("version")

    lines.append(f"# {name}")
    if version:
        lines.append(f"*Version:* {version}\n")

    tiers = cb.get("tiers", {})

    lines.append("## Tier A — Operations")
    _render_list(lines, tiers.get("A_Operations", []))

    lines.append("\n## Tier B — Content")
    for group, codes in tiers.get("B_Content", {}).items():
        lines.append(f"### {group}")
        _render_list(lines, codes)

    lines.append("\n## Tier C — Strategy")
    _render_list(lines, tiers.get("C_Strategy", []))

    step_tags = cb.get("step_tags") or tiers.get("StepTags", [])
    lines.append("\n## Step Tags")
    _render_list(lines, step_tags)

    return "\n".join(lines) + "\n"
