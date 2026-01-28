"""
Scoring and ranking system for analyzed issues.

Takes Claude's analysis and calculates a match score based on:
- How well difficulty matches user's skill level
- How well time estimate matches user's availability
- Repository health
- Issue clarity
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from .config import (
    DIFFICULTY_MATCH_WEIGHT,
    TIME_MATCH_WEIGHT,
    REPO_HEALTH_WEIGHT,
    ISSUE_CLARITY_WEIGHT
)
from .github_client import IssueData, RepoHealth
from .analyzer import IssueAnalysis


@dataclass
class ScoreComponent:
    """
    A single component of the overall match score.

    This provides transparency into how each factor contributes to the final score.
    """
    name: str                    # e.g., "difficulty", "time"
    score: float                 # 0-1 score for this component
    weight: float                # How much this contributes to total (e.g., 0.40)
    weighted_score: float        # score * weight
    confidence: str              # high/medium/low (from LLM or heuristic)
    reasoning: str               # Why this score was given
    match_description: str       # Human-readable match quality


@dataclass
class ScoredIssue:
    """An issue with its analysis and calculated match score."""
    issue: IssueData
    analysis: IssueAnalysis
    score: float                           # Overall score (0-1)
    score_breakdown: dict                  # Legacy: simple scores dict
    score_components: List[ScoreComponent] # New: detailed breakdown
    overall_confidence: str                # Combined confidence level


class IssueScorer:
    """
    Calculates match scores for analyzed issues.

    Scoring weights (from config.py):
    - Difficulty match: 40%
    - Time match: 30%
    - Repo health: 15%
    - Issue clarity: 15%
    """

    def __init__(self):
        # Ordered lists for calculating "distance" between levels
        self.difficulty_order = ["beginner", "intermediate", "advanced"]
        self.time_order = ["quick_win", "half_day", "full_day", "weekend", "deep_dive"]

    def calculate_difficulty_score(self, actual: str, preferred: str) -> float:
        """
        Score how well the issue difficulty matches user preference.

        Perfect match = 1.0
        One level off = 0.6
        Two levels off = 0.2
        """
        try:
            actual_idx = self.difficulty_order.index(actual.lower())
            preferred_idx = self.difficulty_order.index(preferred.lower())
        except ValueError:
            return 0.5  # Unknown difficulty, neutral score

        diff = abs(actual_idx - preferred_idx)

        if diff == 0:
            return 1.0
        elif diff == 1:
            return 0.6
        else:
            return 0.2

    def calculate_time_score(self, actual: str, preferred: str) -> float:
        """
        Score how well the time estimate matches user availability.

        Perfect match = 1.0
        One level off = 0.7
        Two levels off = 0.4
        More = 0.1
        """
        try:
            actual_idx = self.time_order.index(actual.lower())
            preferred_idx = self.time_order.index(preferred.lower())
        except ValueError:
            return 0.5  # Unknown time, neutral score

        diff = abs(actual_idx - preferred_idx)

        if diff == 0:
            return 1.0
        elif diff == 1:
            return 0.7
        elif diff == 2:
            return 0.4
        else:
            return 0.1

    def calculate_health_score(self, repo_health: RepoHealth = None) -> float:
        """
        Score repository health.

        For MVP, we use a simple heuristic based on available data.
        """
        if repo_health is None:
            return 0.7  # Default neutral-positive score

        score = 0.0

        if repo_health.is_healthy:
            score += 0.5

        if repo_health.has_contributing_guide:
            score += 0.3

        # Bonus for very active repos
        if repo_health.days_since_update < 30:
            score += 0.2

        return min(score, 1.0)

    def calculate_clarity_score(self, clarity: int) -> float:
        """
        Normalize clarity score (1-10) to 0-1 range.
        """
        return max(0, min(clarity, 10)) / 10.0

    def _get_match_description(self, score: float, component: str) -> str:
        """Generate human-readable match description."""
        if score >= 0.9:
            return "Excellent match"
        elif score >= 0.7:
            return "Good match"
        elif score >= 0.5:
            return "Partial match"
        elif score >= 0.3:
            return "Weak match"
        else:
            return "Poor match"

    def _calculate_overall_confidence(self, components: List[ScoreComponent]) -> str:
        """
        Calculate overall confidence from component confidences.

        Logic:
        - If any component has LOW confidence, overall is at most MEDIUM
        - If all have HIGH confidence, overall is HIGH
        - Otherwise MEDIUM
        """
        confidences = [c.confidence.lower() for c in components]

        if "low" in confidences:
            return "low"
        elif all(c == "high" for c in confidences):
            return "high"
        else:
            return "medium"

    def score_issue(
        self,
        issue: IssueData,
        analysis: IssueAnalysis,
        user_skill: str,
        user_time: str,
        repo_health: RepoHealth = None
    ) -> ScoredIssue:
        """
        Calculate overall match score for an issue.

        Returns a ScoredIssue with the total score, breakdown, and detailed components.
        """

        components = []

        # =====================================================================
        # DIFFICULTY COMPONENT
        # =====================================================================
        difficulty_score = self.calculate_difficulty_score(
            analysis.difficulty,
            user_skill
        )

        # Generate reasoning for difficulty match
        if difficulty_score == 1.0:
            diff_reasoning = f"Perfect match: issue is {analysis.difficulty}, you selected {user_skill}"
        elif difficulty_score >= 0.6:
            diff_reasoning = f"Close match: issue is {analysis.difficulty}, you selected {user_skill}"
        else:
            diff_reasoning = f"Mismatch: issue is {analysis.difficulty}, but you selected {user_skill}"

        # Get confidence from LLM analysis (with fallback)
        diff_confidence = getattr(analysis, 'difficulty_confidence', 'medium') or 'medium'

        components.append(ScoreComponent(
            name="Difficulty Match",
            score=difficulty_score,
            weight=DIFFICULTY_MATCH_WEIGHT,
            weighted_score=difficulty_score * DIFFICULTY_MATCH_WEIGHT,
            confidence=diff_confidence,
            reasoning=diff_reasoning,
            match_description=self._get_match_description(difficulty_score, "difficulty")
        ))

        # =====================================================================
        # TIME COMPONENT
        # =====================================================================
        time_score = self.calculate_time_score(
            analysis.estimated_time,
            user_time
        )

        # Generate reasoning for time match
        time_display = analysis.estimated_time.replace("_", " ")
        user_time_display = user_time.replace("_", " ")

        if time_score == 1.0:
            time_reasoning = f"Perfect match: estimated {time_display}, you have {user_time_display}"
        elif time_score >= 0.7:
            time_reasoning = f"Close match: estimated {time_display}, you have {user_time_display}"
        else:
            time_reasoning = f"Time mismatch: estimated {time_display}, but you have {user_time_display}"

        # Get confidence from LLM analysis (with fallback)
        time_confidence = getattr(analysis, 'time_confidence', 'medium') or 'medium'

        components.append(ScoreComponent(
            name="Time Match",
            score=time_score,
            weight=TIME_MATCH_WEIGHT,
            weighted_score=time_score * TIME_MATCH_WEIGHT,
            confidence=time_confidence,
            reasoning=time_reasoning,
            match_description=self._get_match_description(time_score, "time")
        ))

        # =====================================================================
        # REPO HEALTH COMPONENT
        # =====================================================================
        health_score = self.calculate_health_score(repo_health)

        # Generate reasoning for health
        if repo_health:
            health_parts = []
            if repo_health.days_since_update < 30:
                health_parts.append("very active")
            elif repo_health.days_since_update < 90:
                health_parts.append("recently updated")
            else:
                health_parts.append(f"last updated {repo_health.days_since_update} days ago")

            if repo_health.has_contributing_guide:
                health_parts.append("has CONTRIBUTING.md")

            health_reasoning = "Repository: " + ", ".join(health_parts)
            health_confidence = "high"  # We have actual data
        else:
            health_reasoning = "Repository health not checked (using default score)"
            health_confidence = "low"

        components.append(ScoreComponent(
            name="Repo Health",
            score=health_score,
            weight=REPO_HEALTH_WEIGHT,
            weighted_score=health_score * REPO_HEALTH_WEIGHT,
            confidence=health_confidence,
            reasoning=health_reasoning,
            match_description=self._get_match_description(health_score, "health")
        ))

        # =====================================================================
        # CLARITY COMPONENT
        # =====================================================================
        clarity_score = self.calculate_clarity_score(analysis.clarity_score)

        # Get reasoning from LLM analysis (with fallback)
        clarity_reasoning = getattr(analysis, 'clarity_reasoning', '') or ''
        if not clarity_reasoning:
            if analysis.clarity_score >= 8:
                clarity_reasoning = "Well-written issue with clear requirements"
            elif analysis.clarity_score >= 5:
                clarity_reasoning = "Moderately clear, some details may need clarification"
            else:
                clarity_reasoning = "Unclear issue, may require discussion with maintainers"

        components.append(ScoreComponent(
            name="Issue Clarity",
            score=clarity_score,
            weight=ISSUE_CLARITY_WEIGHT,
            weighted_score=clarity_score * ISSUE_CLARITY_WEIGHT,
            confidence="high",  # Clarity is directly assessed
            reasoning=clarity_reasoning,
            match_description=self._get_match_description(clarity_score, "clarity")
        ))

        # =====================================================================
        # CALCULATE TOTALS
        # =====================================================================
        total_score = sum(c.weighted_score for c in components)
        overall_confidence = self._calculate_overall_confidence(components)

        # Legacy breakdown dict for backwards compatibility
        breakdown = {
            "difficulty": difficulty_score,
            "time": time_score,
            "health": health_score,
            "clarity": clarity_score
        }

        return ScoredIssue(
            issue=issue,
            analysis=analysis,
            score=total_score,
            score_breakdown=breakdown,
            score_components=components,
            overall_confidence=overall_confidence
        )

    def rank_issues(
        self,
        analyzed_issues: List[Tuple[IssueData, IssueAnalysis]],
        user_skill: str,
        user_time: str
    ) -> List[ScoredIssue]:
        """
        Score and rank all analyzed issues.

        Returns list sorted by score (highest first).
        """

        scored = []
        for issue, analysis in analyzed_issues:
            scored_issue = self.score_issue(
                issue=issue,
                analysis=analysis,
                user_skill=user_skill,
                user_time=user_time
            )
            scored.append(scored_issue)

        # Sort by score, highest first
        scored.sort(key=lambda x: x.score, reverse=True)

        return scored
