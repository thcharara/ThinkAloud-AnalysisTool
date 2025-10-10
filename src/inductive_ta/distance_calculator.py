"""
Distance-to-Truth calculator for the Inductive Think-Aloud framework.

Compares episode hypothesis (FeatureBundle) against scene ground truth (SceneKey)
and classifies at feature-family granularity.
"""

from typing import List, Set
from .models import Episode, SceneKey, DistanceToTruth


class DistanceCalculator:
    """
    Calculate distance-to-truth for episodes.

    Categories:
    - ExactMatch: all required features present
    - FamilyMatch_Partial: at least one correct feature family, but missing key dimensions
    - FamilyMismatch: no overlap with required features
    - RuleFormMismatch: relational vs atomic mismatch
    """

    def __init__(self, scene_key: SceneKey):
        """
        Initialize calculator with ground truth for a scene.

        Args:
            scene_key: SceneKey object with KeyFeatures (e.g., "color=blue; size=small")
        """
        self.scene_key = scene_key
        self.ground_truth_tokens = scene_key.get_feature_tokens()

        # Parse ground truth into feature families
        self.ground_truth_families = self._extract_feature_families(self.ground_truth_tokens)

    def _extract_feature_families(self, feature_bundle: List[str]) -> Set[str]:
        """
        Extract feature families from a feature bundle.

        Examples:
            ["color=blue", "size=small"] -> {"color", "size"}
            ["relation=stacked", "color=different"] -> {"relation", "color"}

        Args:
            feature_bundle: List of "family=value" tokens

        Returns:
            Set of family names
        """
        families = set()
        for token in feature_bundle:
            if '=' in token:
                family, _ = token.split('=', 1)
                families.add(family.strip().lower())
        return families

    def _extract_feature_tokens(self, feature_bundle: List[str]) -> Set[str]:
        """
        Normalize feature bundle to lowercase tokens.

        Args:
            feature_bundle: List of "family=value" tokens

        Returns:
            Set of normalized tokens
        """
        return {token.strip().lower() for token in feature_bundle}

    def _is_relational(self, feature_bundle: List[str]) -> bool:
        """
        Check if feature bundle describes a relational rule.

        Relational indicators: "relation=", "position=", "stacked", "above", "below", "adjacent"

        Args:
            feature_bundle: List of "family=value" tokens

        Returns:
            True if relational
        """
        relational_keywords = ["relation", "position", "stacked", "above", "below", "adjacent"]
        for token in feature_bundle:
            token_lower = token.lower()
            if any(keyword in token_lower for keyword in relational_keywords):
                return True
        return False

    def calculate(self, episode: Episode) -> DistanceToTruth:
        """
        Calculate distance-to-truth for an episode.

        Args:
            episode: Episode with FeatureBundle

        Returns:
            DistanceToTruth category
        """
        if not episode.FeatureBundle or len(episode.FeatureBundle) == 0:
            # No features mentioned -> can't match
            return DistanceToTruth.FamilyMismatch

        # Extract families and tokens from hypothesis
        hypothesis_families = self._extract_feature_families(episode.FeatureBundle)
        hypothesis_tokens = self._extract_feature_tokens(episode.FeatureBundle)
        ground_tokens = self._extract_feature_tokens(self.ground_truth_tokens)

        # Check for rule form mismatch (relational vs atomic)
        ground_is_relational = self._is_relational(self.ground_truth_tokens)
        hyp_is_relational = self._is_relational(episode.FeatureBundle)

        if ground_is_relational != hyp_is_relational:
            return DistanceToTruth.RuleFormMismatch

        # Check for exact match (all ground truth tokens present)
        if ground_tokens.issubset(hypothesis_tokens):
            return DistanceToTruth.ExactMatch

        # Check for family overlap
        family_overlap = self.ground_truth_families.intersection(hypothesis_families)

        if len(family_overlap) > 0:
            # At least one correct family mentioned, but not all features
            return DistanceToTruth.FamilyMatch_Partial
        else:
            # No correct families mentioned
            return DistanceToTruth.FamilyMismatch

    def calculate_and_set(self, episode: Episode) -> DistanceToTruth:
        """
        Calculate distance and set it on the episode.

        Args:
            episode: Episode to update

        Returns:
            DistanceToTruth category (also sets episode.DistanceToTruth)
        """
        distance = self.calculate(episode)
        episode.DistanceToTruth = distance.value
        return distance

    def explain(self, episode: Episode) -> str:
        """
        Generate human-readable explanation of distance calculation.

        Args:
            episode: Episode with FeatureBundle

        Returns:
            Explanation string
        """
        distance = self.calculate(episode)

        hypothesis_families = self._extract_feature_families(episode.FeatureBundle)
        hypothesis_tokens = self._extract_feature_tokens(episode.FeatureBundle)
        ground_tokens = self._extract_feature_tokens(self.ground_truth_tokens)

        overlap = hypothesis_families.intersection(self.ground_truth_families)
        missing = self.ground_truth_families - hypothesis_families

        if distance == DistanceToTruth.ExactMatch:
            return f"✅ Exact match: all required features present ({', '.join(ground_tokens)})"

        elif distance == DistanceToTruth.FamilyMatch_Partial:
            return (
                f"⚠️  Partial match: mentions correct families ({', '.join(overlap)}) "
                f"but missing key dimensions ({', '.join(missing)})"
            )

        elif distance == DistanceToTruth.FamilyMismatch:
            return (
                f"❌ No overlap: hypothesis focuses on {', '.join(hypothesis_families)} "
                f"but ground truth requires {', '.join(self.ground_truth_families)}"
            )

        elif distance == DistanceToTruth.RuleFormMismatch:
            ground_is_relational = self._is_relational(self.ground_truth_tokens)
            if ground_is_relational:
                return "❌ Rule form mismatch: ground truth is relational, but hypothesis is atomic/feature-based"
            else:
                return "❌ Rule form mismatch: ground truth is atomic/feature-based, but hypothesis is relational"

        return str(distance.value)


def calculate_distance_for_scene(episodes: List[Episode], scene_key: SceneKey) -> List[Episode]:
    """
    Convenience function to calculate distance for all episodes in a scene.

    Args:
        episodes: List of episodes for a scene
        scene_key: Ground truth for the scene

    Returns:
        Updated episodes with DistanceToTruth set
    """
    calculator = DistanceCalculator(scene_key)
    for episode in episodes:
        calculator.calculate_and_set(episode)
    return episodes
