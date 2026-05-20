"""Tests for the scoring and ranking logic — no API calls required."""
import pytest
from src.scorer import IssueScorer, ScoreComponent
from tests.conftest import make_issue, make_analysis, make_repo_health


@pytest.fixture
def scorer():
    return IssueScorer()


class TestDifficultyScore:
    def test_perfect_match_beginner(self, scorer):
        assert scorer.calculate_difficulty_score("beginner", "beginner") == 1.0

    def test_perfect_match_intermediate(self, scorer):
        assert scorer.calculate_difficulty_score("intermediate", "intermediate") == 1.0

    def test_perfect_match_advanced(self, scorer):
        assert scorer.calculate_difficulty_score("advanced", "advanced") == 1.0

    def test_one_level_off(self, scorer):
        assert scorer.calculate_difficulty_score("beginner", "intermediate") == 0.6
        assert scorer.calculate_difficulty_score("intermediate", "advanced") == 0.6

    def test_two_levels_off(self, scorer):
        assert scorer.calculate_difficulty_score("beginner", "advanced") == 0.2
        assert scorer.calculate_difficulty_score("advanced", "beginner") == 0.2

    def test_unknown_difficulty_returns_neutral(self, scorer):
        assert scorer.calculate_difficulty_score("unknown", "beginner") == 0.5

    def test_case_insensitive(self, scorer):
        assert scorer.calculate_difficulty_score("BEGINNER", "beginner") == 1.0
        assert scorer.calculate_difficulty_score("Intermediate", "INTERMEDIATE") == 1.0


class TestTimeScore:
    def test_perfect_match(self, scorer):
        assert scorer.calculate_time_score("quick_win", "quick_win") == 1.0
        assert scorer.calculate_time_score("deep_dive", "deep_dive") == 1.0

    def test_one_level_off(self, scorer):
        assert scorer.calculate_time_score("quick_win", "half_day") == 0.7
        assert scorer.calculate_time_score("half_day", "quick_win") == 0.7

    def test_two_levels_off(self, scorer):
        assert scorer.calculate_time_score("quick_win", "full_day") == 0.4

    def test_three_or_more_levels_off(self, scorer):
        assert scorer.calculate_time_score("quick_win", "weekend") == 0.1
        assert scorer.calculate_time_score("quick_win", "deep_dive") == 0.1

    def test_unknown_time_returns_neutral(self, scorer):
        assert scorer.calculate_time_score("unknown", "quick_win") == 0.5


class TestHealthScore:
    def test_none_health_returns_default(self, scorer):
        score = scorer.calculate_health_score(None)
        assert score == 0.7

    def test_fully_healthy_repo(self, scorer):
        repo = make_repo_health(is_healthy=True, has_contributing_guide=True, days_since_update=10)
        score = scorer.calculate_health_score(repo)
        assert score == 1.0

    def test_healthy_no_contributing_guide(self, scorer):
        repo = make_repo_health(is_healthy=True, has_contributing_guide=False, days_since_update=10)
        score = scorer.calculate_health_score(repo)
        assert score == 0.7

    def test_healthy_old_repo(self, scorer):
        repo = make_repo_health(is_healthy=True, has_contributing_guide=True, days_since_update=60)
        score = scorer.calculate_health_score(repo)
        assert score == 0.8

    def test_unhealthy_repo(self, scorer):
        repo = make_repo_health(is_healthy=False, has_contributing_guide=False, days_since_update=200)
        score = scorer.calculate_health_score(repo)
        assert score == 0.0

    def test_score_never_exceeds_one(self, scorer):
        repo = make_repo_health(is_healthy=True, has_contributing_guide=True, days_since_update=1)
        assert scorer.calculate_health_score(repo) <= 1.0


class TestClarityScore:
    def test_max_clarity(self, scorer):
        assert scorer.calculate_clarity_score(10) == 1.0

    def test_min_clarity(self, scorer):
        assert scorer.calculate_clarity_score(1) == 0.1

    def test_midpoint(self, scorer):
        assert scorer.calculate_clarity_score(5) == 0.5

    def test_clamps_above_ten(self, scorer):
        assert scorer.calculate_clarity_score(15) == 1.0

    def test_clamps_below_zero(self, scorer):
        assert scorer.calculate_clarity_score(-5) == 0.0


class TestMatchDescription:
    def test_excellent_match(self, scorer):
        assert scorer._get_match_description(0.95, "difficulty") == "Excellent match"

    def test_good_match(self, scorer):
        assert scorer._get_match_description(0.75, "difficulty") == "Good match"

    def test_partial_match(self, scorer):
        assert scorer._get_match_description(0.55, "difficulty") == "Partial match"

    def test_weak_match(self, scorer):
        assert scorer._get_match_description(0.35, "difficulty") == "Weak match"

    def test_poor_match(self, scorer):
        assert scorer._get_match_description(0.1, "difficulty") == "Poor match"


class TestOverallConfidence:
    def _make_component(self, confidence: str) -> ScoreComponent:
        return ScoreComponent(
            name="test", score=1.0, weight=0.25,
            weighted_score=0.25, confidence=confidence,
            reasoning="test", match_description="test"
        )

    def test_all_high_returns_high(self, scorer):
        components = [self._make_component("high")] * 4
        assert scorer._calculate_overall_confidence(components) == "high"

    def test_any_low_returns_low(self, scorer):
        components = [
            self._make_component("high"),
            self._make_component("medium"),
            self._make_component("low"),
        ]
        assert scorer._calculate_overall_confidence(components) == "low"

    def test_mixed_high_medium_returns_medium(self, scorer):
        components = [
            self._make_component("high"),
            self._make_component("medium"),
        ]
        assert scorer._calculate_overall_confidence(components) == "medium"


class TestScoreIssue:
    def test_returns_scored_issue(self, scorer, issue, analysis, healthy_repo):
        result = scorer.score_issue(issue, analysis, "beginner", "quick_win", healthy_repo)
        assert result.issue is issue
        assert result.analysis is analysis

    def test_score_in_valid_range(self, scorer, issue, analysis, healthy_repo):
        result = scorer.score_issue(issue, analysis, "beginner", "quick_win", healthy_repo)
        assert 0.0 <= result.score <= 1.0

    def test_perfect_match_scores_high(self, scorer, issue, healthy_repo):
        analysis = make_analysis(
            difficulty="beginner", estimated_time="quick_win", clarity_score=10
        )
        result = scorer.score_issue(issue, analysis, "beginner", "quick_win", healthy_repo)
        assert result.score >= 0.85

    def test_mismatch_scores_low(self, scorer, issue, healthy_repo):
        analysis = make_analysis(
            difficulty="advanced", estimated_time="deep_dive", clarity_score=2
        )
        result = scorer.score_issue(issue, analysis, "beginner", "quick_win", healthy_repo)
        assert result.score < 0.5

    def test_score_breakdown_has_all_components(self, scorer, issue, analysis, healthy_repo):
        result = scorer.score_issue(issue, analysis, "beginner", "quick_win", healthy_repo)
        assert "difficulty" in result.score_breakdown
        assert "time" in result.score_breakdown
        assert "health" in result.score_breakdown
        assert "clarity" in result.score_breakdown

    def test_has_four_score_components(self, scorer, issue, analysis, healthy_repo):
        result = scorer.score_issue(issue, analysis, "beginner", "quick_win", healthy_repo)
        assert len(result.score_components) == 4

    def test_weighted_scores_sum_to_total(self, scorer, issue, analysis, healthy_repo):
        result = scorer.score_issue(issue, analysis, "beginner", "quick_win", healthy_repo)
        component_total = sum(c.weighted_score for c in result.score_components)
        assert abs(component_total - result.score) < 1e-9


class TestRankIssues:
    def test_returns_sorted_by_score_descending(self, scorer):
        high_issue = make_issue(id=1)
        low_issue = make_issue(id=2)
        high_analysis = make_analysis(difficulty="beginner", estimated_time="quick_win", clarity_score=10)
        low_analysis = make_analysis(difficulty="advanced", estimated_time="deep_dive", clarity_score=1)

        pairs = [(high_issue, high_analysis), (low_issue, low_analysis)]
        ranked = scorer.rank_issues(pairs, user_skill="beginner", user_time="quick_win")

        assert ranked[0].issue.id == 1
        assert ranked[1].issue.id == 2
        assert ranked[0].score >= ranked[1].score

    def test_empty_list_returns_empty(self, scorer):
        assert scorer.rank_issues([], "beginner", "quick_win") == []

    def test_single_issue_returns_single(self, scorer):
        ranked = scorer.rank_issues(
            [(make_issue(), make_analysis())],
            user_skill="beginner",
            user_time="quick_win",
        )
        assert len(ranked) == 1
