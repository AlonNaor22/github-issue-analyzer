"""Validate that config constants are internally consistent."""
import src.config as config


class TestScoringWeights:
    def test_weights_sum_to_one(self):
        total = (
            config.DIFFICULTY_MATCH_WEIGHT
            + config.TIME_MATCH_WEIGHT
            + config.REPO_HEALTH_WEIGHT
            + config.ISSUE_CLARITY_WEIGHT
        )
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_all_weights_positive(self):
        assert config.DIFFICULTY_MATCH_WEIGHT > 0
        assert config.TIME_MATCH_WEIGHT > 0
        assert config.REPO_HEALTH_WEIGHT > 0
        assert config.ISSUE_CLARITY_WEIGHT > 0


class TestSearchSettings:
    def test_max_results_positive(self):
        assert config.MAX_RESULTS_PER_SEARCH > 0

    def test_min_stars_non_negative(self):
        assert config.MIN_REPO_STARS >= 0

    def test_issues_to_analyze_lte_max_results(self):
        assert config.ISSUES_TO_ANALYZE <= config.MAX_RESULTS_PER_SEARCH


class TestTimeCategories:
    def test_all_expected_categories_present(self):
        expected = {"quick_win", "half_day", "full_day", "weekend", "deep_dive"}
        assert set(config.TIME_CATEGORIES.keys()) == expected

    def test_time_labels_match_categories(self):
        assert set(config.TIME_LABELS.keys()) == set(config.TIME_CATEGORIES.keys())

    def test_time_ranges_are_ordered(self):
        ranges = list(config.TIME_CATEGORIES.values())
        for i in range(len(ranges) - 1):
            assert ranges[i][1] <= ranges[i + 1][0] or ranges[i + 1][0] == ranges[i][1]


class TestLLMSettings:
    def test_temperature_is_zero_for_determinism(self):
        assert config.TEMPERATURE == 0.0

    def test_max_tokens_positive(self):
        assert config.MAX_TOKENS > 0

    def test_model_name_is_string(self):
        assert isinstance(config.MODEL_NAME, str) and config.MODEL_NAME.strip()
