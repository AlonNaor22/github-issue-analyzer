"""
Custom Label Mappings - Repository-specific label to difficulty mappings.

=============================================================================
THE PROBLEM
=============================================================================

GitHub doesn't have standardized labels. Different projects use different
conventions:

    facebook/react:      "good first issue" → beginner
    rust-lang/rust:      "E-easy" → beginner, "E-medium" → intermediate
    godotengine/godot:   "junior job" → beginner
    kubernetes/k8s:      "good first issue" + "help wanted"

Our default mappings (in config.py) work for most repos, but power users
may want to customize mappings for specific repositories they contribute to.

=============================================================================
THE SOLUTION
=============================================================================

Allow users to define custom label mappings per repository:

    {
        "rust-lang/rust": {
            "beginner": ["E-easy", "E-mentor"],
            "intermediate": ["E-medium"],
            "advanced": ["E-hard"]
        },
        "godotengine/godot": {
            "beginner": ["junior job", "good first issue"],
            "intermediate": ["help wanted"]
        }
    }

When analyzing issues from these repos, we use the custom mappings instead
of the defaults.

=============================================================================
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

from .config import (
    DATA_DIR,
    BEGINNER_LABELS,
    INTERMEDIATE_LABELS,
    ADVANCED_LABELS
)


@dataclass
class RepoLabelMapping:
    """
    Label mapping configuration for a specific repository.

    Maps difficulty levels to lists of GitHub labels.
    """
    repo_name: str
    beginner_labels: List[str] = field(default_factory=list)
    intermediate_labels: List[str] = field(default_factory=list)
    advanced_labels: List[str] = field(default_factory=list)
    notes: str = ""  # Optional notes about this repo's conventions

    def to_dict(self) -> dict:
        return {
            "beginner": self.beginner_labels,
            "intermediate": self.intermediate_labels,
            "advanced": self.advanced_labels,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, repo_name: str, data: dict) -> "RepoLabelMapping":
        return cls(
            repo_name=repo_name,
            beginner_labels=data.get("beginner", []),
            intermediate_labels=data.get("intermediate", []),
            advanced_labels=data.get("advanced", []),
            notes=data.get("notes", "")
        )


class LabelMappingManager:
    """
    Manages custom label mappings for repositories.

    Provides:
    - Custom per-repo mappings stored in JSON
    - Fallback to default global mappings
    - Pre-configured mappings for popular repositories
    """

    # Pre-configured mappings for popular repos with non-standard labels
    BUILTIN_MAPPINGS = {
        "rust-lang/rust": {
            "beginner": ["E-easy", "E-mentor"],
            "intermediate": ["E-medium", "E-needs-mentor"],
            "advanced": ["E-hard"],
            "notes": "Rust uses E- prefix for difficulty levels"
        },
        "godotengine/godot": {
            "beginner": ["junior job", "good first issue"],
            "intermediate": ["help wanted"],
            "advanced": ["senior job"],
            "notes": "Godot uses 'junior job' for beginner issues"
        },
        "servo/servo": {
            "beginner": ["E-easy", "good first issue"],
            "intermediate": ["E-less-easy"],
            "advanced": ["E-hard"],
            "notes": "Servo follows Rust conventions"
        },
        "neovim/neovim": {
            "beginner": ["good first issue", "complexity:low"],
            "intermediate": ["help wanted", "complexity:medium"],
            "advanced": ["complexity:high"],
            "notes": "Neovim uses complexity: labels"
        },
        "python/cpython": {
            "beginner": ["easy", "good first issue"],
            "intermediate": ["help wanted"],
            "advanced": ["expert"],
            "notes": "CPython standard labels"
        },
        "django/django": {
            "beginner": ["easy pickings"],
            "intermediate": ["help wanted"],
            "advanced": [],
            "notes": "Django uses 'easy pickings' for beginner issues"
        },
        "rails/rails": {
            "beginner": ["good first issue", "starter"],
            "intermediate": ["help wanted"],
            "advanced": [],
            "notes": "Rails standard labels"
        }
    }

    def __init__(self, data_dir: str = None):
        """Initialize the label mapping manager."""
        self.data_dir = Path(data_dir or DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.mappings_file = self.data_dir / "label_mappings.json"

        # Custom user mappings (loaded from file)
        self._custom_mappings: Dict[str, RepoLabelMapping] = {}
        self._load()

    def _load(self):
        """Load custom mappings from disk."""
        if self.mappings_file.exists():
            try:
                with open(self.mappings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._custom_mappings = {
                    repo: RepoLabelMapping.from_dict(repo, mapping)
                    for repo, mapping in data.items()
                }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load label mappings: {e}")
                self._custom_mappings = {}

    def _save(self):
        """Save custom mappings to disk."""
        data = {
            repo: mapping.to_dict()
            for repo, mapping in self._custom_mappings.items()
        }

        with open(self.mappings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # PUBLIC API - Query Mappings
    # =========================================================================

    def get_mapping(self, repo_name: str) -> RepoLabelMapping:
        """
        Get label mapping for a repository.

        Priority:
        1. User's custom mapping (highest)
        2. Built-in mapping for known repos
        3. Default global mappings (fallback)
        """
        # Check custom mappings first
        if repo_name in self._custom_mappings:
            return self._custom_mappings[repo_name]

        # Check built-in mappings
        if repo_name in self.BUILTIN_MAPPINGS:
            return RepoLabelMapping.from_dict(
                repo_name,
                self.BUILTIN_MAPPINGS[repo_name]
            )

        # Return default mapping
        return RepoLabelMapping(
            repo_name=repo_name,
            beginner_labels=list(BEGINNER_LABELS),
            intermediate_labels=list(INTERMEDIATE_LABELS),
            advanced_labels=list(ADVANCED_LABELS),
            notes="Using default global mappings"
        )

    def get_difficulty_from_labels(
        self,
        repo_name: str,
        labels: List[str]
    ) -> Optional[str]:
        """
        Determine difficulty level from a list of labels.

        Args:
            repo_name: Repository name (e.g., "facebook/react")
            labels: List of label names from the issue

        Returns:
            "beginner", "intermediate", "advanced", or None if no match
        """
        mapping = self.get_mapping(repo_name)

        # Normalize labels for comparison (lowercase)
        labels_lower = [l.lower() for l in labels]

        # Check each difficulty level
        for label in mapping.beginner_labels:
            if label.lower() in labels_lower:
                return "beginner"

        for label in mapping.intermediate_labels:
            if label.lower() in labels_lower:
                return "intermediate"

        for label in mapping.advanced_labels:
            if label.lower() in labels_lower:
                return "advanced"

        return None

    def has_custom_mapping(self, repo_name: str) -> bool:
        """Check if a repository has a custom user mapping."""
        return repo_name in self._custom_mappings

    def has_builtin_mapping(self, repo_name: str) -> bool:
        """Check if a repository has a built-in mapping."""
        return repo_name in self.BUILTIN_MAPPINGS

    # =========================================================================
    # PUBLIC API - Manage Mappings
    # =========================================================================

    def set_mapping(
        self,
        repo_name: str,
        beginner_labels: List[str] = None,
        intermediate_labels: List[str] = None,
        advanced_labels: List[str] = None,
        notes: str = ""
    ) -> RepoLabelMapping:
        """
        Set or update custom mapping for a repository.

        Args:
            repo_name: Full repository name (e.g., "owner/repo")
            beginner_labels: Labels that indicate beginner difficulty
            intermediate_labels: Labels for intermediate difficulty
            advanced_labels: Labels for advanced difficulty
            notes: Optional notes about this repo's conventions

        Returns:
            The created/updated mapping
        """
        mapping = RepoLabelMapping(
            repo_name=repo_name,
            beginner_labels=beginner_labels or [],
            intermediate_labels=intermediate_labels or [],
            advanced_labels=advanced_labels or [],
            notes=notes
        )

        self._custom_mappings[repo_name] = mapping
        self._save()

        return mapping

    def add_label(
        self,
        repo_name: str,
        difficulty: str,
        label: str
    ) -> bool:
        """
        Add a single label to a repository's mapping.

        Creates the mapping if it doesn't exist.
        """
        if difficulty not in ["beginner", "intermediate", "advanced"]:
            raise ValueError(f"Invalid difficulty: {difficulty}")

        # Get or create mapping
        if repo_name in self._custom_mappings:
            mapping = self._custom_mappings[repo_name]
        else:
            mapping = RepoLabelMapping(repo_name=repo_name)

        # Add label to appropriate list
        label_list = getattr(mapping, f"{difficulty}_labels")
        if label not in label_list:
            label_list.append(label)

        self._custom_mappings[repo_name] = mapping
        self._save()

        return True

    def remove_label(
        self,
        repo_name: str,
        difficulty: str,
        label: str
    ) -> bool:
        """Remove a label from a repository's mapping."""
        if repo_name not in self._custom_mappings:
            return False

        mapping = self._custom_mappings[repo_name]
        label_list = getattr(mapping, f"{difficulty}_labels")

        if label in label_list:
            label_list.remove(label)
            self._save()
            return True

        return False

    def remove_mapping(self, repo_name: str) -> bool:
        """Remove custom mapping for a repository entirely."""
        if repo_name in self._custom_mappings:
            del self._custom_mappings[repo_name]
            self._save()
            return True
        return False

    def import_builtin(self, repo_name: str) -> bool:
        """
        Import a built-in mapping as a custom mapping.

        Useful if user wants to modify a built-in mapping.
        """
        if repo_name not in self.BUILTIN_MAPPINGS:
            return False

        mapping = RepoLabelMapping.from_dict(
            repo_name,
            self.BUILTIN_MAPPINGS[repo_name]
        )

        self._custom_mappings[repo_name] = mapping
        self._save()

        return True

    # =========================================================================
    # PUBLIC API - List Mappings
    # =========================================================================

    def list_custom_mappings(self) -> List[RepoLabelMapping]:
        """Get all custom user mappings."""
        return list(self._custom_mappings.values())

    def list_builtin_mappings(self) -> List[str]:
        """Get names of repos with built-in mappings."""
        return list(self.BUILTIN_MAPPINGS.keys())

    def get_stats(self) -> dict:
        """Get statistics about mappings."""
        return {
            "custom_count": len(self._custom_mappings),
            "builtin_count": len(self.BUILTIN_MAPPINGS),
            "custom_repos": list(self._custom_mappings.keys()),
            "builtin_repos": list(self.BUILTIN_MAPPINGS.keys())
        }
