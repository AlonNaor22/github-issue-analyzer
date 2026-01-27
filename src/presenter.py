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

from .config import TIME_LABELS
from .scorer import ScoredIssue


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

    def present_results(self, results: List[ScoredIssue], user_prefs: dict):
        """Display the ranked results."""

        self.show_header(user_prefs, len(results))

        if not results:
            self.console.print("\n[yellow]No matching issues found. Try broadening your search criteria.[/yellow]\n")
            return

        self.console.print()

        for rank, scored_issue in enumerate(results, 1):
            self._present_single_issue(rank, scored_issue)

    def _present_single_issue(self, rank: int, scored_issue: ScoredIssue):
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

        # Build content
        content_lines = [
            f"[bold]Difficulty:[/bold] {difficulty_str}    [bold]Time:[/bold] {time_str}",
            "",
            f"[bold]Summary:[/bold]",
            f"[italic]{analysis.summary}[/italic]",
            "",
            f"[bold]Technical Requirements:[/bold] {', '.join(analysis.technical_requirements)}",
            "",
            f"[bold]Why this issue:[/bold]",
            f"[dim]{analysis.recommendation}[/dim]",
            "",
            f"[bold]Link:[/bold] [link={issue.url}]{issue.url}[/link]",
        ]

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
            subtitle=f"[bold]{title_display}[/bold] | Match: [bold]{score:.0%}[/bold]",
            border_style=border_style,
            padding=(1, 2),
            box=box.ROUNDED
        )

        self.console.print(panel)
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
