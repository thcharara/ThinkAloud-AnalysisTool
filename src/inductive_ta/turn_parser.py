"""
Turn parser for the Inductive Think-Aloud framework.

Segments transcripts into codeable turns (one line/utterance per turn).
Handles Scene headers and [READING]/[THINKING]/[TYPING] tags.
"""

import re
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .models import Turn, SceneData


class TurnParser:
    """
    Parse transcripts into turn-based units.

    Usage:
        parser = TurnParser(project_root="/path/to/project")
        scene_data = parser.parse_participant("P01")
    """

    def __init__(self, project_root: str | Path, config_path: Optional[str] = None):
        self.root = Path(project_root)

        # Load config directly
        config_file = self.root / (config_path or "config/config.yaml")
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # Scene header regex from config
        self.scene_regex = re.compile(
            self.config["markers"]["scene_header_regex"],
            re.IGNORECASE | re.MULTILINE
        )

        # Tag patterns: [READING], [THINKING], [TYPING]
        self.tag_pattern = re.compile(r'\[([A-Z]+)\]')

        # Transcript directory
        paths = self.config.get("paths", {})
        self.transcripts_dir = self.root / paths.get("transcripts_dir", "01_clean_transcripts")

    def parse_participant(self, participant_id: str) -> List[SceneData]:
        """
        Parse all scenes for a participant.

        Args:
            participant_id: e.g., "P01"

        Returns:
            List of SceneData objects (one per scene 1-5)
        """
        transcript_path = self.transcripts_dir / f"{participant_id}.txt"
        if not transcript_path.exists():
            raise FileNotFoundError(f"Transcript not found: {transcript_path}")

        with open(transcript_path, encoding="utf-8") as f:
            text = f.read()

        # Split into scenes
        scenes_dict = self._split_into_scenes(text, participant_id)

        # Parse each scene into turns
        scene_data_list = []
        for scene_num in sorted(scenes_dict.keys()):
            scene_text = scenes_dict[scene_num]
            turns = self._parse_scene_into_turns(participant_id, scene_num, scene_text)

            scene_data = SceneData(
                participant_id=participant_id,
                scene=scene_num,
                turns=turns
            )
            scene_data_list.append(scene_data)

        return scene_data_list

    def _split_into_scenes(self, text: str, participant_id: str) -> Dict[int, str]:
        """
        Split transcript text into scenes based on "Scene N:" headers.

        Returns:
            Dict mapping scene number (1-5) to scene text
        """
        scenes = {}
        current_scene = None
        scene_buffer = []

        for line in text.splitlines():
            # Check if line is a scene header
            match = self.scene_regex.match(line.strip())
            if match:
                # Save previous scene
                if current_scene is not None:
                    scenes[current_scene] = "\n".join(scene_buffer)

                # Start new scene
                current_scene = int(match.group("num"))
                scene_buffer = []
            else:
                # Accumulate lines for current scene
                if current_scene is not None:
                    scene_buffer.append(line)

        # Save last scene
        if current_scene is not None:
            scenes[current_scene] = "\n".join(scene_buffer)

        return scenes

    def _parse_scene_into_turns(
        self,
        participant_id: str,
        scene_num: int,
        scene_text: str
    ) -> List[Turn]:
        """
        Parse a scene's text into turns (one per line/utterance).

        Each non-empty line becomes one turn.
        Tags like [THINKING] are extracted and removed from raw_text.

        Args:
            participant_id: e.g., "P01"
            scene_num: 1-5
            scene_text: raw text for this scene

        Returns:
            List of Turn objects
        """
        turns = []
        char_offset = 0  # Track character position in original scene text

        for turn_index, line in enumerate(scene_text.splitlines()):
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                char_offset += len(line) + 1  # +1 for newline
                continue

            # Extract tags (e.g., [THINKING])
            tag = None
            tag_match = self.tag_pattern.search(line_stripped)
            if tag_match:
                tag = f"[{tag_match.group(1)}]"
                # Remove tag from text for display
                raw_text = self.tag_pattern.sub('', line_stripped).strip()
            else:
                raw_text = line_stripped

            # Calculate char positions
            char_start = char_offset
            char_end = char_offset + len(line)

            turn = Turn(
                participant_id=participant_id,
                scene=scene_num,
                turn_index=turn_index,
                tag=tag,
                raw_text=raw_text,
                char_start=char_start,
                char_end=char_end
            )

            turns.append(turn)
            char_offset = char_end + 1  # +1 for newline

        return turns

    def load_participant_scene(self, participant_id: str, scene: int) -> Optional[SceneData]:
        """
        Load a single scene for a participant.

        Args:
            participant_id: e.g., "P01"
            scene: 1-5

        Returns:
            SceneData or None if not found
        """
        all_scenes = self.parse_participant(participant_id)
        for scene_data in all_scenes:
            if scene_data.scene == scene:
                return scene_data
        return None

    def get_participant_ids(self) -> List[str]:
        """Get list of all participant IDs from transcript files."""
        transcript_files = sorted(self.transcripts_dir.glob("P*.txt"))
        return [f.stem for f in transcript_files]
