"""Advanced analytics for coded transcripts."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from .codebook import load_codebook
from .models import Turn, Episode


TAG_RX = re.compile(
    r'<(?P<tag>[A-Z_]+)(?P<attrs>[^>]*)>(?P<content>.*?)</(?P=tag)>',
    re.DOTALL,
)
ATTR_RX = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"(.*?)"')


def extract_operation_sequence(text: str) -> List[Tuple[str, int]]:
    """Extract sequence of operations with positions."""
    operations = []
    for match in TAG_RX.finditer(text):
        tag = match.group('tag')
        operations.append((tag, match.start()))
    return operations


def detect_incomplete_cycles(text: str) -> List[Dict]:
    """Detect incomplete reasoning cycles (e.g., HYP without TEST)."""
    issues = []
    operations = extract_operation_sequence(text)

    for i, (tag, pos) in enumerate(operations):
        if tag == 'HYPOTHESIZE':
            # Look for TEST_SEEK_EVIDENCE within next 5 operations
            found_test = False
            for j in range(i+1, min(i+6, len(operations))):
                if operations[j][0] == 'TEST_SEEK_EVIDENCE':
                    found_test = True
                    break

            if not found_test:
                issues.append({
                    'type': 'incomplete_cycle',
                    'tag': 'HYPOTHESIZE',
                    'position': pos,
                    'message': 'HYPOTHESIZE not followed by TEST_SEEK_EVIDENCE',
                })

        elif tag == 'TEST_SEEK_EVIDENCE':
            # Look for EVALUATE_REVISE or META_COGNITION
            found_eval = False
            for j in range(i+1, min(i+4, len(operations))):
                if operations[j][0] in ('EVALUATE_REVISE', 'META_COGNITION'):
                    found_eval = True
                    break

            if not found_eval:
                issues.append({
                    'type': 'incomplete_cycle',
                    'tag': 'TEST_SEEK_EVIDENCE',
                    'position': pos,
                    'message': 'TEST_SEEK_EVIDENCE not followed by evaluation',
                })

    return issues


def calculate_code_usage_stats(text: str) -> Dict:
    """Calculate comprehensive code usage statistics."""
    codebook = load_codebook('codebook/codebook.yaml')
    tiers = codebook.get('tiers', {})
    operations = set(tiers.get('A_Operations', {}).keys())

    tag_counts = Counter()
    attribute_counts = defaultdict(Counter)

    for match in TAG_RX.finditer(text):
        tag = match.group('tag')
        tag_counts[tag] += 1

        attrs_raw = match.group('attrs') or ''
        attrs: Dict[str, str] = {}
        for am in ATTR_RX.finditer(attrs_raw):
            attrs[am.group(1)] = am.group(2)

        for key, value in attrs.items():
            if value:
                attribute_counts[key][value] += 1

    # Detect unused operations
    used_operations = set(tag_counts.keys()) & operations
    unused_operations = operations - used_operations

    return {
        'tag_counts': dict(tag_counts),
        'attribute_counts': {k: dict(v) for k, v in attribute_counts.items()},
        'unused_operations': list(unused_operations),
        'total_tags': sum(tag_counts.values()),
        'operation_diversity': len(used_operations) / len(operations) if operations else 0,
    }


def validate_evidence_citations(text: str, available_panels: List[str]) -> List[Dict]:
    """Validate that evidence citations reference valid panels."""
    issues = []
    available_set = set(available_panels)

    for match in TAG_RX.finditer(text):
        tag = match.group('tag')
        if tag != 'TEST_SEEK_EVIDENCE':
            continue

        attrs_raw = match.group('attrs') or ''
        attrs: Dict[str, str] = {}
        for am in ATTR_RX.finditer(attrs_raw):
            attrs[am.group(1)] = am.group(2)

        evidence = attrs.get('evidence_cited', '')
        if evidence:
            # Parse panel references (e.g., "A, C, F" or "panels A and C")
            panel_pattern = re.compile(r'\b([A-F])\b')
            cited_panels = panel_pattern.findall(evidence.upper())

            for panel in cited_panels:
                if panel not in available_set:
                    issues.append({
                        'type': 'invalid_panel',
                        'position': match.start(),
                        'panel': panel,
                        'message': f'Panel {panel} not found in available panels',
                    })

    return issues


def detect_attribute_mismatches(text: str) -> List[Dict]:
    """Detect attributes applied to inappropriate tags."""
    issues = []

    # Rules for attribute-tag compatibility
    evidence_required_tags = {'TEST_SEEK_EVIDENCE', 'HYPOTHESIZE'}
    error_required_tags = {'EVALUATE_REVISE'}

    for match in TAG_RX.finditer(text):
        tag = match.group('tag')
        attrs_raw = match.group('attrs') or ''
        attrs: Dict[str, str] = {}
        for am in ATTR_RX.finditer(attrs_raw):
            attrs[am.group(1)] = am.group(2)

        # Check for evidence attribute on non-testing tags
        if 'evidence' in attrs and tag not in evidence_required_tags:
            issues.append({
                'type': 'attribute_mismatch',
                'position': match.start(),
                'tag': tag,
                'attribute': 'evidence',
                'message': f'Evidence attribute typically not used with {tag}',
            })

        # Check for error attribute without EVALUATE_REVISE
        if 'error' in attrs and tag not in error_required_tags:
            issues.append({
                'type': 'attribute_mismatch',
                'position': match.start(),
                'tag': tag,
                'attribute': 'error',
                'message': f'Error attribute typically only used with EVALUATE_REVISE',
            })

    return issues


def calculate_inter_rater_agreement(text_a: str, text_b: str) -> Dict:
    """Calculate agreement metrics between two coders."""
    tags_a = extract_operation_sequence(text_a)
    tags_b = extract_operation_sequence(text_b)

    # Simple overlap based on tag types
    tags_a_types = Counter(t[0] for t in tags_a)
    tags_b_types = Counter(t[0] for t in tags_b)

    all_tags = set(tags_a_types.keys()) | set(tags_b_types.keys())

    agreements = 0
    disagreements = 0

    for tag in all_tags:
        count_a = tags_a_types.get(tag, 0)
        count_b = tags_b_types.get(tag, 0)
        agreements += min(count_a, count_b)
        disagreements += abs(count_a - count_b)

    total = agreements + disagreements
    agreement_rate = agreements / total if total > 0 else 0

    return {
        'agreement_rate': agreement_rate,
        'agreements': agreements,
        'disagreements': disagreements,
        'total_codes': total,
        'tag_counts_a': dict(tags_a_types),
        'tag_counts_b': dict(tags_b_types),
    }


def generate_timeline_data(text: str, scene_boundaries: List[Tuple[int, int]]) -> Dict:
    """Generate timeline visualization data."""
    operations = []

    for match in TAG_RX.finditer(text):
        tag = match.group('tag')
        content = match.group('content').strip()
        attrs_raw = match.group('attrs') or ''

        attrs: Dict[str, str] = {}
        for am in ATTR_RX.finditer(attrs_raw):
            attrs[am.group(1)] = am.group(2)

        # Determine scene
        scene = 1
        for scene_num, (start, end) in enumerate(scene_boundaries, 1):
            if start <= match.start() < end:
                scene = scene_num
                break

        operations.append({
            'tag': tag,
            'position': match.start(),
            'scene': scene,
            'snippet': content[:80] + '...' if len(content) > 80 else content,
            'episode': attrs.get('ep', attrs.get('episode', '')),
            'confidence': attrs.get('confidence', ''),
            'features': attrs.get('feature', '').split() if attrs.get('feature') else [],
        })

    return {
        'operations': operations,
        'total': len(operations),
        'by_scene': _group_by_scene(operations),
    }


def _group_by_scene(operations: List[Dict]) -> Dict[int, List[Dict]]:
    """Group operations by scene."""
    by_scene = defaultdict(list)
    for op in operations:
        by_scene[op['scene']].append(op)
    return dict(by_scene)


def get_cross_scene_patterns(text: str, scene_boundaries: List[Tuple[int, int]]) -> Dict:
    """Detect patterns that span multiple scenes."""
    timeline = generate_timeline_data(text, scene_boundaries)
    operations = timeline['operations']

    # Track features across scenes
    features_by_scene = defaultdict(set)
    for op in operations:
        if op['features']:
            features_by_scene[op['scene']].update(op['features'])

    # Detect perseveration (same features appearing in multiple scenes)
    feature_appearances = defaultdict(list)
    for scene, features in features_by_scene.items():
        for feature in features:
            feature_appearances[feature].append(scene)

    perseverations = {
        feature: scenes
        for feature, scenes in feature_appearances.items()
        if len(scenes) > 1
    }

    # Detect complexity escalation
    complexity_by_scene = {}
    for scene, ops in timeline['by_scene'].items():
        feature_counts = [len(op['features']) for op in ops if op['features']]
        avg_complexity = sum(feature_counts) / len(feature_counts) if feature_counts else 0
        complexity_by_scene[scene] = avg_complexity

    return {
        'features_by_scene': {k: list(v) for k, v in features_by_scene.items()},
        'perseverations': perseverations,
        'complexity_by_scene': complexity_by_scene,
        'total_scenes_coded': len(features_by_scene),
    }


# ============================================================================
# Suggestion Heuristics and Scene Summaries
# ============================================================================

HEDGE_WORDS = {
    'maybe', 'i think', 'i guess', 'i feel', 'i suppose', 'seems', 'probably', 'perhaps',
    'i wonder', 'not sure', "i'm not sure", 'i do not know', "i don't know",
}

FEATURE_KEYWORDS = {
    'blue': 'COLOR_Blue',
    'green': 'COLOR_Green',
    'red': 'COLOR_Red',
    'small': 'SIZE_Small',
    'little': 'SIZE_Small',
    'tiny': 'SIZE_Small',
    'large': 'SIZE_Large',
    'big': 'SIZE_Large',
    'upright': 'ORIENTATION_Upright',
    'right side up': 'ORIENTATION_Upright',
    'standing': 'ORIENTATION_Upright',
    'slanted': 'ORIENTATION_Slanted',
    'sideways': 'ORIENTATION_Slanted',
    'tilted': 'ORIENTATION_Slanted',
    'horizontal': 'ORIENTATION_Horizontal',
    'lying': 'ORIENTATION_Horizontal',
    'upside down': 'ORIENTATION_UpsideDown',
    'inverted': 'ORIENTATION_UpsideDown',
    'above': 'POSITIONREL_AboveBelow',
    'on top of': 'POSITIONREL_AboveBelow',
    'stacked': 'POSITIONREL_AboveBelow',
    'next to': 'POSITIONREL_Adjacency',
    'beside': 'POSITIONREL_Adjacency',
    'together': 'POSITIONREL_Adjacency',
    'at least': 'COUNT_Presence',
    'has a': 'COUNT_Presence',
    'have a': 'COUNT_Presence',
    'exactly': 'COUNT_ExactN',
    'just one': 'COUNT_ExactN',
    'only one': 'COUNT_ExactN',
    'two': 'COUNT_ExactN',
}

POLARITY_HOOKS = {
    'must': 'Presence',
    'has to': 'Presence',
    'needs to': 'Presence',
    'always': 'Presence',
    'only if': 'Conditional',
    'if': 'Conditional',
    'when': 'Conditional',
    'unless': 'Conditional',
    'without': 'Absence',
    'no': 'Absence',
    'none': 'Absence',
    "doesn't": 'Absence',
    'never': 'Absence',
}

OPERATION_RULES = [
    ('HYPOTHESIZE', ['i think', 'maybe', 'rule is', 'must be', 'i guess', 'i suppose', 'i believe']),
    ('TEST_SEEK_EVIDENCE', ['does', 'do', 'check', 'see if', 'look at', 'verify']),
    ('EVALUATE_REVISE', ['does not', "doesn't", 'not working', 'no longer', "i don't think", 'maybe not', 'that fails']),
    ('META_COGNITION', ['hard', 'difficult', 'confused', 'no idea', "i'm stuck", 'not sure what to do', 'frustrating']),
    ('COMPARE_CONTRAST', ['than', 'compared', 'difference', 'different from', 'whereas', 'while this']),
]


def suggest_turn_codes(text: str, tag: Optional[str] = None) -> Dict[str, object]:
    """Generate lightweight suggestions for a single turn."""
    lower = text.lower()
    suggestions: Dict[str, object] = {
        'tier_a': None,
        'tier_b': [],
        'polarity': None,
        'confidence': None,
        'step_tag': None,
        'notes': [],
    }

    # Tier A suggestion
    if tag == '[TYPING]':
        suggestions['tier_a'] = 'RESPONSE_ENTRY'
    else:
        for code, cues in OPERATION_RULES:
            if any(cue in lower for cue in cues):
                suggestions['tier_a'] = code
                break

    # Feature families
    seen = set()
    for cue, code in FEATURE_KEYWORDS.items():
        if cue in lower and code not in seen:
            seen.add(code)
    if seen:
        suggestions['tier_b'] = list(seen)

    # Polarity cues
    for cue, code in POLARITY_HOOKS.items():
        if cue in lower:
            suggestions['polarity'] = code
            break

    # Confidence hedges
    for hedge in HEDGE_WORDS:
        if hedge in lower:
            suggestions['confidence'] = 'Hedged'
            break

    # Step-tag heuristics
    if suggestions['tier_a'] == 'HYPOTHESIZE':
        suggestions['step_tag'] = 'STEP_HYP'
    elif suggestions['tier_a'] == 'TEST_SEEK_EVIDENCE':
        suggestions['step_tag'] = 'STEP_TEST_CONFIRM'
    elif suggestions['tier_a'] == 'EVALUATE_REVISE':
        suggestions['step_tag'] = 'STEP_REVISE'
    elif suggestions['tier_a'] == 'OBSERVE_DESCRIBE':
        suggestions['step_tag'] = 'STEP_OBS'

    if 'not sure' in lower or "don't know" in lower:
        suggestions['notes'].append('Uncertainty language detected.')

    return suggestions


FEATURE_PREFIXES = ('COLOR_', 'SIZE_', 'ORIENTATION_', 'POSITIONREL_', 'COUNT_')


def compute_scene_statistics(turns: List[Turn], episodes: List[Episode]) -> Dict[str, object]:
    """Return aggregated counts for operations, features, transitions, and episodes."""
    operations = Counter()
    step_tags = Counter()
    transitions = Counter()
    feature_counts = Counter()

    last_step = None
    for turn in turns:
        if turn.A_operation:
            operations[turn.A_operation] += 1
        if turn.step_tag:
            step_tags[turn.step_tag] += 1
            if last_step:
                transitions[(last_step, turn.step_tag)] += 1
            last_step = turn.step_tag
        else:
            last_step = None

        if turn.A_operation == 'HYPOTHESIZE' and turn.B_content:
            for code in turn.B_content:
                if code.startswith(FEATURE_PREFIXES):
                    feature_counts[code] += 1

    evidence_policy_counts = Counter()
    outcome_counts = Counter()
    distance_counts = Counter()
    for episode in episodes:
        if episode.StrategyCodes:
            for code in episode.StrategyCodes:
                if code.startswith('EvidencePolicy_'):
                    evidence_policy_counts[code] += 1
        if episode.Outcome:
            outcome_counts[episode.Outcome] += 1
        if episode.DistanceToTruth:
            distance_counts[episode.DistanceToTruth] += 1

    def _counter_to_sorted_list(counter: Counter) -> List[Dict[str, object]]:
        return [
            {'code': key, 'count': value}
            for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        ]

    return {
        'operations': _counter_to_sorted_list(operations),
        'step_tags': _counter_to_sorted_list(step_tags),
        'feature_counts': _counter_to_sorted_list(feature_counts),
        'transitions': [
            {'from': src, 'to': dst, 'count': count}
            for (src, dst), count in sorted(transitions.items(), key=lambda item: (-item[1], item[0]))
        ],
        'evidence_policies': _counter_to_sorted_list(evidence_policy_counts),
        'episode_outcomes': _counter_to_sorted_list(outcome_counts),
        'distance_to_truth': _counter_to_sorted_list(distance_counts),
        'total_turns': len(turns),
        'total_episodes': len(episodes),
    }
