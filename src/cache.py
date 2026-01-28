"""
Caching layer for GitHub Issue Analyzer.

=============================================================================
WHY CACHING MATTERS FOR AI APPLICATIONS
=============================================================================

1. COST SAVINGS:
   - Every Claude API call costs money (input + output tokens)
   - Analyzing the same issue twice = paying twice for identical results
   - With caching, we pay once and reuse

2. SPEED:
   - Claude API calls take 1-3 seconds each
   - Cached responses are instant (milliseconds)
   - Users get faster results on repeated searches

3. RATE LIMITS:
   - GitHub: 5,000 requests/hour (with token)
   - Caching reduces redundant API calls

=============================================================================
CACHING STRATEGY
=============================================================================

We cache at TWO levels:

1. GITHUB SEARCH CACHE (short-lived: 15 minutes)
   - Key: hash of search query parameters
   - Value: list of issue data
   - Why short? Issues change frequently (new comments, closed, etc.)

2. LLM ANALYSIS CACHE (long-lived: 24 hours)
   - Key: hash of (issue_id + issue_updated_at + user_preferences)
   - Value: Claude's analysis
   - Why longer? Analysis doesn't change unless the issue changes
   - We include updated_at in the key so edits invalidate the cache

=============================================================================
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Any, List
from pathlib import Path

from diskcache import Cache

from .config import (
    CACHE_DIR,
    GITHUB_CACHE_TTL_MINUTES,
    LLM_CACHE_TTL_HOURS
)


class CacheManager:
    """
    Manages caching for both GitHub API and LLM responses.

    Uses diskcache, which stores data on disk (not just memory).
    This means cache persists between program runs!
    """

    def __init__(self, cache_dir: str = None):
        """
        Initialize the cache.

        Args:
            cache_dir: Directory to store cache files.
                      Defaults to .cache/ in project root.
        """
        self.cache_dir = cache_dir or CACHE_DIR

        # Create separate caches for different purposes
        # This allows different expiration policies
        self.github_cache = Cache(os.path.join(self.cache_dir, "github"))
        self.llm_cache = Cache(os.path.join(self.cache_dir, "llm"))

        # Statistics for reporting
        self.stats = {
            "github_hits": 0,
            "github_misses": 0,
            "llm_hits": 0,
            "llm_misses": 0
        }

    # =========================================================================
    # GITHUB SEARCH CACHING
    # =========================================================================

    def _make_github_key(self, topic: str, language: str, difficulty: str) -> str:
        """
        Create a unique cache key for a GitHub search.

        We hash the parameters to create a consistent, short key.
        Same parameters = same hash = cache hit!
        """
        # Combine parameters into a string
        key_data = f"github_search:{topic}:{language}:{difficulty}"

        # Hash it for a shorter, consistent key
        return hashlib.md5(key_data.encode()).hexdigest()

    def get_github_search(
        self,
        topic: str,
        language: str,
        difficulty: str
    ) -> Optional[List[dict]]:
        """
        Try to get cached GitHub search results.

        Returns:
            List of issue dicts if cached, None if not found or expired
        """
        key = self._make_github_key(topic, language, difficulty)

        result = self.github_cache.get(key)

        if result is not None:
            self.stats["github_hits"] += 1
            return result
        else:
            self.stats["github_misses"] += 1
            return None

    def set_github_search(
        self,
        topic: str,
        language: str,
        difficulty: str,
        issues: List[dict]
    ):
        """
        Cache GitHub search results.

        Args:
            issues: List of issue data (as dicts, not dataclass objects)
        """
        key = self._make_github_key(topic, language, difficulty)

        # expire= sets TTL in seconds
        ttl_seconds = GITHUB_CACHE_TTL_MINUTES * 60

        self.github_cache.set(key, issues, expire=ttl_seconds)

    # =========================================================================
    # LLM ANALYSIS CACHING
    # =========================================================================

    def _make_llm_key(
        self,
        issue_id: int,
        repo_name: str,
        issue_updated_at: datetime,
        user_skill: str,
        user_time: str
    ) -> str:
        """
        Create a unique cache key for an LLM analysis.

        IMPORTANT: We include issue_updated_at in the key!
        This means if the issue is edited, we get a cache miss
        and re-analyze with the new content.

        We also include user preferences because Claude's analysis
        considers them (e.g., "good match for beginner" vs "too easy for advanced")
        """
        # Format datetime consistently
        updated_str = issue_updated_at.isoformat() if issue_updated_at else "unknown"

        key_data = f"llm:{repo_name}:{issue_id}:{updated_str}:{user_skill}:{user_time}"

        return hashlib.md5(key_data.encode()).hexdigest()

    def get_llm_analysis(
        self,
        issue_id: int,
        repo_name: str,
        issue_updated_at: datetime,
        user_skill: str,
        user_time: str
    ) -> Optional[dict]:
        """
        Try to get cached LLM analysis.

        Returns:
            Analysis dict if cached, None if not found or expired
        """
        key = self._make_llm_key(
            issue_id, repo_name, issue_updated_at, user_skill, user_time
        )

        result = self.llm_cache.get(key)

        if result is not None:
            self.stats["llm_hits"] += 1
            return result
        else:
            self.stats["llm_misses"] += 1
            return None

    def set_llm_analysis(
        self,
        issue_id: int,
        repo_name: str,
        issue_updated_at: datetime,
        user_skill: str,
        user_time: str,
        analysis: dict
    ):
        """
        Cache an LLM analysis result.

        Args:
            analysis: The IssueAnalysis as a dict
        """
        key = self._make_llm_key(
            issue_id, repo_name, issue_updated_at, user_skill, user_time
        )

        ttl_seconds = LLM_CACHE_TTL_HOURS * 3600

        self.llm_cache.set(key, analysis, expire=ttl_seconds)

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

    def get_stats(self) -> dict:
        """Get cache hit/miss statistics."""
        total_github = self.stats["github_hits"] + self.stats["github_misses"]
        total_llm = self.stats["llm_hits"] + self.stats["llm_misses"]

        return {
            "github": {
                "hits": self.stats["github_hits"],
                "misses": self.stats["github_misses"],
                "hit_rate": self.stats["github_hits"] / total_github if total_github > 0 else 0
            },
            "llm": {
                "hits": self.stats["llm_hits"],
                "misses": self.stats["llm_misses"],
                "hit_rate": self.stats["llm_hits"] / total_llm if total_llm > 0 else 0
            },
            "cache_size_mb": self._get_cache_size_mb()
        }

    def _get_cache_size_mb(self) -> float:
        """Calculate total cache size in MB."""
        total_bytes = 0
        cache_path = Path(self.cache_dir)

        if cache_path.exists():
            for file in cache_path.rglob("*"):
                if file.is_file():
                    total_bytes += file.stat().st_size

        return round(total_bytes / (1024 * 1024), 2)

    def clear_all(self):
        """Clear all caches."""
        self.github_cache.clear()
        self.llm_cache.clear()
        self.stats = {k: 0 for k in self.stats}

    def clear_github(self):
        """Clear only GitHub cache."""
        self.github_cache.clear()

    def clear_llm(self):
        """Clear only LLM cache."""
        self.llm_cache.clear()


# =============================================================================
# LANGCHAIN CACHING INTEGRATION
# =============================================================================
#
# LangChain also has built-in caching support! You could use:
#
#   from langchain.cache import SQLiteCache
#   from langchain.globals import set_llm_cache
#
#   set_llm_cache(SQLiteCache(database_path=".langchain.db"))
#
# This caches ALL LLM calls automatically based on the prompt.
#
# However, we're using manual caching because:
# 1. We want more control over cache keys (include issue_updated_at)
# 2. We want separate TTLs for GitHub vs LLM caches
# 3. We want to track statistics
# 4. Educational purposes - understanding what's happening!
#
# In production, you might use both:
# - LangChain's cache for general LLM calls
# - Custom cache for domain-specific logic
#
# =============================================================================
