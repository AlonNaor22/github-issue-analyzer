"""
Results Exporter - Save analyzed results to JSON or Markdown files.

Supports two formats:
- JSON: Machine-readable, can be re-loaded for further processing
- Markdown: Human-readable report with formatted tables and details
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .scorer import ScoredIssue


def export_results(
    results: List[ScoredIssue],
    prefs: dict,
    filepath: str,
    fmt: str = None
):
    """
    Export ranked results to a file.

    Args:
        results: List of ScoredIssue objects to export
        prefs: User preferences dict (topic, language, skill, time)
        filepath: Output file path
        fmt: Format to use ('json' or 'md'). Auto-detected from extension if None.
    """
    path = Path(filepath)

    if fmt is None:
        ext = path.suffix.lower()
        if ext == ".json":
            fmt = "json"
        elif ext in (".md", ".markdown"):
            fmt = "md"
        else:
            fmt = "json"

    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        _export_json(results, prefs, path)
    else:
        _export_markdown(results, prefs, path)


def _export_json(results: List[ScoredIssue], prefs: dict, path: Path):
    """Export results as JSON."""
    data = {
        "exported_at": datetime.now().isoformat(),
        "preferences": prefs,
        "total_results": len(results),
        "results": [_scored_issue_to_dict(r) for r in results]
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _export_markdown(results: List[ScoredIssue], prefs: dict, path: Path):
    """Export results as a Markdown report."""
    lines = []

    lines.append("# GitHub Issue Analyzer Results")
    lines.append("")
    lines.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Topic:** {prefs.get('topic', 'any')} | "
                 f"**Language:** {prefs.get('language', 'any')} | "
                 f"**Skill:** {prefs.get('skill', 'any')} | "
                 f"**Time:** {prefs.get('time', 'any')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for rank, scored in enumerate(results, 1):
        issue = scored.issue
        analysis = scored.analysis

        lines.append(f"## #{rank} {issue.repo_name} — {issue.title}")
        lines.append("")
        lines.append(f"| Field | Value |")
        lines.append(f"|-------|-------|")
        lines.append(f"| **Match Score** | {scored.score:.0%} ({scored.overall_confidence} confidence) |")
        lines.append(f"| **Difficulty** | {analysis.difficulty} ({analysis.difficulty_confidence} confidence) |")
        lines.append(f"| **Estimated Time** | {analysis.estimated_time.replace('_', ' ')} ({analysis.time_confidence} confidence) |")
        lines.append(f"| **Clarity** | {analysis.clarity_score}/10 |")
        lines.append(f"| **Stars** | {issue.repo_stars:,} |")
        lines.append(f"| **Labels** | {', '.join(issue.labels) if issue.labels else 'None'} |")
        lines.append(f"| **Link** | {issue.url} |")
        lines.append("")
        lines.append(f"**Summary:** {analysis.summary}")
        lines.append("")
        lines.append(f"**Technical Requirements:** {', '.join(analysis.technical_requirements)}")
        lines.append("")
        lines.append(f"**Recommendation:** {analysis.recommendation}")
        lines.append("")

        if scored.score_components:
            lines.append("**Score Breakdown:**")
            lines.append("")
            lines.append("| Component | Score | Weight | Confidence |")
            lines.append("|-----------|-------|--------|------------|")
            for comp in scored.score_components:
                lines.append(f"| {comp.name} | {comp.score:.0%} | {comp.weight:.0%} | {comp.confidence} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _scored_issue_to_dict(scored: ScoredIssue) -> dict:
    """Convert a ScoredIssue to a serializable dict."""
    issue = scored.issue
    analysis = scored.analysis

    return {
        "score": round(scored.score, 4),
        "overall_confidence": scored.overall_confidence,
        "issue": {
            "id": issue.id,
            "title": issue.title,
            "url": issue.url,
            "repo_name": issue.repo_name,
            "repo_stars": issue.repo_stars,
            "labels": issue.labels,
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
            "comments_count": issue.comments_count,
        },
        "analysis": {
            "difficulty": analysis.difficulty,
            "difficulty_confidence": analysis.difficulty_confidence,
            "difficulty_reasoning": analysis.difficulty_reasoning,
            "estimated_time": analysis.estimated_time,
            "time_confidence": analysis.time_confidence,
            "time_reasoning": analysis.time_reasoning,
            "summary": analysis.summary,
            "technical_requirements": analysis.technical_requirements,
            "clarity_score": analysis.clarity_score,
            "clarity_reasoning": analysis.clarity_reasoning,
            "recommendation": analysis.recommendation,
        },
        "score_breakdown": [
            {
                "name": comp.name,
                "score": round(comp.score, 4),
                "weight": comp.weight,
                "weighted_score": round(comp.weighted_score, 4),
                "confidence": comp.confidence,
                "reasoning": comp.reasoning,
            }
            for comp in scored.score_components
        ],
    }
