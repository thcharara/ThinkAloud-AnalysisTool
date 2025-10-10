from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class MicroUnit(BaseModel):
    participant_id: str
    scene: int
    tag: str  # Tier A operation code
    text: str
    ep: Optional[str] = None
    # Tier B (all optional)
    feature: Optional[str] = None  # space/comma separated feature tokens
    polarity: Optional[str] = None
    evidence: Optional[str] = None
    abstraction: Optional[str] = None
    confidence: Optional[str] = None
    error: Optional[str] = None
    truth_alignment: Optional[str] = None
    # Provenance
    file: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class Episode(BaseModel):
    participant: str
    scene: int
    episode: str
    strategy_search_mode: Optional[str] = None
    strategy_hypothesis_management: Optional[str] = None
    strategy_evidence_policy: Optional[str] = None
    complexity: Optional[str] = None
    cross_scene_shift: Optional[str] = None
    hypothesis_verbatim: Optional[str] = None
    feature_bundle: Optional[str] = None
    evidence_cited: Optional[str] = None
    confidence: Optional[str] = None
    outcome: Optional[str] = None
    summary: Optional[str] = None


class Sequence(BaseModel):
    participant: str
    scene: int
    sequence: List[str]

