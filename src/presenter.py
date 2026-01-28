"""
Results presenter using Rich for beautiful terminal output.

Rich is a Python library for rich text and beautiful formatting in the terminal.
It provides: tables, panels, colors, progress bars, and more.
"""

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from typing import Optional, TYPE_CHECKING

from .config import TIME_LABELS
from .scorer import ScoredIssue, ScoreComponent

if TYPE_CHECKING:
    from .history import HistoryManager


class ResultsPresenter:
    """Presents analyzed issues in a beautiful terminal format."""

    def __init__(self):
        self.console = Console()

        # Visual indicators for difficulty levels
        self.difficulty_display = {
            "beginner": ("[green]Beginner[/green]", "beginner"),
            "intermediate": ("[yellow]Intermediate[/yellow]", "intermediate"),
            "advanced": ("[red]Advanced[/red]", "advanced")
        }

        # Visual indicators for time estimates
        self.time_display = {
            "quick_win": "[cyan]< 2 hours[/cyan]",
            "half_day": "[cyan]2-4 hours[/cyan]",
            "full_day": "[cyan]4-8 hours[/cyan]",
            "weekend": "[cyan]1-3 days[/cyan]",
            "deep_dive": "[cyan]1+ week[/cyan]"
        }

    def show_header(self, user_prefs: dict, total_found: int):
        """Display search header with user preferences."""

        self.console.print()
        header_text = (
            f"[bold]GitHub Issue Analyzer[/bold]\n\n"
            f"Topic: [cyan]{user_prefs['topic']}[/cyan] | "
            f"Language: [cyan]{user_prefs['language']}[/cyan] | "
            f"Level: [cyan]{user_prefs['skill']}[/cyan] | "
            f"Time: [cyan]{user_prefs['time']}[/cyan]\n\n"
            f"Found [green]{total_found}[/green] matching issues"
        )

        self.console.print(Panel(
            header_text,
            title="[bold blue]Search Results[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        ))

    def present_results(
        self,
        results: List[ScoredIssue],
        user_prefs: dict,
        show_confidence: bool = True,
        history: Optional["HistoryManager"] = None
    ):
        """Display the ranked results."""

        self.show_header(user_prefs, len(results))

        if not results:
            self.console.print("\n[yellow]No matching issues found. Try broadening your search criteria.[/yellow]\n")
            return

        self.console.print()

        for rank, scored_issue in enumerate(results, 1):
            # Check history status if available
            history_status = None
            if history:
                history_status = history.get_status(
                    scored_issue.issue.repo_name,
                    scored_issue.issue.id
                )

            self._present_single_issue(
                rank,
                scored_issue,
                show_confidence=show_confidence,
                history_status=history_status
            )

    def _render_score_bar(self, score: float, width: int = 10) -> str:
        """
        Render a visual progress bar for a score.

        Example: _render_score_bar(0.7, 10) -> "███████░░░"
        """
        filled = int(score * width)
        empty = width - filled

        # Color based on score
        if score >= 0.8:
            color = "green"
        elif score >= 0.6:
            color = "yellow"
        elif score >= 0.4:
            color = "orange3"
        else:
            color = "red"

        bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"
        return bar

    def _render_confidence_badge(self, confidence: str) -> str:
        """Render a confidence indicator badge."""
        confidence = confidence.lower() if confidence else "medium"

        badges = {
            "high": "[green]●[/green]",      # Solid circle = high confidence
            "medium": "[yellow]◐[/yellow]",  # Half circle = medium confidence
            "low": "[red]○[/red]"            # Empty circle = low confidence
        }

        return badges.get(confidence, badges["medium"])

    def _render_score_breakdown(self, components: list, show_details: bool = True) -> str:
        """
        Render the score breakdown as a visual tree.

        Example output:
        ┌─ Score Breakdown ─────────────────────────────┐
        │ Difficulty Match  ████████░░  80%  ● high     │
        │ Time Match        ██████████ 100%  ● high     │
        │ Repo Health       ██████░░░░  60%  ◐ medium   │
        │ Issue Clarity     █████████░  90%  ● high     │
        └───────────────────────────────────────────────┘
        """
        lines = []

        for comp in components:
            bar = self._render_score_bar(comp.score)
            badge = self._render_confidence_badge(comp.confidence)
            score_pct = f"{comp.score * 100:3.0f}%"

            # Pad component name to align bars
            name_padded = f"{comp.name:<16}"

            line = f"  {name_padded} {bar} {score_pct} {badge}"

            if show_details and comp.reasoning:
                # Add reasoning on next line, indented
                lines.append(line)
                lines.append(f"    [dim]{comp.reasoning}[/dim]")
            else:
                lines.append(line)

        return "\n".join(lines)

    def _render_history_badge(self, status: Optional[str]) -> str:
        """Render a badge showing history status."""
        if not status:
            return ""

        badges = {
            "viewed": "[dim](seen before)[/dim]",
            "interested": "[cyan](interested)[/cyan]",
            "attempted": "[yellow](in progress)[/yellow]",
            "completed": "[green](completed)[/green]",
            "abandoned": "[red](abandoned)[/red]",
            "skipped": "[dim](skipped)[/dim]"
        }

        return badges.get(status, "")

    def _present_single_issue(
        self,
        rank: int,
        scored_issue: ScoredIssue,
        show_confidence: bool = True,
        history_status: Optional[str] = None
    ):
        """Present a single issue in a panel."""

        issue = scored_issue.issue
        analysis = scored_issue.analysis
        score = scored_issue.score

        # Get display strings
        difficulty_str = self.difficulty_display.get(
            analysis.difficulty.lower(),
            (f"[white]{analysis.difficulty}[/white]", analysis.difficulty)
        )[0]

        time_str = self.time_display.get(
            analysis.estimated_time.lower(),
            f"[cyan]{analysis.estimated_time}[/cyan]"
        )

        # Get confidence badge for overall score
        overall_confidence = getattr(scored_issue, 'overall_confidence', 'medium')
        confidence_badge = self._render_confidence_badge(overall_confidence)

        # Get history badge
        history_badge = self._render_history_badge(history_status)

        # Build content
        first_line = f"[bold]Difficulty:[/bold] {difficulty_str}    [bold]Time:[/bold] {time_str}"
        if history_badge:
            first_line += f"    {history_badge}"

        content_lines = [
            first_line,
            "",
            f"[bold]Summary:[/bold]",
            f"[italic]{analysis.summary}[/italic]",
            "",
            f"[bold]Technical Requirements:[/bold] {', '.join(analysis.technical_requirements)}",
        ]

        # Add score breakdown if we have components
        if show_confidence and hasattr(scored_issue, 'score_components') and scored_issue.score_components:
            content_lines.append("")
            content_lines.append("[bold]Score Breakdown:[/bold]")
            breakdown = self._render_score_breakdown(scored_issue.score_components, show_details=False)
            content_lines.append(breakdown)
            content_lines.append(f"  [dim]Confidence: {overall_confidence} {confidence_badge}[/dim]")

        content_lines.extend([
            "",
            f"[bold]Why this issue:[/bold]",
            f"[dim]{analysis.recommendation}[/dim]",
            "",
            f"[bold]Link:[/bold] [link={issue.url}]{issue.url}[/link]",
        ])

        content = "\n".join(content_lines)

        # Determine border color based on score
        if score >= 0.8:
            border_style = "green"
        elif score >= 0.6:
            border_style = "yellow"
        else:
            border_style = "white"

        # Truncate long titles
        title_display = issue.title if len(issue.title) <= 60 else issue.title[:57] + "..."

        panel = Panel(
            content,
            title=f"[bold]#{rank} {issue.repo_name}[/bold]",
            subtitle=f"[bold]{title_display}[/bold] | Match: [bold]{score:.0%}[/bold] {confidence_badge}",
            border_style=border_style,
            padding=(1, 2),
            box=box.ROUNDED
        )

        self.console.print(panel)
        self.console.print()

    def present_detailed_breakdown(self, scored_issue: ScoredIssue):
        """
        Present a detailed score breakdown for a single issue.

        This shows the full reasoning behind each score component.
        Useful for understanding why an issue got its score.
        """
        issue = scored_issue.issue

        self.console.print()
        self.console.print(f"[bold blue]Detailed Score Breakdown: {issue.repo_name}#{issue.id}[/bold blue]")
        self.console.print()

        if hasattr(scored_issue, 'score_components') and scored_issue.score_components:
            for comp in scored_issue.score_components:
                badge = self._render_confidence_badge(comp.confidence)
                bar = self._render_score_bar(comp.score, width=20)

                self.console.print(f"[bold]{comp.name}[/bold]")
                self.console.print(f"  Score: {bar} {comp.score:.0%}")
                self.console.print(f"  Weight: {comp.weight:.0%} of total → contributes {comp.weighted_score:.0%}")
                self.console.print(f"  Confidence: {comp.confidence} {badge}")
                self.console.print(f"  Reasoning: [italic]{comp.reasoning}[/italic]")
                self.console.print()

            # Overall
            overall_confidence = getattr(scored_issue, 'overall_confidence', 'medium')
            self.console.print(f"[bold]Overall Score:[/bold] {scored_issue.score:.0%}")
            self.console.print(f"[bold]Overall Confidence:[/bold] {overall_confidence}")
        else:
            self.console.print("[yellow]Detailed breakdown not available[/yellow]")

        self.console.print()

    def show_progress(self, current: int, total: int, message: str = ""):
        """Show progress during analysis."""
        truncated_msg = message[:50] + "..." if len(message) > 50 else message
        self.console.print(f"  Analyzing [{current}/{total}]: {truncated_msg}", end="\r")

    def show_status(self, message: str, style: str = "yellow"):
        """Show a status message."""
        self.console.print(f"[{style}]{message}[/{style}]")

    def clear_line(self):
        """Clear the current line (for progress updates)."""
        self.console.print(" " * 80, end="\r")
