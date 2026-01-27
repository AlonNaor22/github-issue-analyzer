"""
GitHub Issue Analyzer - Main CLI Entry Point

An AI-powered tool that helps developers find open-source contribution
opportunities matching their interests, skill level, and available time.

Usage:
    python main.py                    # Interactive mode
    python main.py --no-interactive   # Use command-line arguments
"""

import typer
from rich.console import Console
from rich.prompt import Prompt
from dotenv import load_dotenv

from src.github_client import GitHubClient
from src.analyzer import IssueAnalyzer
from src.scorer import IssueScorer
from src.presenter import ResultsPresenter
from src.config import ISSUES_TO_ANALYZE

# Load environment variables
load_dotenv()

# Initialize Typer app and Rich console
app = typer.Typer(
    name="github-issue-analyzer",
    help="Find GitHub issues matching your skills and available time."
)
console = Console()


def get_user_preferences_interactive() -> dict:
    """Gather user preferences through interactive prompts."""

    console.print("\n[bold blue]GitHub Issue Analyzer[/bold blue]")
    console.print("[dim]Find open-source issues matching your profile[/dim]\n")

    topic = Prompt.ask(
        "[bold]What topic interests you?[/bold]",
        choices=["ai", "web", "backend", "devops", "mobile", "data", "security", "any"],
        default="any"
    )

    language = Prompt.ask(
        "[bold]Preferred programming language?[/bold]",
        choices=["python", "javascript", "typescript", "rust", "go", "java", "any"],
        default="python"
    )

    skill = Prompt.ask(
        "[bold]Your skill level?[/bold]",
        choices=["beginner", "intermediate", "advanced"],
        default="beginner"
    )

    time = Prompt.ask(
        "[bold]How much time do you have?[/bold]",
        choices=["quick_win", "half_day", "full_day", "weekend", "deep_dive"],
        default="half_day"
    )

    return {
        "topic": topic,
        "language": language,
        "skill": skill,
        "time": time
    }


def run_analysis(prefs: dict, max_results: int = 5):
    """
    Run the full analysis pipeline.

    Pipeline:
    1. Search GitHub for matching issues
    2. Analyze top issues with Claude
    3. Score and rank results
    4. Present to user
    """

    # Initialize components
    github = GitHubClient()
    analyzer = IssueAnalyzer()
    scorer = IssueScorer()
    presenter = ResultsPresenter()

    # -------------------------------------------------------------------------
    # Step 1: Search GitHub
    # -------------------------------------------------------------------------
    presenter.show_status("\nSearching GitHub for matching issues...")

    issues = github.search_issues(
        topic=prefs["topic"],
        language=prefs["language"],
        difficulty=prefs["skill"],
    )

    if not issues:
        presenter.show_status(
            "No issues found matching your criteria. Try broadening your search.",
            style="red"
        )
        return

    presenter.show_status(f"Found {len(issues)} potential issues", style="green")

    # -------------------------------------------------------------------------
    # Step 2: Analyze with Claude
    # -------------------------------------------------------------------------
    presenter.show_status(f"\nAnalyzing top {min(len(issues), ISSUES_TO_ANALYZE)} issues with Claude...")

    # Only analyze top N issues to save API costs
    issues_to_analyze = issues[:ISSUES_TO_ANALYZE]

    def progress_callback(current, total, title):
        presenter.show_progress(current, total, title)

    analyzed = analyzer.analyze_batch(
        issues=issues_to_analyze,
        user_skill=prefs["skill"],
        user_time=prefs["time"],
        progress_callback=progress_callback
    )

    presenter.clear_line()

    if not analyzed:
        presenter.show_status(
            "Failed to analyze issues. Check your API key and try again.",
            style="red"
        )
        return

    presenter.show_status(f"Successfully analyzed {len(analyzed)} issues", style="green")

    # -------------------------------------------------------------------------
    # Step 3: Score and Rank
    # -------------------------------------------------------------------------
    ranked = scorer.rank_issues(
        analyzed_issues=analyzed,
        user_skill=prefs["skill"],
        user_time=prefs["time"]
    )

    # -------------------------------------------------------------------------
    # Step 4: Present Results
    # -------------------------------------------------------------------------
    top_results = ranked[:max_results]
    presenter.present_results(top_results, prefs)

    # Offer to show more if available
    if len(ranked) > max_results:
        console.print(f"[dim]Showing top {max_results} of {len(ranked)} analyzed issues.[/dim]")
        show_more = Prompt.ask(
            "\nWould you like to see more results?",
            choices=["yes", "no"],
            default="no"
        )
        if show_more == "yes":
            presenter.present_results(ranked[max_results:max_results + 5], prefs)


@app.command()
def find(
    topic: str = typer.Option(None, "--topic", "-t", help="Topic area (ai, web, backend, devops, mobile, data, security, any)"),
    language: str = typer.Option(None, "--language", "-l", help="Programming language"),
    skill: str = typer.Option(None, "--skill", "-s", help="Skill level (beginner, intermediate, advanced)"),
    time: str = typer.Option(None, "--time", "-T", help="Available time (quick_win, half_day, full_day, weekend, deep_dive)"),
    results: int = typer.Option(5, "--results", "-n", help="Number of results to show"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-I", help="Use interactive prompts")
):
    """
    Find GitHub issues matching your preferences.

    Run without arguments for interactive mode, or pass all options for CLI mode.
    """

    if interactive or not all([topic, language, skill, time]):
        # Interactive mode
        prefs = get_user_preferences_interactive()
    else:
        # CLI mode
        prefs = {
            "topic": topic,
            "language": language,
            "skill": skill,
            "time": time
        }

    run_analysis(prefs, max_results=results)


@app.command()
def check_setup():
    """
    Verify that API keys are configured correctly.
    """
    import os

    console.print("\n[bold]Checking setup...[/bold]\n")

    # Check GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        console.print("[green]GitHub Token: Configured[/green]")
        # Test the token
        try:
            client = GitHubClient()
            rate_limit = client.get_rate_limit_status()
            console.print(f"  Rate limit: {rate_limit['remaining']}/{rate_limit['limit']} requests remaining")
        except Exception as e:
            console.print(f"[yellow]  Warning: Could not verify token: {e}[/yellow]")
    else:
        console.print("[yellow]GitHub Token: Not configured (will use lower rate limits)[/yellow]")

    # Check Anthropic key
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        console.print("[green]Anthropic API Key: Configured[/green]")
    else:
        console.print("[red]Anthropic API Key: NOT CONFIGURED[/red]")
        console.print("  Set ANTHROPIC_API_KEY in your .env file")

    console.print()


if __name__ == "__main__":
    app()
