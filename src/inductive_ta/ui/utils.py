from __future__ import annotations

import re
from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from ..codebook import load_codebook
from ..scaffold import TEMPLATE_HEADER
from ..utils import load_config


@dataclass
class SceneSegment:
    number: int
    heading: str
    body: str


def _project_paths() -> Dict[str, Path]:
    cfg = load_config()
    base = Path('.').resolve()
    paths = cfg.get('paths', {}) if isinstance(cfg, dict) else {}
    transcripts_dir = base / paths.get('transcripts_dir', '01_clean_transcripts')
    annotations_dir = base / '02_annotations'
    return {
        'base': base,
        'transcripts': transcripts_dir,
        'annotations': annotations_dir,
    }


def _scene_regex() -> re.Pattern[str]:
    cfg = load_config()
    markers = cfg.get('markers', {}) if isinstance(cfg, dict) else {}
    pattern = markers.get('scene_header_regex', r'^Scene\s*(?P<num>\d+)\s*:')
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


def _clean_header(pid: str) -> str:
    # Remove VS Code snippet placeholders when creating initial file via UI
    header = TEMPLATE_HEADER.format(pid=pid, scene='1')
    header = header.replace('${1|1,2,3,4,5|}', '1')
    return header


def ensure_annotation_file(participant_id: str) -> Path:
    paths = _project_paths()
    annotations_dir = paths['annotations']
    annotations_dir.mkdir(parents=True, exist_ok=True)
    md_path = annotations_dir / f'{participant_id}.md'
    if md_path.exists():
        return md_path

    transcripts_dir = paths['transcripts']
    txt_path = transcripts_dir / f'{participant_id}.txt'
    if not txt_path.exists():
        raise FileNotFoundError(f'Raw transcript not found for {participant_id}')

    raw_text = txt_path.read_text(encoding='utf-8', errors='replace')
    header = _clean_header(participant_id)
    md_path.write_text(f'{header}\n\n{raw_text}', encoding='utf-8')
    return md_path


def load_annotation_text(participant_id: str) -> Tuple[str, Path]:
    md_path = ensure_annotation_file(participant_id)
    text = md_path.read_text(encoding='utf-8', errors='replace')
    return text, md_path


def save_annotation_text(md_path: Path, text: str) -> None:
    md_path.write_text(text, encoding='utf-8')


def split_into_scenes(text: str) -> Tuple[str, List[SceneSegment]]:
    pattern = _scene_regex()
    matches = list(pattern.finditer(text))
    if not matches:
        return text, []

    scenes: List[SceneSegment] = []
    preamble = text[:matches[0].start()]

    for idx, match in enumerate(matches):
        heading = text[match.start():match.end()]
        try:
            raw_num = match.group('num')
        except IndexError:
            raw_num = match.group(1)
        number = int(raw_num)
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        scenes.append(SceneSegment(number=number, heading=heading, body=body))

    return preamble, scenes


def rebuild_document(preamble: str, scenes: Iterable[SceneSegment]) -> str:
    pieces: List[str] = [preamble]
    for scene in scenes:
        pieces.append(scene.heading)
        pieces.append(scene.body)
    return ''.join(pieces)


TAG_RX = re.compile(r'<([A-Z_]+)([^>]*)>')


def count_tags(text: str) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for match in TAG_RX.finditer(text):
        tag = match.group(1)
        counts[tag] += 1
    return dict(counts)


def list_participants() -> List[Dict[str, Any]]:
    paths = _project_paths()
    annotations_dir = paths['annotations']
    transcripts_dir = paths['transcripts']
    participants: Dict[str, Dict[str, Any]] = {}

    for txt_path in sorted(transcripts_dir.glob('P*.txt')):
        pid = txt_path.stem
        participants[pid] = {
            'participant_id': pid,
            'has_annotation': False,
            'tags_total': 0,
            'path': str(txt_path),
        }

    for md_path in sorted(annotations_dir.glob('P*.md')):
        pid = md_path.stem
        text = md_path.read_text(encoding='utf-8', errors='replace')
        counts = count_tags(text)
        total = sum(counts.values())
        entry = participants.setdefault(
            pid,
            {
                'participant_id': pid,
                'has_annotation': True,
                'tags_total': total,
                'path': str(md_path),
            },
        )
        entry['has_annotation'] = True
        entry['tags_total'] = total
        entry['path'] = str(md_path)
        entry['tag_counts'] = counts

    return sorted(participants.values(), key=lambda item: item['participant_id'])


def _extract_content_group(items: Dict[str, Any]) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    for key, value in items.items():
        output.append({'code': key, 'description': str(value)})
    return output


def load_codebook_spec() -> Dict[str, Any]:
    cb = load_codebook('codebook/codebook.yaml')
    tiers = cb.get('tiers', {})

    operations = [
        {'code': code, 'description': desc}
        for code, desc in tiers.get('A_Operations', {}).items()
    ]

    content = tiers.get('B_Content', {})
    features_dict = content.get('B1_FeatureFamily', {})
    feature_groups: Dict[str, List[Dict[str, str]]] = OrderedDict()
    for code, desc in features_dict.items():
        family = code.split('_', 1)[0]
        feature_groups.setdefault(family, []).append({'code': code, 'description': desc})

    truth_alignment = [
        'exact',
        'family_only',
        'off_target',
        'off_target_salience',
        'partial',
        'unknown',
    ]

    spec = {
        'operations': operations,
        'content': {
            'feature_groups': feature_groups,
            'polarity': _extract_content_group(content.get('B2_Polarity', {})),
            'evidence': _extract_content_group(content.get('B3_EvidenceType', {})),
            'abstraction': _extract_content_group(content.get('B4_Abstraction', {})),
            'confidence': _extract_content_group(content.get('B5_Confidence', {})),
            'error': _extract_content_group(content.get('B6_ErrorType', {})),
        },
        'strategy': tiers.get('C_Strategy', {}),
        'episode_fields': cb.get('episode_fields', []),
        'step_tags': cb.get('step_tags') or tiers.get('StepTags', {}),
        'truth_alignment': truth_alignment,
    }

    # Optional extra file with hedge tokens
    hedges_path = Path('codebook/codebook2.yaml')
    hedges: List[str] = []
    if hedges_path.exists():
        import yaml

        with hedges_path.open('r', encoding='utf-8') as handle:
            cb2 = yaml.safe_load(handle) or {}
            hedges = [token.lower() for token in cb2.get('hedges', [])]
    spec['hedges'] = hedges or ['maybe', 'i think', 'seems', 'guess', 'probably']
    return spec


def participant_payload(participant_id: str) -> Dict[str, Any]:
    text, md_path = load_annotation_text(participant_id)
    preamble, scenes = split_into_scenes(text)
    if not scenes:
        # treat whole document as Scene 1 body when no explicit markers
        scenes = [SceneSegment(number=1, heading='Scene 1:', body=text)]
        preamble = ''
    counts = count_tags(text)
    return {
        'participant_id': participant_id,
        'document_path': str(md_path),
        'preamble': preamble,
        'scenes': [
            {
                'number': scene.number,
                'heading': scene.heading,
                'body': scene.body,
            }
            for scene in scenes
        ],
        'stats': {
            'tag_counts': counts,
            'total_tags': sum(counts.values()),
        },
    }
