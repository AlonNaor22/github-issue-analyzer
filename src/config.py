"""
Configuration constants for the GitHub Issue Analyzer.

This file contains all the tunable parameters that control how the agent
searches, filters, and analyzes GitHub issues.
"""

# =============================================================================
# GitHub Search Settings
# =============================================================================

MAX_RESULTS_PER_SEARCH = 50      # Issues to fetch from GitHub API
MIN_REPO_STARS = 50              # Minimum repository stars (filters low-quality repos)
MAX_ISSUE_AGE_DAYS = 365         # Ignore issues older than this
MIN_REPO_ACTIVITY_DAYS = 180     # Repo must have commits within this period

# =============================================================================
# LLM Analysis Settings
# =============================================================================

ISSUES_TO_ANALYZE = 20           # Top issues to send to Claude for analysis
MODEL_NAME = "claude-haiku-4-5-20251001"  # Cost-effective model for analysis
TEMPERATURE = 0.0                # Deterministic output (no randomness)
MAX_TOKENS = 1024                # Max response length per issue

# =============================================================================
# Scoring Weights (must sum to 1.0)
# =============================================================================

DIFFICULTY_MATCH_WEIGHT = 0.40   # How well difficulty matches user preference
TIME_MATCH_WEIGHT = 0.30         # How well time estimate matches
REPO_HEALTH_WEIGHT = 0.15        # Repository activity and quality
ISSUE_CLARITY_WEIGHT = 0.15      # How clear and actionable the issue is

# =============================================================================
# Difficulty Label Mappings
# =============================================================================
# These map GitHub labels to our internal difficulty levels

BEGINNER_LABELS = [
    "good first issue",
    "beginner",
    "easy",
    "starter",
    "first-timers-only",
    "good-first-issue",
    "low-hanging-fruit"
]

INTERMEDIATE_LABELS = [
    "help wanted",
    "intermediate",
    "medium"
]

ADVANCED_LABELS = [
    "advanced",
    "hard",
    "expert",
    "complex"
]

# =============================================================================
# Time Categories (in hours)
# =============================================================================

TIME_CATEGORIES = {
    "quick_win": (0, 2),        # < 2 hours
    "half_day": (2, 4),         # 2-4 hours
    "full_day": (4, 8),         # 4-8 hours
    "weekend": (8, 24),         # 1-3 days
    "deep_dive": (24, float('inf'))  # 1+ week
}

# Human-readable time labels
TIME_LABELS = {
    "quick_win": "< 2 hours",
    "half_day": "2-4 hours",
    "full_day": "4-8 hours",
    "weekend": "1-3 days",
    "deep_dive": "1+ week"
}

# =============================================================================
# Topic Keywords (for search query building)
# =============================================================================

TOPIC_KEYWORDS = {
    "ai": ["machine-learning", "deep-learning", "artificial-intelligence", "ml", "ai"],
    "web": ["web", "frontend", "react", "vue", "angular", "css", "html"],
    "backend": ["backend", "api", "server", "database", "rest", "graphql"],
    "devops": ["devops", "docker", "kubernetes", "ci-cd", "infrastructure"],
    "mobile": ["mobile", "ios", "android", "react-native", "flutter"],
    "data": ["data-science", "analytics", "visualization", "pandas"],
    "security": ["security", "authentication", "encryption"]
}
