"""Hypothesis tracking and evolution analysis."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .codebook import load_codebook
from .utils import load_config


@dataclass
class HypothesisInstance:
    """A single hypothesis mention in the transcript."""
    id: str
    participant: str
    scene: int
    episode: str
    verbatim: str
    features: List[str]
    evidence_cited: str
    confidence: str
    outcome: str  # accepted|revised|rejected|pending
    position: int  # character position in document
    related_tags: List[str] = field(default_factory=list)  # tag IDs that reference this hypothesis

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'participant': self.participant,
            'scene': self.scene,
            'episode': self.episode,
            'verbatim': self.verbatim,
            'features': self.features,
            'evidence_cited': self.evidence_cited,
            'confidence': self.confidence,
            'outcome': self.outcome,
            'position': self.position,
            'related_tags': self.related_tags,
        }


@dataclass
class HypothesisEvolution:
    """Tracks how a hypothesis evolves across scenes."""
    root_id: str
    participant: str
    initial_scene: int
    instances: List[HypothesisInstance]
    relationship_type: str  # original|refined|contradiction|perseveration

    def to_dict(self) -> Dict:
        return {
            'root_id': self.root_id,
            'participant': self.participant,
            'initial_scene': self.initial_scene,
            'instances': [h.to_dict() for h in self.instances],
            'relationship_type': self.relationship_type,
        }


EP_BLOCK_RX = re.compile(r'```episode\s*(?P<body>.*?)```', re.DOTALL | re.IGNORECASE)
TAG_RX = re.compile(
    r'<(?P<tag>[A-Z_]+)(?P<attrs>[^>]*)>(?P<content>.*?)</(?P=tag)>',
    re.DOTALL,
)
ATTR_RX = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"(.*?)"')


def extract_hypotheses_from_text(text: str, participant: str) -> List[HypothesisInstance]:
    """Extract all hypotheses from annotated text."""
    hypotheses: List[HypothesisInstance] = []

    # Extract from episode blocks
    for match in EP_BLOCK_RX.finditer(text):
        body = match.group('body').strip()
        lines = body.split('\n')
        data: Dict[str, str] = {}

        for line in lines:
            if ':' in line:
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()
                data[key] = value

        episode = data.get('episode', data.get('ep', ''))
        scene = int(data.get('scene', 0))
        verbatim = data.get('hypothesis_verbatim', '')
        features_str = data.get('feature_bundle', '')
        features = [f.strip() for f in features_str.split(',') if f.strip()]

        if verbatim and episode:
            hyp = HypothesisInstance(
                id=f"{participant}_{scene}_{episode}",
                participant=participant,
                scene=scene,
                episode=episode,
                verbatim=verbatim,
                features=features,
                evidence_cited=data.get('evidence_cited', ''),
                confidence=data.get('confidence', ''),
                outcome=data.get('outcome', 'pending'),
                position=match.start(),
            )
            hypotheses.append(hyp)

    # Also extract from HYPOTHESIZE tags
    for match in TAG_RX.finditer(text):
        tag = match.group('tag')
        if tag != 'HYPOTHESIZE':
            continue

        attrs_raw = match.group('attrs') or ''
        content = match.group('content').strip()

        attrs: Dict[str, str] = {}
        for am in ATTR_RX.finditer(attrs_raw):
            attrs[am.group(1)] = am.group(2)

        episode = attrs.get('ep', attrs.get('episode', ''))
        scene = 0  # Would need context to determine
        feature_str = attrs.get('feature', '')
        features = [f.strip() for f in feature_str.split() if f.strip()]

        if content and episode:
            hyp_id = f"{participant}_tag_{match.start()}"
            hyp = HypothesisInstance(
                id=hyp_id,
                participant=participant,
                scene=scene,
                episode=episode,
                verbatim=content[:200],
                features=features,
                evidence_cited=attrs.get('evidence', ''),
                confidence=attrs.get('confidence', ''),
                outcome='pending',
                position=match.start(),
            )
            hypotheses.append(hyp)

    return sorted(hypotheses, key=lambda h: h.position)


def detect_hypothesis_evolution(hypotheses: List[HypothesisInstance]) -> List[HypothesisEvolution]:
    """Detect how hypotheses evolve across scenes."""
    evolutions: List[HypothesisEvolution] = []

    # Group by participant
    by_participant: Dict[str, List[HypothesisInstance]] = {}
    for hyp in hypotheses:
        by_participant.setdefault(hyp.participant, []).append(hyp)

    for participant, participant_hyps in by_participant.items():
        # Sort by scene
        sorted_hyps = sorted(participant_hyps, key=lambda h: (h.scene, h.position))

        # Simple grouping by feature overlap
        processed = set()
        for i, hyp in enumerate(sorted_hyps):
            if hyp.id in processed:
                continue

            evolution = HypothesisEvolution(
                root_id=hyp.id,
                participant=participant,
                initial_scene=hyp.scene,
                instances=[hyp],
                relationship_type='original',
            )
            processed.add(hyp.id)

            # Look for related hypotheses in later scenes
            hyp_features = set(hyp.features)
            for later_hyp in sorted_hyps[i+1:]:
                if later_hyp.id in processed:
                    continue

                later_features = set(later_hyp.features)
                overlap = hyp_features & later_features

                if overlap:
                    evolution.instances.append(later_hyp)
                    processed.add(later_hyp.id)

                    # Determine relationship type
                    if later_hyp.outcome == 'rejected' and hyp.outcome == 'rejected':
                        evolution.relationship_type = 'perseveration'
                    elif len(later_features) > len(hyp_features):
                        evolution.relationship_type = 'refined'

            if len(evolution.instances) > 1:
                evolutions.append(evolution)

    return evolutions


def get_hypothesis_graph(participant: str, annotation_text: str) -> Dict:
    """Generate a hypothesis graph for visualization."""
    hypotheses = extract_hypotheses_from_text(annotation_text, participant)
    evolutions = detect_hypothesis_evolution(hypotheses)

    nodes = []
    edges = []

    for hyp in hypotheses:
        nodes.append({
            'id': hyp.id,
            'scene': hyp.scene,
            'episode': hyp.episode,
            'verbatim': hyp.verbatim[:100] + '...' if len(hyp.verbatim) > 100 else hyp.verbatim,
            'features': hyp.features,
            'outcome': hyp.outcome,
            'confidence': hyp.confidence,
        })

    for evolution in evolutions:
        instances = evolution.instances
        for i in range(len(instances) - 1):
            edges.append({
                'from': instances[i].id,
                'to': instances[i+1].id,
                'type': evolution.relationship_type,
            })

    return {
        'nodes': nodes,
        'edges': edges,
        'stats': {
            'total_hypotheses': len(hypotheses),
            'evolution_chains': len(evolutions),
            'scenes_covered': len(set(h.scene for h in hypotheses)),
        }
    }
