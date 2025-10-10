"""
Project loader and validator for the Inductive Think-Aloud framework.

Loads and validates:
- config/config.yaml
- codebook/codebook.yaml
- ground_truth/SceneKeys.yaml
- Optional: existing corpus_enriched.jsonl
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, validator
from .models import SceneKey


# ============================================================================
# Validation Result
# ============================================================================

class ValidationError(BaseModel):
    """Single validation error."""
    severity: str  # "error" | "warning"
    category: str  # "codebook" | "ground_truth" | "config" | "corpus"
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None

    def __str__(self) -> str:
        prefix = "❌ ERROR" if self.severity == "error" else "⚠️  WARNING"
        location = f" ({self.file_path}:{self.line_number})" if self.file_path and self.line_number else ""
        return f"{prefix} [{self.category}]{location}: {self.message}"


class ValidationResult(BaseModel):
    """Collection of validation errors/warnings."""
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)

    def add_error(self, category: str, message: str, file_path: Optional[str] = None, line_number: Optional[int] = None):
        self.errors.append(ValidationError(severity="error", category=category, message=message, file_path=file_path, line_number=line_number))

    def add_warning(self, category: str, message: str, file_path: Optional[str] = None, line_number: Optional[int] = None):
        self.warnings.append(ValidationError(severity="warning", category=category, message=message, file_path=file_path, line_number=line_number))

    def is_valid(self) -> bool:
        """Returns True if no blocking errors (warnings are ok)."""
        return len(self.errors) == 0

    def format_report(self) -> str:
        """Format validation report for display."""
        lines = []
        if self.errors:
            lines.append(f"Found {len(self.errors)} blocking error(s):\n")
            for err in self.errors:
                lines.append(f"  {err}")
        if self.warnings:
            lines.append(f"\nFound {len(self.warnings)} warning(s):\n")
            for warn in self.warnings:
                lines.append(f"  {warn}")
        if not self.errors and not self.warnings:
            lines.append("✅ All validations passed!")
        return "\n".join(lines)


# ============================================================================
# Codebook Structure
# ============================================================================

class CodebookSpec(BaseModel):
    """
    Parsed and validated codebook.yaml structure.

    Matches the three-tier + step-tags + episode_fields format.
    """
    meta: Dict[str, str]
    tiers: Dict[str, Any]
    step_tags: Dict[str, str]
    episode_fields: List[Dict[str, str]]
    ground_truth_tokens: List[str] = Field(default_factory=list)

    def get_tier_a_operations(self) -> Dict[str, str]:
        """Get Tier A operations with descriptions."""
        return self.tiers.get("A_Operations", {})

    def get_tier_b_content(self) -> Dict[str, Any]:
        """Get Tier B content categories (B1-B6)."""
        return self.tiers.get("B_Content", {})

    def get_tier_c_strategy(self) -> Dict[str, str]:
        """Get Tier C strategy codes."""
        return self.tiers.get("C_Strategy", {})

    def get_all_operation_codes(self) -> List[str]:
        """Get list of all Tier A operation codes."""
        return list(self.get_tier_a_operations().keys())

    def get_all_b_codes(self) -> List[str]:
        """Get list of all Tier B codes (flattened from B1-B6)."""
        codes = []
        b_content = self.get_tier_b_content()
        for category, items in b_content.items():
            if isinstance(items, dict):
                codes.extend(items.keys())
        return codes

    def get_all_strategy_codes(self) -> List[str]:
        """Get list of all Tier C strategy codes."""
        return list(self.get_tier_c_strategy().keys())

    def get_all_step_tags(self) -> List[str]:
        """Get list of all step-tag codes."""
        return list(self.step_tags.keys())


# ============================================================================
# Config Structure
# ============================================================================

class ConfigSpec(BaseModel):
    """Parsed config.yaml structure."""
    paths: Dict[str, str]
    scenes: List[int]
    markers: Dict[str, Any]
    normalize: Optional[Dict[str, bool]] = None


# ============================================================================
# Project Loader
# ============================================================================

class ProjectLoader:
    """
    Load and validate project files with blocking validation.

    Usage:
        loader = ProjectLoader(project_root="/path/to/project")
        validation = loader.validate_all()

        if validation.is_valid():
            codebook = loader.load_codebook()
            scene_keys = loader.load_scene_keys()
            config = loader.load_config()
        else:
            print(validation.format_report())
    """

    def __init__(self, project_root: str | Path, config_path: Optional[str] = None):
        self.root = Path(project_root)
        self.codebook_path = self.root / "codebook" / "codebook.yaml"
        self.scene_keys_path = self.root / "ground_truth" / "SceneKeys.yaml"
        self.config_path = self.root / (config_path or "config/config.yaml")

        # Load config to get exports_dir
        if self.config_path.exists():
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
                exports_dir = config.get('paths', {}).get('exports_dir', 'exports')
                self.corpus_path = self.root / exports_dir / "corpus_enriched.jsonl"
        else:
            self.corpus_path = self.root / "exports" / "corpus_enriched.jsonl"

    def validate_all(self) -> ValidationResult:
        """
        Run all validations and return blocking result.

        Returns:
            ValidationResult with errors (blocking) and warnings (non-blocking)
        """
        result = ValidationResult()

        # Validate file existence
        if not self.codebook_path.exists():
            result.add_error("codebook", f"Codebook file not found: {self.codebook_path}")
        if not self.scene_keys_path.exists():
            result.add_error("ground_truth", f"SceneKeys file not found: {self.scene_keys_path}")
        if not self.config_path.exists():
            result.add_error("config", f"Config file not found: {self.config_path}")

        # If files don't exist, stop here
        if not result.is_valid():
            return result

        # Validate codebook
        self._validate_codebook(result)

        # Validate scene keys
        self._validate_scene_keys(result)

        # Validate config
        self._validate_config(result)

        return result

    def _validate_codebook(self, result: ValidationResult):
        """Validate codebook.yaml structure and content."""
        try:
            with open(self.codebook_path) as f:
                data = yaml.safe_load(f)

            # Check required top-level keys
            required_keys = ["meta", "tiers", "step_tags", "episode_fields"]
            for key in required_keys:
                if key not in data:
                    result.add_error("codebook", f"Missing required key: {key}", str(self.codebook_path))

            # Check Tier A
            if "tiers" in data and "A_Operations" in data["tiers"]:
                ops = data["tiers"]["A_Operations"]
                if not isinstance(ops, dict) or len(ops) == 0:
                    result.add_error("codebook", "Tier A_Operations must be a non-empty dict", str(self.codebook_path))

                # Check for duplicate keys (shouldn't happen with YAML, but check anyway)
                if len(ops) != len(set(ops.keys())):
                    result.add_error("codebook", "Duplicate operation codes in Tier A", str(self.codebook_path))

                # Check for illegal characters in keys
                for code in ops.keys():
                    if not all(c.isalnum() or c == '_' for c in code):
                        result.add_error("codebook", f"Illegal characters in operation code: {code}", str(self.codebook_path))
            else:
                result.add_error("codebook", "Missing Tier A_Operations", str(self.codebook_path))

            # Check Tier B
            if "tiers" in data and "B_Content" in data["tiers"]:
                b_content = data["tiers"]["B_Content"]
                if not isinstance(b_content, dict):
                    result.add_error("codebook", "Tier B_Content must be a dict", str(self.codebook_path))

                # Expected B categories
                expected_b = ["B1_FeatureFamily", "B2_Polarity", "B3_EvidenceType", "B4_Abstraction", "B5_Confidence", "B6_ErrorType"]
                for category in expected_b:
                    if category not in b_content:
                        result.add_warning("codebook", f"Missing Tier B category: {category}", str(self.codebook_path))
            else:
                result.add_error("codebook", "Missing Tier B_Content", str(self.codebook_path))

            # Check Tier C
            if "tiers" in data and "C_Strategy" in data["tiers"]:
                strat = data["tiers"]["C_Strategy"]
                if not isinstance(strat, dict) or len(strat) == 0:
                    result.add_warning("codebook", "Tier C_Strategy is empty or not a dict", str(self.codebook_path))
            else:
                result.add_error("codebook", "Missing Tier C_Strategy", str(self.codebook_path))

            # Check step_tags
            if "step_tags" in data:
                if not isinstance(data["step_tags"], dict) or len(data["step_tags"]) == 0:
                    result.add_warning("codebook", "step_tags is empty or not a dict", str(self.codebook_path))
            else:
                result.add_error("codebook", "Missing step_tags", str(self.codebook_path))

            # Check episode_fields
            if "episode_fields" in data:
                if not isinstance(data["episode_fields"], list) or len(data["episode_fields"]) == 0:
                    result.add_error("codebook", "episode_fields must be a non-empty list", str(self.codebook_path))

                # Check required episode fields
                required_ep_fields = ["HypothesisVerbatim", "FeatureBundle", "EvidenceCited", "Confidence", "Outcome"]
                field_names = [f.get("name") for f in data["episode_fields"]]
                for req in required_ep_fields:
                    if req not in field_names:
                        result.add_error("codebook", f"Missing required episode field: {req}", str(self.codebook_path))

        except yaml.YAMLError as e:
            result.add_error("codebook", f"YAML parse error: {e}", str(self.codebook_path))
        except Exception as e:
            result.add_error("codebook", f"Unexpected error: {e}", str(self.codebook_path))

    def _validate_scene_keys(self, result: ValidationResult):
        """Validate SceneKeys.yaml structure and content."""
        try:
            with open(self.scene_keys_path) as f:
                data = yaml.safe_load(f)

            if not isinstance(data, list):
                result.add_error("ground_truth", "SceneKeys must be a list of scene definitions", str(self.scene_keys_path))
                return

            # Check for exactly 5 scenes (1-5)
            scenes = [item.get("Scene") for item in data if "Scene" in item]
            expected_scenes = [1, 2, 3, 4, 5]

            if sorted(scenes) != expected_scenes:
                result.add_error("ground_truth", f"Expected scenes 1-5, got: {sorted(scenes)}", str(self.scene_keys_path))

            # Check required fields per scene
            required_fields = ["Scene", "TargetRuleType", "KeyFeatures", "ShortKey"]
            for i, scene_def in enumerate(data):
                for field in required_fields:
                    if field not in scene_def or not scene_def[field]:
                        result.add_error("ground_truth", f"Scene {i+1}: missing or empty field '{field}'", str(self.scene_keys_path))

        except yaml.YAMLError as e:
            result.add_error("ground_truth", f"YAML parse error: {e}", str(self.scene_keys_path))
        except Exception as e:
            result.add_error("ground_truth", f"Unexpected error: {e}", str(self.scene_keys_path))

    def _validate_config(self, result: ValidationResult):
        """Validate config.yaml structure."""
        try:
            with open(self.config_path) as f:
                data = yaml.safe_load(f)

            # Check required keys
            required_keys = ["paths", "scenes", "markers"]
            for key in required_keys:
                if key not in data:
                    result.add_error("config", f"Missing required key: {key}", str(self.config_path))

            # Check scenes list
            if "scenes" in data:
                if not isinstance(data["scenes"], list) or data["scenes"] != [1, 2, 3, 4, 5]:
                    result.add_error("config", "scenes must be [1, 2, 3, 4, 5]", str(self.config_path))

            # Check paths
            if "paths" in data:
                required_paths = ["transcripts_dir", "exports_dir"]
                for path_key in required_paths:
                    if path_key not in data["paths"]:
                        result.add_warning("config", f"Missing path key: {path_key}", str(self.config_path))

        except yaml.YAMLError as e:
            result.add_error("config", f"YAML parse error: {e}", str(self.config_path))
        except Exception as e:
            result.add_error("config", f"Unexpected error: {e}", str(self.config_path))

    def load_codebook(self) -> CodebookSpec:
        """Load codebook.yaml (after validation passes)."""
        with open(self.codebook_path) as f:
            data = yaml.safe_load(f)
        return CodebookSpec(**data)

    def load_scene_keys(self) -> List[SceneKey]:
        """Load SceneKeys.yaml (after validation passes)."""
        with open(self.scene_keys_path) as f:
            data = yaml.safe_load(f)
        return [SceneKey(**scene) for scene in data]

    def load_config(self) -> ConfigSpec:
        """Load config.yaml (after validation passes)."""
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        return ConfigSpec(**data)

    def get_scene_key(self, scene: int) -> Optional[SceneKey]:
        """Get ground truth for a specific scene."""
        scene_keys = self.load_scene_keys()
        for key in scene_keys:
            if key.Scene == scene:
                return key
        return None
