"""Tests for GitHub search query construction — no API calls required."""
import pytest
from src.github_client import GitHubClient


@pytest.fixture
def client():
    return GitHubClient(token="fake-token-for-testing")


class TestBaseQueryParts:
    def test_always_filters_issues_only(self, client):
        query = client._build_query("any", "any", "beginner")
        assert "is:issue" in query

    def test_always_filters_open_only(self, client):
        query = client._build_query("any", "any", "beginner")
        assert "is:open" in query

    def test_always_filters_unassigned(self, client):
        query = client._build_query("any", "any", "beginner")
        assert "no:assignee" in query

    def test_always_includes_stars_filter(self, client):
        query = client._build_query("any", "any", "beginner")
        assert "stars:>" in query


class TestLanguageFilter:
    def test_any_language_omits_filter(self, client):
        query = client._build_query("any", "any", "beginner")
        assert "language:" not in query

    def test_specific_language_included(self, client):
        query = client._build_query("any", "python", "beginner")
        assert "language:python" in query

    def test_language_case_insensitive(self, client):
        query = client._build_query("any", "Python", "beginner")
        assert "language:Python" in query


class TestDifficultyFilter:
    def test_beginner_adds_good_first_issue_label(self, client):
        query = client._build_query("any", "any", "beginner")
        assert 'label:"good first issue"' in query

    def test_intermediate_adds_help_wanted_label(self, client):
        query = client._build_query("any", "any", "intermediate")
        assert 'label:"help wanted"' in query

    def test_advanced_adds_no_label_filter(self, client):
        query = client._build_query("any", "any", "advanced")
        assert "label:" not in query


class TestTopicFilter:
    def test_any_topic_omits_topic_filter(self, client):
        query = client._build_query("any", "any", "beginner")
        assert "topic:" not in query

    def test_known_topic_adds_first_keyword(self, client):
        query = client._build_query("ai", "any", "beginner")
        assert "topic:" in query

    def test_unknown_topic_uses_topic_itself(self, client):
        query = client._build_query("robotics", "any", "beginner")
        assert "topic:robotics" in query
