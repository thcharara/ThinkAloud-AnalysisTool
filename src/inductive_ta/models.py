"""
Data models for the Inductive Think-Aloud framework.

Implements the three-level unit structure:
- Turn (micro): single utterance/line
- Episode (meso): hypothesis pursuit run
- Scene (macro): full puzzle per participant
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# Tier A: Operations (mutually exclusive at turn level)
# ============================================================================

class Operation(str, Enum):
    ORIENT = "ORIENT"
    OBSERVE_DESCRIBE = "OBSERVE_DESCRIBE"
    INFERENCE = "INFERENCE"
    HYPOTHESIZE = "HYPOTHESIZE"
    TEST_SEEK_EVIDENCE = "TEST_SEEK_EVIDENCE"
    EVALUATE_REVISE = "EVALUATE_REVISE"
    META_COGNITION = "META_COGNITION"
    RESPONSE_ENTRY = "RESPONSE_ENTRY"


# ============================================================================
# Step Tags (micro-sequence labels)
# ============================================================================

class StepTag(str, Enum):
    STEP_OBS = "STEP_OBS"
    STEP_INFERENCE = "STEP_INFERENCE"
    STEP_HYP = "STEP_HYP"
    STEP_TEST_CONFIRM = "STEP_TEST_CONFIRM"
    STEP_TEST_DISCONFIRM = "STEP_TEST_DISCONFIRM"
    STEP_REVISE = "STEP_REVISE"
    STEP_COMMIT = "STEP_COMMIT"


# ============================================================================
# Tier B: Content (multi-label; co-occurs with Tier A)
# ============================================================================

# B3: Evidence Type
class EvidenceType(str, Enum):
    PositiveCases = "PositiveCases"
    NegativeCases = "NegativeCases"
    Mixed = "Mixed"


# B5: Confidence
class Confidence(str, Enum):
    Definite = "Definite"
    Hedged = "Hedged"
    Disavowal = "Disavowal"


# ============================================================================
# Tier C: Strategy (episode-level only)
# ============================================================================

class StrategyCode(str, Enum):
    SearchMode_featureBreadth = "SearchMode_featureBreadth"
    SearchMode_panelBreadth = "SearchMode_panelBreadth"
    SearchMode_featureDepth = "SearchMode_featureDepth"
    SearchMode_panelDepth = "SearchMode_panelDepth"
    HypMgmt_SingleTrack = "HypMgmt_SingleTrack"
    HypMgmt_Parallel = "HypMgmt_Parallel"
    HypMgmt_Elimination = "HypMgmt_Elimination"
    EvidencePolicy_ConfirmOnly = "EvidencePolicy_ConfirmOnly"
    EvidencePolicy_Contrastive = "EvidencePolicy_Contrastive"
    EvidencePolicy_Falsification = "EvidencePolicy_Falsification"
    Complexity_Atomic = "Complexity_Atomic"
    Complexity_Conjunctive = "Complexity_Conjunctive"
    Complexity_Relational = "Complexity_Relational"
    CrossScene_Transfer = "CrossScene_Transfer"
    CrossScene_Perseveration = "CrossScene_Perseveration"
    CrossScene_AdaptiveShift = "CrossScene_AdaptiveShift"


# ============================================================================
# Distance to Truth
# ============================================================================

class DistanceToTruth(str, Enum):
    ExactMatch = "ExactMatch"
    FamilyMatch_Partial = "FamilyMatch_Partial"
    FamilyMismatch = "FamilyMismatch"
    RuleFormMismatch = "RuleFormMismatch"


# ============================================================================
# Episode Outcome
# ============================================================================

class EpisodeOutcome(str, Enum):
    accepted = "accepted"
    revised = "revised"
    rejected = "rejected"
    pending = "pending"


# ============================================================================
# Turn Record (Micro-level) - ENHANCED
# ============================================================================

class Turn(BaseModel):
    """
    Smallest codeable unit: one line/utterance.
    Corresponds to one row in corpus_enriched.jsonl.
    """
    participant_id: str  # e.g., P01
    scene: int  # 1-5
    turn_index: int  # 0..N within scene
    tag: Optional[str] = None  # [READING], [THINKING], [TYPING], or None
    raw_text: str
    char_start: int  # offset in original transcript
    char_end: int

    # Codes
    A_operation: Optional[str] = None  # Exactly one from Operation enum
    B_content: List[str] = Field(default_factory=list)  # Any of B1-B6 codes
    step_tag: Optional[str] = None  # From StepTag enum

    # Metadata
    notes: str = ""
    auto_suggestions: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Episode Record (Meso-level)
# ============================================================================

class Episode(BaseModel):
    """
    A contiguous run pursuing one candidate hypothesis OR a reasoning chunk.
    Corresponds to one row in episodes.jsonl.
    """
    episode_id: str  # e.g., P07_S3_EP2
    participant_id: str
    scene: int
    episode_index: int  # 0..N within scene
    turn_span_start: int  # start turn index
    turn_span_end: int  # end turn index

    # Episode type (dual workflow)
    episode_type: str = "hypothesis_episode"  # hypothesis_episode | reasoning_chunk

    # For reasoning chunks
    chunk_type: Optional[str] = None  # exploratory_observation | hypothesis_flow | testing_sequence | evaluation_period
    chunk_description: str = ""

    # For hypothesis episodes (required when episode_type = hypothesis_episode)
    HypothesisVerbatim: str = ""
    FeatureBundle: List[str] = Field(default_factory=list)  # e.g., ["color=blue", "size=small"]
    EvidenceCited: Optional[str] = None  # PositiveCases|NegativeCases|Mixed
    Confidence: Optional[str] = None  # Definite|Hedged|Disavowal
    Outcome: Optional[str] = None  # accepted|revised|rejected|pending

    # Strategy codes (Tier C)
    StrategyCodes: List[str] = Field(default_factory=list)

    # Distance to truth
    DistanceToTruth: Optional[str] = None

    # Optional
    Notes: str = ""


# ============================================================================
# Scene Record (Macro-level)
# ============================================================================

class SceneData(BaseModel):
    """Full puzzle per participant."""
    participant_id: str
    scene: int  # 1-5

    # Performance metrics
    Correct: Optional[bool] = None
    TimeSeconds: Optional[float] = None
    NumGuesses: Optional[int] = None
    FinalAnswerText: str = ""

    # Turns and episodes
    turns: List[Turn] = Field(default_factory=list)
    episodes: List[Episode] = Field(default_factory=list)


# ============================================================================
# Ground Truth
# ============================================================================

class SceneKey(BaseModel):
    """Ground truth for one scene."""
    Scene: int
    TargetRuleType: str
    KeyFeatures: str  # semicolon-separated, e.g., "color=blue; size=small"
    ShortKey: str

    def get_feature_tokens(self) -> List[str]:
        """Parse KeyFeatures into list of tokens."""
        return [f.strip() for f in self.KeyFeatures.split(';')]


class SceneChunk(BaseModel):
    participant_id: str
    scene: int
    text: str


class ParseReport(BaseModel):
    participants: int
    scenes: int
    turns: int
    reading_turns: int
    thinking_turns: int
    typing_turns: int
