"""
JSONL export functions for the Inductive Think-Aloud framework.

Exports:
- corpus_enriched.jsonl (turn records with codes)
- episodes.jsonl (episode records)
- CHANGELOG.jsonl (audit trail)
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime, timezone
from .models import Turn, Episode


class JSONLExporter:
    """
    Export turn and episode data to JSONL format.

    Usage:
        exporter = JSONLExporter(exports_dir="05_exports")
        exporter.export_turns(turns)
        exporter.export_episodes(episodes)
    """

    def __init__(self, exports_dir: str | Path):
        self.exports_dir = Path(exports_dir)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        self.corpus_path = self.exports_dir / "corpus_enriched.jsonl"
        self.episodes_path = self.exports_dir / "episodes.jsonl"
        self.changelog_path = self.exports_dir / "CHANGELOG.jsonl"

    def export_turns(self, turns: List[Turn], mode: str = 'w') -> None:
        """
        Export turns to corpus_enriched.jsonl.

        Args:
            turns: List of Turn objects
            mode: 'w' to overwrite, 'a' to append
        """
        with open(self.corpus_path, mode, encoding='utf-8') as f:
            for turn in turns:
                # Convert to dict and write as JSON line
                turn_dict = turn.model_dump()
                f.write(json.dumps(turn_dict, ensure_ascii=False) + '\n')

    def export_episodes(self, episodes: List[Episode], mode: str = 'w') -> None:
        """
        Export episodes to episodes.jsonl.

        Args:
            episodes: List of Episode objects
            mode: 'w' to overwrite, 'a' to append
        """
        with open(self.episodes_path, mode, encoding='utf-8') as f:
            for episode in episodes:
                # Convert to dict and write as JSON line
                episode_dict = episode.model_dump()
                f.write(json.dumps(episode_dict, ensure_ascii=False) + '\n')

    def log_change(
        self,
        participant_id: str,
        scene: int,
        action_type: str,
        before: dict = None,
        after: dict = None,
        notes: str = ""
    ) -> None:
        """
        Append a change entry to CHANGELOG.jsonl.

        Args:
            participant_id: e.g., "P01"
            scene: 1-5
            action_type: "apply_code", "remove_code", "create_episode", "update_episode", etc.
            before: Payload before change
            after: Payload after change
            notes: Optional notes
        """
        change_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "participant_id": participant_id,
            "scene": scene,
            "action_type": action_type,
            "before": before or {},
            "after": after or {},
            "notes": notes
        }

        with open(self.changelog_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(change_entry, ensure_ascii=False) + '\n')

    def load_turns(self) -> List[Turn]:
        """
        Load all turns from corpus_enriched.jsonl.

        Returns:
            List of Turn objects
        """
        if not self.corpus_path.exists():
            return []

        turns = []
        with open(self.corpus_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    turn_dict = json.loads(raw)
                except json.JSONDecodeError:
                    # Skip corrupt line; keep file usable
                    continue
                turns.append(Turn(**turn_dict))
        return turns

    def load_episodes(self) -> List[Episode]:
        """
        Load all episodes from episodes.jsonl.

        Returns:
            List of Episode objects
        """
        if not self.episodes_path.exists():
            return []

        episodes = []
        with open(self.episodes_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    episode_dict = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                episodes.append(Episode(**episode_dict))
        return episodes

    def load_turns_for_participant_scene(self, participant_id: str, scene: int) -> List[Turn]:
        """
        Load turns for a specific participant and scene.

        Args:
            participant_id: e.g., "P01"
            scene: 1-5

        Returns:
            List of Turn objects
        """
        all_turns = self.load_turns()
        return [
            t for t in all_turns
            if t.participant_id == participant_id and t.scene == scene
        ]

    def load_episodes_for_participant_scene(self, participant_id: str, scene: int) -> List[Episode]:
        """
        Load episodes for a specific participant and scene.

        Args:
            participant_id: e.g., "P01"
            scene: 1-5

        Returns:
            List of Episode objects
        """
        all_episodes = self.load_episodes()
        return [
            e for e in all_episodes
            if e.participant_id == participant_id and e.scene == scene
        ]

    def export_participant_scene(
        self,
        participant_id: str,
        scene: int,
        turns: List[Turn],
        episodes: List[Episode]
    ) -> None:
        """
        Export turns and episodes for a specific participant/scene.

        This is an incremental export: it updates the JSONL files
        by replacing records for this participant/scene.

        Args:
            participant_id: e.g., "P01"
            scene: 1-5
            turns: Turns to export
            episodes: Episodes to export
        """
        # Load existing data
        all_turns = self.load_turns()
        all_episodes = self.load_episodes()

        # Remove existing records for this participant/scene
        all_turns = [
            t for t in all_turns
            if not (t.participant_id == participant_id and t.scene == scene)
        ]
        all_episodes = [
            e for e in all_episodes
            if not (e.participant_id == participant_id and e.scene == scene)
        ]

        # Add new records
        all_turns.extend(turns)
        all_episodes.extend(episodes)

        # Write back
        self.export_turns(all_turns, mode='w')
        self.export_episodes(all_episodes, mode='w')

    def export_structured_json(
        self,
        participant_id: str,
        scene: int,
        turns: List[Turn],
        codebook: dict = None
    ) -> None:
        """
        Export a structured JSON file per participant/scene with full code labels.

        Creates: {exports_dir}/structured_json/{participant_id}_scene{scene}_coded.json

        Format similar to:
        {
            "participant_id": "P01",
            "scene": "scene1",
            "turns": [
                {
                    "id": 1,
                    "span": "Alright. Uh, let's see, let's see.",
                    "open_code": "Orientation",
                    "summary": "orients themselves to the task",
                    "tier_a_operation": "ORIENT",
                    "tier_b_content": ["Confidence_Hedged"],
                    "step_tag": "STEP_OBS"
                },
                ...
            ]
        }

        Args:
            participant_id: e.g., "P01"
            scene: 1-5
            turns: List of Turn objects
            codebook: Optional codebook dict for label lookups
        """
        # Keep structured JSON inside the configured exports directory
        annotations_dir = self.exports_dir / "structured_json"
        annotations_dir.mkdir(parents=True, exist_ok=True)

        # Build structured data
        structured_turns = []
        for i, turn in enumerate(turns, start=1):
            turn_data = {
                "id": turn.turn_index if turn.turn_index is not None else i,
                "span": turn.raw_text,
                "open_code": self._get_operation_label(turn.A_operation),
                "summary": self._generate_turn_summary(turn),
                "tier_a_operation": turn.A_operation,
                "tier_b_content": turn.B_content or [],
                "step_tag": turn.step_tag,
                "tag": turn.tag  # [READING], [THINKING], [TYPING]
            }
            structured_turns.append(turn_data)

        output = {
            "participant_id": participant_id,
            "scene": f"scene{scene}",
            "title": f"scene{scene}",
            "turns": structured_turns
        }

        # Write JSON file
        output_path = annotations_dir / f"{participant_id}_scene{scene}_coded.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)

    def _get_operation_label(self, operation_code: str) -> str:
        """Convert operation code to human-readable label."""
        if not operation_code:
            return ""

        labels = {
            "ORIENT": "Orientation",
            "OBSERVE_DESCRIBE": "Observation",
            "INFERENCE": "Inference",
            "COMPARE_CONTRAST": "Comparison",  # Legacy support
            "HYPOTHESIZE": "Hypothesis",
            "TEST_SEEK_EVIDENCE": "Testing",
            "EVALUATE_REVISE": "Evaluation",
            "META_COGNITION": "Meta-cognition",
            "RESPONSE_ENTRY": "Response"
        }
        return labels.get(operation_code, operation_code)

    def _generate_turn_summary(self, turn: Turn) -> str:
        """Generate a brief summary of the turn based on codes."""
        if not turn.A_operation:
            return ""

        summaries = {
            "ORIENT": "orients themselves to the task",
            "OBSERVE_DESCRIBE": "describes observations",
            "INFERENCE": "seeks patterns/compares",
            "COMPARE_CONTRAST": "compares panels",  # Legacy support
            "HYPOTHESIZE": "proposes hypothesis",
            "TEST_SEEK_EVIDENCE": "tests hypothesis",
            "EVALUATE_REVISE": "evaluates/revises",
            "META_COGNITION": "reflects on process",
            "RESPONSE_ENTRY": "enters response"
        }

        base_summary = summaries.get(turn.A_operation, "")

        # Add feature mentions if relevant
        if turn.B_content and turn.A_operation in ["HYPOTHESIZE", "TEST_SEEK_EVIDENCE"]:
            features = [c.split('_')[1] if '_' in c else c for c in turn.B_content[:2]]
            if features:
                base_summary += f" ({', '.join(features).lower()})"

        return base_summary


def export_to_csv_matrices(
    turns: List[Turn],
    episodes: List[Episode],
    output_dir: str | Path
) -> None:
    """
    Export matrix CSVs for analysis.

    Creates:
    - feature_attention_by_scene.csv (Scene × FeatureFamily counts in HYPOTHESIZE turns)
    - evidence_policy_by_outcome.csv (EvidencePolicy × Outcome counts)

    Args:
        turns: All turns
        episodes: All episodes
        output_dir: Directory to write CSVs
    """
    import csv
    from collections import Counter

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Scene × FeatureFamily matrix (HYPOTHESIZE turns only)
    feature_counts = Counter()
    for turn in turns:
        if turn.A_operation == "HYPOTHESIZE" and turn.B_content:
            for code in turn.B_content:
                # Extract feature family codes (B1_FeatureFamily codes start with COLOR_, SIZE_, etc.)
                if any(code.startswith(prefix) for prefix in ["COLOR_", "SIZE_", "ORIENTATION_", "POSITIONREL_", "COUNT_"]):
                    feature_counts[(turn.scene, code)] += 1

    # Write feature attention matrix
    feature_matrix_path = output_dir / "feature_attention_by_scene.csv"
    with open(feature_matrix_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Get all unique features and scenes
        all_features = sorted(set(code for (_, code) in feature_counts.keys()))
        all_scenes = sorted(set(scene for (scene, _) in feature_counts.keys()))

        # Header
        writer.writerow(['Scene'] + all_features)

        # Rows
        for scene in all_scenes:
            row = [scene]
            for feature in all_features:
                row.append(feature_counts.get((scene, feature), 0))
            writer.writerow(row)

    # EvidencePolicy × Outcome matrix
    policy_outcome_counts = Counter()
    for episode in episodes:
        # Extract evidence policy from StrategyCodes
        evidence_policy = None
        for code in episode.StrategyCodes:
            if code.startswith("EvidencePolicy_"):
                evidence_policy = code
                break

        if evidence_policy and episode.Outcome:
            policy_outcome_counts[(evidence_policy, episode.Outcome)] += 1

    # Write evidence policy matrix
    policy_matrix_path = output_dir / "evidence_policy_by_outcome.csv"
    with open(policy_matrix_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Get all unique policies and outcomes
        all_policies = sorted(set(policy for (policy, _) in policy_outcome_counts.keys()))
        all_outcomes = sorted(set(outcome for (_, outcome) in policy_outcome_counts.keys()))

        # Header
        writer.writerow(['EvidencePolicy'] + all_outcomes)

        # Rows
        for policy in all_policies:
            row = [policy]
            for outcome in all_outcomes:
                row.append(policy_outcome_counts.get((policy, outcome), 0))
            writer.writerow(row)
