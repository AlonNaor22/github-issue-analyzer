"""
Favorites Manager - Save and manage bookmarked GitHub issues.

This module provides functionality to:
- Save issues for later reference
- List saved favorites
- Remove favorites
- Add notes/tags to favorites

=============================================================================
DATA PERSISTENCE PATTERNS
=============================================================================

When building CLI tools, you often need to persist data between runs.
Common approaches:

1. JSON FILES (what we use here)
   - Human-readable and editable
   - Easy to backup/share
   - Good for small datasets (<1000 items)
   - Example: ~/.config/myapp/data.json

2. SQLITE DATABASE
   - Better for structured queries
   - Handles larger datasets
   - Example: ~/.local/share/myapp/data.db

3. CLOUD STORAGE
   - Sync across devices
   - Requires authentication
   - Example: Firebase, Supabase

For a personal CLI tool, JSON is perfect - simple and transparent.

=============================================================================
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict, field

from .config import DATA_DIR


@dataclass
class FavoriteIssue:
    """
    A saved/bookmarked GitHub issue.

    We store more than just the URL so users can browse their
    favorites without making API calls.
    """

    # Core issue data
    issue_id: int
    repo_name: str
    title: str
    url: str

    # Analysis snapshot (at time of saving)
    difficulty: str
    estimated_time: str
    summary: str

    # User additions
    saved_at: str  # ISO format datetime
    notes: str = ""  # User's personal notes
    tags: List[str] = field(default_factory=list)  # User-defined tags
    status: str = "saved"  # saved, in_progress, completed, abandoned

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FavoriteIssue":
        """Create from dictionary (when loading from JSON)."""
        return cls(**data)


class FavoritesManager:
    """
    Manages the user's saved/bookmarked issues.

    Storage: JSON file at .data/favorites.json
    """

    def __init__(self, data_dir: str = None):
        """
        Initialize the favorites manager.

        Args:
            data_dir: Directory to store data files.
                     Defaults to .data/ in project root.
        """
        self.data_dir = Path(data_dir or DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.favorites_file = self.data_dir / "favorites.json"

        # Load existing favorites
        self._favorites: Dict[str, FavoriteIssue] = {}
        self._load()

    def _make_key(self, repo_name: str, issue_id: int) -> str:
        """Create a unique key for an issue."""
        return f"{repo_name}#{issue_id}"

    def _load(self):
        """Load favorites from disk."""
        if self.favorites_file.exists():
            try:
                with open(self.favorites_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._favorites = {
                    key: FavoriteIssue.from_dict(item)
                    for key, item in data.items()
                }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load favorites: {e}")
                self._favorites = {}
        else:
            self._favorites = {}

    def _save(self):
        """Save favorites to disk."""
        data = {
            key: fav.to_dict()
            for key, fav in self._favorites.items()
        }

        with open(self.favorites_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def add(
        self,
        issue_id: int,
        repo_name: str,
        title: str,
        url: str,
        difficulty: str,
        estimated_time: str,
        summary: str,
        notes: str = "",
        tags: List[str] = None
    ) -> FavoriteIssue:
        """
        Add an issue to favorites.

        Args:
            issue_id: GitHub issue number
            repo_name: Full repo name (e.g., "facebook/react")
            title: Issue title
            url: GitHub URL
            difficulty: Analyzed difficulty level
            estimated_time: Analyzed time estimate
            summary: Issue summary from analysis
            notes: Optional user notes
            tags: Optional tags for organization

        Returns:
            The created FavoriteIssue
        """
        key = self._make_key(repo_name, issue_id)

        favorite = FavoriteIssue(
            issue_id=issue_id,
            repo_name=repo_name,
            title=title,
            url=url,
            difficulty=difficulty,
            estimated_time=estimated_time,
            summary=summary,
            saved_at=datetime.now().isoformat(),
            notes=notes,
            tags=tags or []
        )

        self._favorites[key] = favorite
        self._save()

        return favorite

    def remove(self, repo_name: str, issue_id: int) -> bool:
        """
        Remove an issue from favorites.

        Returns:
            True if removed, False if not found
        """
        key = self._make_key(repo_name, issue_id)

        if key in self._favorites:
            del self._favorites[key]
            self._save()
            return True

        return False

    def get(self, repo_name: str, issue_id: int) -> Optional[FavoriteIssue]:
        """Get a specific favorite by repo and issue ID."""
        key = self._make_key(repo_name, issue_id)
        return self._favorites.get(key)

    def is_favorite(self, repo_name: str, issue_id: int) -> bool:
        """Check if an issue is in favorites."""
        key = self._make_key(repo_name, issue_id)
        return key in self._favorites

    def list_all(self) -> List[FavoriteIssue]:
        """Get all favorites, sorted by saved date (newest first)."""
        return sorted(
            self._favorites.values(),
            key=lambda x: x.saved_at,
            reverse=True
        )

    def list_by_status(self, status: str) -> List[FavoriteIssue]:
        """Get favorites filtered by status."""
        return [
            fav for fav in self.list_all()
            if fav.status == status
        ]

    def list_by_tag(self, tag: str) -> List[FavoriteIssue]:
        """Get favorites that have a specific tag."""
        return [
            fav for fav in self.list_all()
            if tag in fav.tags
        ]

    def update_notes(self, repo_name: str, issue_id: int, notes: str) -> bool:
        """Update notes for a favorite."""
        key = self._make_key(repo_name, issue_id)

        if key in self._favorites:
            self._favorites[key].notes = notes
            self._save()
            return True

        return False

    def update_status(self, repo_name: str, issue_id: int, status: str) -> bool:
        """
        Update status of a favorite.

        Valid statuses: saved, in_progress, completed, abandoned
        """
        valid_statuses = ["saved", "in_progress", "completed", "abandoned"]

        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

        key = self._make_key(repo_name, issue_id)

        if key in self._favorites:
            self._favorites[key].status = status
            self._save()
            return True

        return False

    def add_tag(self, repo_name: str, issue_id: int, tag: str) -> bool:
        """Add a tag to a favorite."""
        key = self._make_key(repo_name, issue_id)

        if key in self._favorites:
            if tag not in self._favorites[key].tags:
                self._favorites[key].tags.append(tag)
                self._save()
            return True

        return False

    def remove_tag(self, repo_name: str, issue_id: int, tag: str) -> bool:
        """Remove a tag from a favorite."""
        key = self._make_key(repo_name, issue_id)

        if key in self._favorites:
            if tag in self._favorites[key].tags:
                self._favorites[key].tags.remove(tag)
                self._save()
            return True

        return False

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all favorites."""
        tags = set()
        for fav in self._favorites.values():
            tags.update(fav.tags)
        return sorted(tags)

    def count(self) -> int:
        """Get total number of favorites."""
        return len(self._favorites)

    def get_stats(self) -> dict:
        """Get statistics about favorites."""
        all_favs = list(self._favorites.values())

        status_counts = {}
        for fav in all_favs:
            status_counts[fav.status] = status_counts.get(fav.status, 0) + 1

        difficulty_counts = {}
        for fav in all_favs:
            difficulty_counts[fav.difficulty] = difficulty_counts.get(fav.difficulty, 0) + 1

        return {
            "total": len(all_favs),
            "by_status": status_counts,
            "by_difficulty": difficulty_counts,
            "tags": self.get_all_tags()
        }
