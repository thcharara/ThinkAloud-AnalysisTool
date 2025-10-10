from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, Tuple, Union

import yaml
from unidecode import unidecode


def load_config() -> Dict[str, object]:
    """Read the project configuration from config/config.yaml."""
    config_path = Path("config/config.yaml")
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_text(s: str, cfg: Dict[str, object]) -> str:
    """Normalize raw transcript text according to config flags."""
    options = cfg.get("normalize", {}) if isinstance(cfg, dict) else {}
    text = s

    if options.get("smart_quotes"):
        smart_quote_map = {
            "“": '"',
            "”": '"',
            "„": '"',
            "‟": '"',
            "‘": "'",
            "’": "'",
            "‚": "'",
            "‛": "'",
        }
        text = text.translate(str.maketrans(smart_quote_map))

    if options.get("ellipses_to_three_dots"):
        text = text.replace("…", "...")

    if options.get("dashes_to_hyphen"):
        dash_chars = ["—", "–", "‒", "−"]
        for dash in dash_chars:
            text = text.replace(dash, "-")

    if options.get("ascii_fallback"):
        text = unidecode(text)

    return text


def find_scenes(text: str, regex: Union[str, re.Pattern]) -> List[Tuple[int, int, int]]:
    """Return (scene_number, start, end) tuples for each detected scene chunk."""
    pattern = re.compile(regex, re.MULTILINE) if isinstance(regex, str) else regex
    matches = list(pattern.finditer(text))
    scenes: List[Tuple[int, int, int]] = []

    for idx, match in enumerate(matches):
        try:
            raw_num = match.group("num") if "num" in match.groupdict() else match.group(1)
        except IndexError as exc:  # pragma: no cover - malformed pattern
            raise ValueError("Scene header regex must capture the scene number") from exc

        if raw_num is None:
            raise ValueError("Scene header regex must expose a 'num' named group or first group")

        scene_num = int(raw_num)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        scenes.append((scene_num, start, end))

    return scenes


def iter_turns(
    scene_text: str,
    tags: Sequence[str],
    base_offset: int = 0,
) -> Iterator[Tuple[str, str, int, int]]:
    """Yield (tag, text, abs_start, abs_end) for each non-empty line within a scene."""
    tag_set = set(tags)
    default_tag = "[THINKING]" if "[THINKING]" in tag_set else (tags[0] if tags else "[THINKING]")

    idx = 0
    length = len(scene_text)

    while idx < length:
        newline_pos = scene_text.find("\n", idx)
        if newline_pos == -1:
            line_terminus = length
            next_idx = length
        else:
            line_terminus = newline_pos
            next_idx = newline_pos + 1

        raw_line = scene_text[idx:line_terminus]
        if raw_line.endswith("\r"):
            raw_line = raw_line[:-1]

        stripped_total = raw_line.strip()
        if not stripped_total:
            idx = next_idx
            continue

        leading_ws = len(raw_line) - len(raw_line.lstrip())
        trailing_ws = len(raw_line) - len(raw_line.rstrip())
        working = raw_line.lstrip()

        tag = default_tag
        content = working
        content_offset = leading_ws

        if working:
            split_idx = working.find(" ")
            token = working if split_idx == -1 else working[:split_idx]
            remainder = "" if split_idx == -1 else working[split_idx:]

            if token in tag_set:
                tag = token
                remainder_lstripped = remainder.lstrip()
                consumed = len(working) - len(remainder_lstripped)
                content_offset = leading_ws + consumed
                content = remainder_lstripped
            else:
                content = working

        abs_start = base_offset + idx + content_offset
        abs_end = base_offset + idx + len(raw_line) - trailing_ws

        yield tag, content, abs_start, abs_end
        idx = next_idx
