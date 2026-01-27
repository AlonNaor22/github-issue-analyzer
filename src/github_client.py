"""
GitHub API Client for searching issues and checking repository health.

This module handles all interactions with GitHub's REST API using PyGithub.
"""

import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Optional

from github import Github
from dotenv import load_dotenv

from .config import (
    MAX_RESULTS_PER_SEARCH,
    MIN_REPO_STARS,
    BEGINNER_LABELS,
    TOPIC_KEYWORDS
)

# Load environment variables from .env file
load_dotenv()


@dataclass
class IssueData:
    """
    Structured container for GitHub issue data.

    Using a dataclass gives us:
    - Clean, typed data structure
    - Automatic __init__, __repr__, etc.
    - Easy to pass around between components
    """
    id: int
    title: str
    body: str
    url: str
    repo_name: str
    repo_stars: int
    repo_description: str
    labels: List[str]
    created_at: datetime
    updated_at: datetime
    comments_count: int
    assignees: List[str]


@dataclass
class RepoHealth:
    """Repository health metrics."""
    stars: int
    forks: int
    open_issues: int
    days_since_update: int
    has_contributing_guide: bool
    is_healthy: bool


class GitHubClient:
    """
    Client for interacting with GitHub's API.

    Handles:
    - Searching for issues based on user criteria
    - Fetching repository health information
    - Rate limiting awareness
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitHub client.

        Args:
            token: GitHub Personal Access Token. If not provided,
                   reads from GITHUB_TOKEN environment variable.
                   Without a token, you're limited to 60 requests/hour.
                   With a token, you get 5,000 requests/hour.
        """
        self.token = token or os.getenv("GITHUB_TOKEN")

        # PyGithub handles authentication automatically
        self.github = Github(self.token) if self.token else Github()

    def search_issues(
        self,
        topic: str = "any",
        language: str = "any",
        difficulty: str = "beginner",
        max_results: int = MAX_RESULTS_PER_SEARCH
    ) -> List[IssueData]:
        """
        Search GitHub for open issues matching the criteria.

        Args:
            topic: Domain area (ai, web, backend, etc.) or "any"
            language: Programming language or "any"
            difficulty: Skill level (beginner, intermediate, advanced)
            max_results: Maximum number of issues to return

        Returns:
            List of IssueData objects
        """

        # Build the GitHub search query
        query = self._build_query(topic, language, difficulty)

        print(f"  Search query: {query}")

        # Execute the search
        # PyGithub returns a PaginatedList - we iterate through it
        search_results = self.github.search_issues(
            query=query,
            sort="updated",    # Most recently updated first
            order="desc"
        )

        # Convert GitHub objects to our IssueData structure
        issues = []
        for issue in search_results[:max_results]:
            try:
                repo = issue.repository

                issue_data = IssueData(
                    id=issue.number,
                    title=issue.title,
                    body=issue.body or "",  # Body can be None
                    url=issue.html_url,
                    repo_name=repo.full_name,
                    repo_stars=repo.stargazers_count,
                    repo_description=repo.description or "",
                    labels=[label.name for label in issue.labels],
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    comments_count=issue.comments,
                    assignees=[a.login for a in issue.assignees]
                )
                issues.append(issue_data)

            except Exception as e:
                # Skip issues that fail to parse (rare edge cases)
                print(f"  Warning: Skipping issue due to error: {e}")
                continue

        return issues

    def _build_query(self, topic: str, language: str, difficulty: str) -> str:
        """
        Build a GitHub search query string from user preferences.

        GitHub search syntax reference:
        - is:issue - only issues (not PRs)
        - is:open - only open issues
        - no:assignee - not assigned to anyone
        - language:python - repository language
        - label:"good first issue" - has specific label
        - stars:>50 - minimum stars
        - topic:machine-learning - repository topic
        """

        # Start with base filters
        query_parts = [
            "is:issue",      # Only issues, not pull requests
            "is:open",       # Only open issues
            "no:assignee",   # Not already assigned
        ]

        # Add language filter
        if language.lower() != "any":
            query_parts.append(f"language:{language}")

        # Add difficulty-based label filter
        if difficulty == "beginner":
            # Search for common beginner-friendly labels
            query_parts.append('label:"good first issue"')
        elif difficulty == "intermediate":
            query_parts.append('label:"help wanted"')
        # Advanced: no label filter, we'll rely on LLM analysis

        # Add topic filter
        if topic.lower() != "any":
            # Get topic keywords from config
            keywords = TOPIC_KEYWORDS.get(topic.lower(), [topic])
            if keywords:
                # Use the first keyword as the topic
                query_parts.append(f"topic:{keywords[0]}")

        # Add quality filter - only repos with some community
        query_parts.append(f"stars:>{MIN_REPO_STARS}")

        return " ".join(query_parts)

    def check_repo_health(self, repo_name: str) -> RepoHealth:
        """
        Check if a repository is active and healthy.

        A healthy repo:
        - Has been updated recently (< 180 days)
        - Has a CONTRIBUTING.md file
        - Has active maintainers

        Args:
            repo_name: Full repository name (e.g., "facebook/react")

        Returns:
            RepoHealth object with health metrics
        """

        repo = self.github.get_repo(repo_name)

        # Calculate days since last update
        now = datetime.now(timezone.utc)
        last_updated = repo.updated_at.replace(tzinfo=timezone.utc)
        days_since_update = (now - last_updated).days

        # Check for CONTRIBUTING.md
        has_contributing = self._has_file(repo, "CONTRIBUTING.md")

        # Determine if repo is healthy
        is_healthy = (
            days_since_update < 180 and  # Updated in last 6 months
            repo.stargazers_count >= MIN_REPO_STARS
        )

        return RepoHealth(
            stars=repo.stargazers_count,
            forks=repo.forks_count,
            open_issues=repo.open_issues_count,
            days_since_update=days_since_update,
            has_contributing_guide=has_contributing,
            is_healthy=is_healthy
        )

    def _has_file(self, repo, filename: str) -> bool:
        """Check if repository has a specific file."""
        try:
            repo.get_contents(filename)
            return True
        except:
            return False

    def get_rate_limit_status(self) -> dict:
        """Check current API rate limit status."""
        rate_limit = self.github.get_rate_limit()
        return {
            "remaining": rate_limit.core.remaining,
            "limit": rate_limit.core.limit,
            "reset_time": rate_limit.core.reset
        }
