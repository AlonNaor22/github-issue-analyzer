"""
Issue History Tracker - Track viewed and attempted issues.

=============================================================================
HISTORY vs FAVORITES
=============================================================================

These serve different purposes:

FAVORITES (favorites.py):
- User EXPLICITLY saves issues they're interested in
- Stores full analysis snapshot
- Like a "reading list" or "todo list"

HISTORY (this file):
- AUTOMATICALLY tracks all issues user has seen
- Stores minimal metadata (to keep file small)
- Like "browser history" for issues
- Helps avoid showing the same issues repeatedly

=============================================================================
TRACKING WORKFLOW
=============================================================================

When user views search results:
  Issue appears → Marked as "viewed" (automatic)

When user decides to work on issue:
  User marks as "attempted" (manual or via favorites)

When user completes or abandons:
  User marks as "completed" or "abandoned"

The history helps answer:
- "Have I seen this issue before?"
- "How many issues have I looked at this month?"
- "What's my completion rate?"

=============================================================================
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, asdict
from enum import Enum

from .config import DATA_DIR


class IssueStatus(Enum):
    """Status of an issue in the user's history."""
    VIEWED = "viewed"           # User has seen this issue
    INTERESTED = "interested"   # User showed interest (e.g., clicked link)
    ATTEMPTED = "attempted"     # User started working on it
    COMPLETED = "completed"     # User completed and submitted PR
    ABANDONED = "abandoned"     # User gave up on this issue
    SKIPPED = "skipped"         # User explicitly skipped/dismissed


@dataclass
class HistoryEntry:
    """
    A single entry in the issue history.

    We keep this lightweight - just enough to identify and filter issues.
    Full details are in favorites if user saved it.
    """
    issue_id: int
    repo_name: str
    title: str                    # For display in history list
    first_seen: str               # ISO datetime - when first viewed
    last_seen: str                # ISO datetime - most recent view
    view_count: int               # How many times viewed
    status: str                   # IssueStatus value
    difficulty: str = ""          # Cached from analysis
    url: str = ""                 # GitHub URL

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(**data)


class HistoryManager:
    """
    Manages the user's issue viewing history.

    Features:
    - Automatic tracking of viewed issues
    - Status progression tracking
    - Filtering seen issues from results
    - Statistics and insights
    """

    def __init__(self, data_dir: str = None):
        """Initialize the history manager."""
        self.data_dir = Path(data_dir or DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.data_dir / "history.json"

        # History stored as dict for O(1) lookups
        self._history: Dict[str, HistoryEntry] = {}
        self._load()

    def _make_key(self, repo_name: str, issue_id: int) -> str:
        """Create unique key for an issue."""
        return f"{repo_name}#{issue_id}"

    def _load(self):
        """Load history from disk."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._history = {
                    key: HistoryEntry.from_dict(entry)
                    for key, entry in data.items()
                }
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: Could not load history: {e}")
                self._history = {}

    def _save(self):
        """Save history to disk."""
        data = {
            key: entry.to_dict()
            for key, entry in self._history.items()
        }

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # TRACKING - Record Issue Views
    # =========================================================================

    def record_view(
        self,
        issue_id: int,
        repo_name: str,
        title: str,
        difficulty: str = "",
        url: str = ""
    ) -> HistoryEntry:
        """
        Record that user viewed an issue.

        If already in history, updates last_seen and increments view_count.
        If new, creates entry with status=VIEWED.
        """
        key = self._make_key(repo_name, issue_id)
        now = datetime.now().isoformat()

        if key in self._history:
            # Update existing entry
            entry = self._history[key]
            entry.last_seen = now
            entry.view_count += 1
            # Update title/difficulty if provided (might have changed)
            if title:
                entry.title = title
            if difficulty:
                entry.difficulty = difficulty
            if url:
                entry.url = url
        else:
            # Create new entry
            entry = HistoryEntry(
                issue_id=issue_id,
                repo_name=repo_name,
                title=title,
                first_seen=now,
                last_seen=now,
                view_count=1,
                status=IssueStatus.VIEWED.value,
                difficulty=difficulty,
                url=url
            )
            self._history[key] = entry

        self._save()
        return entry

    def record_batch(self, issues: List[dict]):
        """
        Record multiple issues as viewed (e.g., from search results).

        Args:
            issues: List of dicts with keys: issue_id, repo_name, title, difficulty, url
        """
        for issue in issues:
            self.record_view(
                issue_id=issue.get("issue_id"),
                repo_name=issue.get("repo_name"),
                title=issue.get("title", ""),
                difficulty=issue.get("difficulty", ""),
                url=issue.get("url", "")
            )

    # =========================================================================
    # STATUS UPDATES
    # =========================================================================

    def update_status(
        self,
        repo_name: str,
        issue_id: int,
        status: IssueStatus
    ) -> bool:
        """
        Update the status of an issue in history.

        Args:
            status: New IssueStatus value
        """
        key = self._make_key(repo_name, issue_id)

        if key not in self._history:
            return False

        self._history[key].status = status.value
        self._history[key].last_seen = datetime.now().isoformat()
        self._save()

        return True

    def mark_attempted(self, repo_name: str, issue_id: int) -> bool:
        """Mark an issue as attempted (started working on it)."""
        return self.update_status(repo_name, issue_id, IssueStatus.ATTEMPTED)

    def mark_completed(self, repo_name: str, issue_id: int) -> bool:
        """Mark an issue as completed (PR submitted/merged)."""
        return self.update_status(repo_name, issue_id, IssueStatus.COMPLETED)

    def mark_abandoned(self, repo_name: str, issue_id: int) -> bool:
        """Mark an issue as abandoned (gave up)."""
        return self.update_status(repo_name, issue_id, IssueStatus.ABANDONED)

    def mark_skipped(self, repo_name: str, issue_id: int) -> bool:
        """Mark an issue as skipped (not interested)."""
        return self.update_status(repo_name, issue_id, IssueStatus.SKIPPED)

    # =========================================================================
    # QUERIES
    # =========================================================================

    def is_seen(self, repo_name: str, issue_id: int) -> bool:
        """Check if an issue has been seen before."""
        key = self._make_key(repo_name, issue_id)
        return key in self._history

    def get_entry(self, repo_name: str, issue_id: int) -> Optional[HistoryEntry]:
        """Get history entry for a specific issue."""
        key = self._make_key(repo_name, issue_id)
        return self._history.get(key)

    def get_status(self, repo_name: str, issue_id: int) -> Optional[str]:
        """Get status of an issue, or None if not in history."""
        entry = self.get_entry(repo_name, issue_id)
        return entry.status if entry else None

    def get_seen_issue_keys(self) -> Set[str]:
        """Get set of all seen issue keys for fast filtering."""
        return set(self._history.keys())

    def filter_unseen(self, issues: List[dict]) -> List[dict]:
        """
        Filter a list of issues to only those not yet seen.

        Args:
            issues: List of issue dicts with 'repo_name' and 'issue_id' keys

        Returns:
            Filtered list with only unseen issues
        """
        seen_keys = self.get_seen_issue_keys()

        return [
            issue for issue in issues
            if self._make_key(issue["repo_name"], issue["issue_id"]) not in seen_keys
        ]

    # =========================================================================
    # LISTING
    # =========================================================================

    def list_all(self, limit: int = None) -> List[HistoryEntry]:
        """Get all history entries, sorted by last_seen (newest first)."""
        entries = sorted(
            self._history.values(),
            key=lambda x: x.last_seen,
            reverse=True
        )
        return entries[:limit] if limit else entries

    def list_by_status(self, status: IssueStatus) -> List[HistoryEntry]:
        """Get entries filtered by status."""
        return [
            entry for entry in self._history.values()
            if entry.status == status.value
        ]

    def list_recent(self, days: int = 7) -> List[HistoryEntry]:
        """Get entries from the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        return [
            entry for entry in self.list_all()
            if entry.last_seen >= cutoff
        ]

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict:
        """Get statistics about the history."""
        all_entries = list(self._history.values())

        # Count by status
        status_counts = {}
        for entry in all_entries:
            status_counts[entry.status] = status_counts.get(entry.status, 0) + 1

        # Count by difficulty
        difficulty_counts = {}
        for entry in all_entries:
            if entry.difficulty:
                difficulty_counts[entry.difficulty] = difficulty_counts.get(entry.difficulty, 0) + 1

        # Recent activity
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        month_ago = (datetime.now() - timedelta(days=30)).isoformat()

        recent_week = len([e for e in all_entries if e.last_seen >= week_ago])
        recent_month = len([e for e in all_entries if e.last_seen >= month_ago])

        # Completion rate
        attempted = status_counts.get(IssueStatus.ATTEMPTED.value, 0)
        completed = status_counts.get(IssueStatus.COMPLETED.value, 0)
        completion_rate = completed / (attempted + completed) if (attempted + completed) > 0 else 0

        # Most viewed
        most_viewed = sorted(all_entries, key=lambda x: x.view_count, reverse=True)[:5]

        return {
            "total": len(all_entries),
            "by_status": status_counts,
            "by_difficulty": difficulty_counts,
            "recent_week": recent_week,
            "recent_month": recent_month,
            "completion_rate": completion_rate,
            "most_viewed": most_viewed
        }

    def count(self) -> int:
        """Get total number of entries in history."""
        return len(self._history)

    # =========================================================================
    # MANAGEMENT
    # =========================================================================

    def remove_entry(self, repo_name: str, issue_id: int) -> bool:
        """Remove a single entry from history."""
        key = self._make_key(repo_name, issue_id)
        if key in self._history:
            del self._history[key]
            self._save()
            return True
        return False

    def clear_old(self, days: int = 90) -> int:
        """
        Remove entries older than N days (except completed/attempted).

        Returns number of entries removed.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        keep_statuses = {IssueStatus.ATTEMPTED.value, IssueStatus.COMPLETED.value}

        to_remove = [
            key for key, entry in self._history.items()
            if entry.last_seen < cutoff and entry.status not in keep_statuses
        ]

        for key in to_remove:
            del self._history[key]

        if to_remove:
            self._save()

        return len(to_remove)

    def clear_all(self) -> int:
        """Clear all history. Returns count of removed entries."""
        count = len(self._history)
        self._history = {}
        self._save()
        return count
