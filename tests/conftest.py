"""Shared fixtures for all test modules."""
import pytest
from datetime import datetime, timezone

from src.github_client import IssueData, RepoHealth
from src.analyzer import IssueAnalysis


def make_issue(**overrides) -> IssueData:
    """Factory for IssueData with sensible defaults."""
    defaults = dict(
        id=1,
        title="Fix null pointer in login handler",
        body="When user submits empty form, app crashes with NPE.",
        url="https://github.com/org/repo/issues/1",
        repo_name="org/repo",
        repo_stars=500,
        repo_description="A web framework",
        labels=["good first issue"],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        comments_count=3,
        assignees=[],
    )
    return IssueData(**{**defaults, **overrides})


def make_analysis(**overrides) -> IssueAnalysis:
    """Factory for IssueAnalysis with sensible defaults."""
    defaults = dict(
        difficulty="beginner",
        difficulty_confidence="high",
        difficulty_reasoning="Simple fix with clear instructions.",
        estimated_time="quick_win",
        time_confidence="high",
        time_reasoning="One-line change with an existing test.",
        summary="Fix null check in the login handler.",
        technical_requirements=["Python", "pytest"],
        clarity_score=8,
        clarity_reasoning="Issue is well described with steps to reproduce.",
        recommendation="Great for a beginner looking for a quick win.",
    )
    return IssueAnalysis(**{**defaults, **overrides})


def make_repo_health(**overrides) -> RepoHealth:
    """Factory for RepoHealth with a healthy default."""
    defaults = dict(
        stars=500,
        forks=50,
        open_issues=12,
        days_since_update=10,
        has_contributing_guide=True,
        is_healthy=True,
    )
    return RepoHealth(**{**defaults, **overrides})


@pytest.fixture
def issue():
    return make_issue()


@pytest.fixture
def analysis():
    return make_analysis()


@pytest.fixture
def healthy_repo():
    return make_repo_health()
