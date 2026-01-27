"""
Scoring and ranking system for analyzed issues.

Takes Claude's analysis and calculates a match score based on:
- How well difficulty matches user's skill level
- How well time estimate matches user's availability
- Repository health
- Issue clarity
"""

from dataclasses import dataclass
from typing import List, Tuple

from .config import (
    DIFFICULTY_MATCH_WEIGHT,
    TIME_MATCH_WEIGHT,
    REPO_HEALTH_WEIGHT,
    ISSUE_CLARITY_WEIGHT
)
from .github_client import IssueData, RepoHealth
from .analyzer import IssueAnalysis


@dataclass
class ScoredIssue:
    """An issue with its analysis and calculated match score."""
    issue: IssueData
    analysis: IssueAnalysis
    score: float              # Overall score (0-1)
    score_breakdown: dict     # Individual component scores


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

        Returns a ScoredIssue with the total score and breakdown.
        """

        # Calculate individual scores
        difficulty_score = self.calculate_difficulty_score(
            analysis.difficulty,
            user_skill
        )

        time_score = self.calculate_time_score(
            analysis.estimated_time,
            user_time
        )

        health_score = self.calculate_health_score(repo_health)

        clarity_score = self.calculate_clarity_score(analysis.clarity_score)

        # Weighted total
        total_score = (
            difficulty_score * DIFFICULTY_MATCH_WEIGHT +
            time_score * TIME_MATCH_WEIGHT +
            health_score * REPO_HEALTH_WEIGHT +
            clarity_score * ISSUE_CLARITY_WEIGHT
        )

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
            score_breakdown=breakdown
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
