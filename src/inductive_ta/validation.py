from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence


TAG_TOKEN_RX = re.compile(r'<(/?)([A-Z_]+)([^>]*)>')
ATTR_RX = re.compile(r'([a-z_]+)="([^\"]*)"')


@dataclass
class ValidationContext:
    allowed_tags: Sequence[str]
    feature_codes: Sequence[str]
    polarity_codes: Sequence[str]
    evidence_codes: Sequence[str]
    abstraction_codes: Sequence[str]
    confidence_codes: Sequence[str]
    error_codes: Sequence[str]
    truth_alignment_codes: Sequence[str]

    def as_sets(self) -> Dict[str, set[str]]:
        return {
            'allowed_tags': set(self.allowed_tags),
            'feature_codes': set(self.feature_codes),
            'polarity_codes': set(self.polarity_codes),
            'evidence_codes': set(self.evidence_codes),
            'abstraction_codes': set(self.abstraction_codes),
            'confidence_codes': set(self.confidence_codes),
            'error_codes': set(self.error_codes),
            'truth_alignment_codes': set(self.truth_alignment_codes),
        }


DEFAULT_TRUTH_ALIGNMENT = [
    'exact',
    'family_only',
    'off_target',
    'off_target_salience',
    'partial',
    'unknown',
]


def build_context(spec: Dict[str, object]) -> ValidationContext:
    content = spec.get('content', {}) if isinstance(spec, dict) else {}
    features = []
    feature_groups = content.get('feature_groups', {}) if isinstance(content, dict) else {}
    for group_items in feature_groups.values():
        for item in group_items:
            features.append(item['code'])

    def _codes(key: str) -> List[str]:
        items = content.get(key, []) if isinstance(content, dict) else []
        return [item['code'] for item in items]

    return ValidationContext(
        allowed_tags=[item['code'] for item in spec.get('operations', [])],
        feature_codes=features,
        polarity_codes=_codes('polarity'),
        evidence_codes=_codes('evidence'),
        abstraction_codes=_codes('abstraction'),
        confidence_codes=_codes('confidence'),
        error_codes=_codes('error'),
        truth_alignment_codes=spec.get('truth_alignment', DEFAULT_TRUTH_ALIGNMENT),
    )


def validate_document(text: str, context: ValidationContext) -> List[str]:
    sets = context.as_sets()
    errors: List[str] = []
    stack: List[tuple[str, int]] = []

    for match in TAG_TOKEN_RX.finditer(text):
        closing, tag, attr_text = match.groups()
        pos = match.start()
        if closing:
            if not stack:
                errors.append(f'Unexpected closing tag </{tag}> at position {pos}')
                continue
            open_tag, open_pos = stack.pop()
            if open_tag != tag:
                errors.append(
                    f'Mismatched tag </{tag}> at position {pos}; expected </{open_tag}> for opening at {open_pos}'
                )
            continue

        stack.append((tag, pos))
        if tag not in sets['allowed_tags']:
            errors.append(f'Unknown tag <{tag}> at position {pos}')

        attrs = {}
        if attr_text:
            for attr_match in ATTR_RX.finditer(attr_text):
                attr_name, attr_value = attr_match.groups()
                attrs[attr_name] = attr_value

        allowed_attr_names = {
            'ep',
            'feature',
            'polarity',
            'evidence',
            'abstraction',
            'confidence',
            'error',
            'truth_alignment',
        }
        for attr_name in attrs:
            if attr_name not in allowed_attr_names:
                errors.append(f'Unknown attribute "{attr_name}" on <{tag}> at position {pos}')

        feature_val = attrs.get('feature')
        if feature_val:
            tokens = [token.strip() for token in feature_val.replace(',', ' ').split() if token.strip()]
            for token in tokens:
                if token not in sets['feature_codes']:
                    errors.append(f'Unknown feature token "{token}" on <{tag}> at position {pos}')

        def _check(attr: str, allowed_key: str) -> None:
            value = attrs.get(attr)
            if value and value not in sets[allowed_key]:
                errors.append(f'Invalid value "{value}" for attribute "{attr}" on <{tag}> at position {pos}')

        _check('polarity', 'polarity_codes')
        _check('evidence', 'evidence_codes')
        _check('abstraction', 'abstraction_codes')
        _check('confidence', 'confidence_codes')
        _check('error', 'error_codes')

        truth_alignment = attrs.get('truth_alignment')
        if truth_alignment and truth_alignment not in sets['truth_alignment_codes']:
            errors.append(
                f'Invalid value "{truth_alignment}" for attribute "truth_alignment" on <{tag}> at position {pos}'
            )

    if stack:
        for tag, pos in reversed(stack):
            errors.append(f'Unclosed tag <{tag}> opened at position {pos}')

    return errors

