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
from src.cache import CacheManager
from src.favorites import FavoritesManager
from src.label_mappings import LabelMappingManager
from src.history import HistoryManager, IssueStatus
from src.exporter import export_results
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


def run_analysis(
    prefs: dict,
    max_results: int = 5,
    use_cache: bool = True,
    show_confidence: bool = True,
    hide_seen: bool = False,
    track_history: bool = True,
    export_path: str = None
):
    """
    Run the full analysis pipeline.

    Pipeline:
    1. Search GitHub for matching issues
    2. (Optional) Filter out previously seen issues
    3. Analyze top issues with Claude (with caching!)
    4. Score and rank results
    5. Present to user
    6. Record viewed issues in history

    Args:
        prefs: User preferences dict
        max_results: Number of results to show
        use_cache: Whether to use caching (default True)
        show_confidence: Whether to show confidence breakdown (default True)
        hide_seen: Whether to filter out previously viewed issues
        track_history: Whether to record viewed issues in history
        export_path: If provided, save full results to this file (.json or .md)
    """

    # Initialize cache manager
    cache = CacheManager() if use_cache else None

    # Initialize history manager
    history = HistoryManager() if (hide_seen or track_history) else None

    # Initialize components (pass cache to analyzer)
    github = GitHubClient()
    analyzer = IssueAnalyzer(cache=cache)
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
    # Step 1.5: Filter out previously seen issues (if requested)
    # -------------------------------------------------------------------------
    original_count = len(issues)
    if hide_seen and history:
        # Convert issues to dicts for filtering
        issue_dicts = [
            {"repo_name": i.repo_name, "issue_id": i.id}
            for i in issues
        ]
        unseen_dicts = history.filter_unseen(issue_dicts)
        unseen_keys = {f"{d['repo_name']}#{d['issue_id']}" for d in unseen_dicts}

        # Filter original list
        issues = [i for i in issues if f"{i.repo_name}#{i.id}" in unseen_keys]

        filtered_count = original_count - len(issues)
        if filtered_count > 0:
            presenter.show_status(
                f"Filtered out {filtered_count} previously seen issues",
                style="dim"
            )

        if not issues:
            presenter.show_status(
                "All matching issues have been seen before. Use --no-hide-seen to show them.",
                style="yellow"
            )
            return

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
    presenter.present_results(
        top_results,
        prefs,
        show_confidence=show_confidence,
        history=history
    )

    # -------------------------------------------------------------------------
    # Step 5: Export Results (if requested)
    # -------------------------------------------------------------------------
    if export_path:
        export_results(ranked, prefs, export_path)
        console.print(f"\n[green]Results exported to {export_path}[/green]")

    # Offer to show more if available
    if len(ranked) > max_results:
        console.print(f"[dim]Showing top {max_results} of {len(ranked)} analyzed issues.[/dim]")
        show_more = Prompt.ask(
            "\nWould you like to see more results?",
            choices=["yes", "no"],
            default="no"
        )
        if show_more == "yes":
            presenter.present_results(
                ranked[max_results:max_results + 5],
                prefs,
                show_confidence=show_confidence,
                history=history
            )

    # -------------------------------------------------------------------------
    # Offer to save favorites
    # -------------------------------------------------------------------------
    _offer_save_favorites(ranked)

    # -------------------------------------------------------------------------
    # Record viewed issues in history
    # -------------------------------------------------------------------------
    if track_history and history:
        for scored in ranked:
            history.record_view(
                issue_id=scored.issue.id,
                repo_name=scored.issue.repo_name,
                title=scored.issue.title,
                difficulty=scored.analysis.difficulty,
                url=scored.issue.url
            )
        console.print(f"[dim]Recorded {len(ranked)} issues in history.[/dim]")

    # -------------------------------------------------------------------------
    # Show Cache Statistics
    # -------------------------------------------------------------------------
    if cache:
        stats = cache.get_stats()
        llm_stats = stats["llm"]

        if llm_stats["hits"] > 0 or llm_stats["misses"] > 0:
            console.print()
            console.print(
                f"[dim]Cache: {llm_stats['hits']} hits, {llm_stats['misses']} API calls "
                f"(saved ~${llm_stats['hits'] * 0.003:.3f} in API costs)[/dim]"
            )


def _offer_save_favorites(ranked: list):
    """Offer to save issues to favorites after displaying results."""
    from src.scorer import ScoredIssue

    if not ranked:
        return

    console.print()
    save_choice = Prompt.ask(
        "Would you like to save any issues to favorites?",
        choices=["yes", "no"],
        default="no"
    )

    if save_choice != "yes":
        return

    favorites = FavoritesManager()

    # Show numbered list for selection
    console.print("\n[bold]Enter the numbers of issues to save (comma-separated):[/bold]")
    for i, scored in enumerate(ranked, 1):
        is_fav = favorites.is_favorite(scored.issue.repo_name, scored.issue.id)
        fav_marker = " [green](already saved)[/green]" if is_fav else ""
        console.print(f"  {i}. {scored.issue.repo_name}#{scored.issue.id}: {scored.issue.title[:50]}...{fav_marker}")

    selection = Prompt.ask("\nEnter numbers (e.g., 1,3,5) or 'all'", default="")

    if not selection:
        return

    # Parse selection
    indices = []
    if selection.lower() == "all":
        indices = list(range(len(ranked)))
    else:
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(",")]
        except ValueError:
            console.print("[red]Invalid input. Use numbers separated by commas.[/red]")
            return

    # Optional notes
    notes = Prompt.ask("Add notes to these favorites (optional)", default="")

    # Save selected issues
    saved_count = 0
    for idx in indices:
        if 0 <= idx < len(ranked):
            scored: ScoredIssue = ranked[idx]
            issue = scored.issue
            analysis = scored.analysis

            if not favorites.is_favorite(issue.repo_name, issue.id):
                favorites.add(
                    issue_id=issue.id,
                    repo_name=issue.repo_name,
                    title=issue.title,
                    url=issue.url,
                    difficulty=analysis.difficulty,
                    estimated_time=analysis.estimated_time,
                    summary=analysis.summary,
                    notes=notes
                )
                saved_count += 1

    if saved_count > 0:
        console.print(f"\n[green]Saved {saved_count} issue(s) to favorites![/green]")
        console.print("[dim]Use 'python main.py favorites list' to view them.[/dim]")


@app.command()
def find(
    topic: str = typer.Option(None, "--topic", "-t", help="Topic area (ai, web, backend, devops, mobile, data, security, any)"),
    language: str = typer.Option(None, "--language", "-l", help="Programming language"),
    skill: str = typer.Option(None, "--skill", "-s", help="Skill level (beginner, intermediate, advanced)"),
    time: str = typer.Option(None, "--time", "-T", help="Available time (quick_win, half_day, full_day, weekend, deep_dive)"),
    results: int = typer.Option(5, "--results", "-n", help="Number of results to show"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-I", help="Use interactive prompts"),
    use_cache: bool = typer.Option(True, "--cache/--no-cache", help="Use caching to reduce API calls"),
    show_confidence: bool = typer.Option(True, "--confidence/--no-confidence", help="Show confidence score breakdown"),
    hide_seen: bool = typer.Option(False, "--hide-seen", "-H", help="Hide issues you've already viewed"),
    track_history: bool = typer.Option(True, "--track/--no-track", help="Track viewed issues in history"),
    export: str = typer.Option(None, "--export", "-e", help="Export results to file (.json or .md)")
):
    """
    Find GitHub issues matching your preferences.

    Run without arguments for interactive mode, or pass all options for CLI mode.

    Caching is enabled by default. Use --no-cache to force fresh API calls.

    The confidence breakdown shows:
    - How well each factor matches your preferences
    - AI confidence level for each assessment (high/medium/low)

    History tracking:
    - By default, viewed issues are recorded in history
    - Use --hide-seen to filter out previously viewed issues
    - Use --no-track to disable history recording

    Export:
    - Use --export results.json to save as JSON
    - Use --export results.md to save as Markdown
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

    run_analysis(
        prefs,
        max_results=results,
        use_cache=use_cache,
        show_confidence=show_confidence,
        hide_seen=hide_seen,
        track_history=track_history,
        export_path=export
    )


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

    # Check cache
    cache = CacheManager()
    stats = cache.get_stats()
    console.print(f"\n[bold]Cache Status:[/bold]")
    console.print(f"  Size: {stats['cache_size_mb']} MB")
    console.print(f"  Location: .cache/")

    console.print()


@app.command()
def cache(
    action: str = typer.Argument(
        "stats",
        help="Action: 'stats' to show statistics, 'clear' to clear cache"
    )
):
    """
    Manage the cache for API responses.

    The cache stores:
    - GitHub search results (15 min TTL)
    - Claude analysis results (24 hour TTL)

    This reduces API costs and speeds up repeated searches.
    """

    cache_manager = CacheManager()

    if action == "stats":
        stats = cache_manager.get_stats()

        console.print("\n[bold blue]Cache Statistics[/bold blue]\n")

        console.print("[bold]LLM Analysis Cache:[/bold]")
        console.print(f"  Hits: {stats['llm']['hits']}")
        console.print(f"  Misses: {stats['llm']['misses']}")
        console.print(f"  Hit Rate: {stats['llm']['hit_rate']:.1%}")

        console.print(f"\n[bold]GitHub Search Cache:[/bold]")
        console.print(f"  Hits: {stats['github']['hits']}")
        console.print(f"  Misses: {stats['github']['misses']}")
        console.print(f"  Hit Rate: {stats['github']['hit_rate']:.1%}")

        console.print(f"\n[bold]Total Size:[/bold] {stats['cache_size_mb']} MB")

        if stats['llm']['hits'] > 0:
            estimated_savings = stats['llm']['hits'] * 0.003  # ~$0.003 per analysis
            console.print(f"[green]Estimated savings: ~${estimated_savings:.2f}[/green]")

        console.print()

    elif action == "clear":
        confirm = Prompt.ask(
            "Are you sure you want to clear the cache?",
            choices=["yes", "no"],
            default="no"
        )
        if confirm == "yes":
            cache_manager.clear_all()
            console.print("[green]Cache cleared successfully![/green]")
        else:
            console.print("[yellow]Cache clear cancelled.[/yellow]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Use 'stats' or 'clear'")


# =============================================================================
# FAVORITES COMMANDS
# =============================================================================

@app.command()
def favorites(
    action: str = typer.Argument(
        "list",
        help="Action: 'list', 'stats', or 'clear'"
    ),
    status_filter: str = typer.Option(
        None, "--status", "-s",
        help="Filter by status: saved, in_progress, completed, abandoned"
    ),
    tag_filter: str = typer.Option(
        None, "--tag", "-t",
        help="Filter by tag"
    )
):
    """
    Manage your saved favorite issues.

    Actions:
    - list: View all saved favorites (default)
    - stats: View statistics about your favorites
    - clear: Remove all favorites

    Examples:
        python main.py favorites                    # List all
        python main.py favorites list --status in_progress
        python main.py favorites stats
    """
    from rich.table import Table
    from rich import box

    fav_manager = FavoritesManager()

    if action == "list":
        # Get favorites (with optional filters)
        if status_filter:
            favs = fav_manager.list_by_status(status_filter)
            title = f"Favorites (status: {status_filter})"
        elif tag_filter:
            favs = fav_manager.list_by_tag(tag_filter)
            title = f"Favorites (tag: {tag_filter})"
        else:
            favs = fav_manager.list_all()
            title = "All Favorites"

        if not favs:
            console.print("\n[yellow]No favorites found.[/yellow]")
            console.print("[dim]Use 'python main.py find' to search and save issues.[/dim]\n")
            return

        # Display as table
        table = Table(title=title, box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("Repository", style="cyan")
        table.add_column("Title", max_width=40)
        table.add_column("Difficulty", width=12)
        table.add_column("Time", width=12)
        table.add_column("Status", width=12)
        table.add_column("Tags", max_width=20)

        for i, fav in enumerate(favs, 1):
            # Color-code status
            status_colors = {
                "saved": "white",
                "in_progress": "yellow",
                "completed": "green",
                "abandoned": "red"
            }
            status_style = status_colors.get(fav.status, "white")

            # Color-code difficulty
            diff_colors = {
                "beginner": "green",
                "intermediate": "yellow",
                "advanced": "red"
            }
            diff_style = diff_colors.get(fav.difficulty.lower(), "white")

            table.add_row(
                str(i),
                f"{fav.repo_name}#{fav.issue_id}",
                fav.title[:40] + "..." if len(fav.title) > 40 else fav.title,
                f"[{diff_style}]{fav.difficulty}[/{diff_style}]",
                fav.estimated_time.replace("_", " "),
                f"[{status_style}]{fav.status}[/{status_style}]",
                ", ".join(fav.tags) if fav.tags else "-"
            )

        console.print()
        console.print(table)
        console.print()
        console.print("[dim]Use 'python main.py favorite-update <repo>#<id>' to update status or notes[/dim]")

    elif action == "stats":
        stats = fav_manager.get_stats()

        console.print("\n[bold blue]Favorites Statistics[/bold blue]\n")
        console.print(f"[bold]Total saved:[/bold] {stats['total']}")

        if stats['by_status']:
            console.print("\n[bold]By Status:[/bold]")
            for status, count in stats['by_status'].items():
                console.print(f"  {status}: {count}")

        if stats['by_difficulty']:
            console.print("\n[bold]By Difficulty:[/bold]")
            for diff, count in stats['by_difficulty'].items():
                console.print(f"  {diff}: {count}")

        if stats['tags']:
            console.print(f"\n[bold]Tags:[/bold] {', '.join(stats['tags'])}")

        console.print()

    elif action == "clear":
        if fav_manager.count() == 0:
            console.print("[yellow]No favorites to clear.[/yellow]")
            return

        confirm = Prompt.ask(
            f"Are you sure you want to delete all {fav_manager.count()} favorites?",
            choices=["yes", "no"],
            default="no"
        )
        if confirm == "yes":
            # Clear by removing all
            for fav in fav_manager.list_all():
                fav_manager.remove(fav.repo_name, fav.issue_id)
            console.print("[green]All favorites cleared.[/green]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Use 'list', 'stats', or 'clear'")


@app.command()
def favorite_update(
    issue_ref: str = typer.Argument(
        ...,
        help="Issue reference in format 'owner/repo#number' (e.g., 'facebook/react#123')"
    ),
    status: str = typer.Option(
        None, "--status", "-s",
        help="New status: saved, in_progress, completed, abandoned"
    ),
    notes: str = typer.Option(
        None, "--notes", "-n",
        help="Update notes for this favorite"
    ),
    add_tag: str = typer.Option(
        None, "--add-tag",
        help="Add a tag to this favorite"
    ),
    remove_tag: str = typer.Option(
        None, "--remove-tag",
        help="Remove a tag from this favorite"
    )
):
    """
    Update a saved favorite issue.

    Examples:
        python main.py favorite-update facebook/react#123 --status in_progress
        python main.py favorite-update owner/repo#456 --notes "Started working on this"
        python main.py favorite-update owner/repo#789 --add-tag "weekend-project"
    """
    # Parse issue reference
    try:
        repo_part, issue_num = issue_ref.rsplit("#", 1)
        issue_id = int(issue_num)
        repo_name = repo_part
    except (ValueError, IndexError):
        console.print("[red]Invalid format. Use 'owner/repo#number'[/red]")
        return

    fav_manager = FavoritesManager()

    # Check if favorite exists
    if not fav_manager.is_favorite(repo_name, issue_id):
        console.print(f"[red]Issue {issue_ref} is not in favorites.[/red]")
        return

    # Apply updates
    updates_made = []

    if status:
        try:
            fav_manager.update_status(repo_name, issue_id, status)
            updates_made.append(f"status → {status}")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            return

    if notes is not None:
        fav_manager.update_notes(repo_name, issue_id, notes)
        updates_made.append("notes updated")

    if add_tag:
        fav_manager.add_tag(repo_name, issue_id, add_tag)
        updates_made.append(f"tag '{add_tag}' added")

    if remove_tag:
        fav_manager.remove_tag(repo_name, issue_id, remove_tag)
        updates_made.append(f"tag '{remove_tag}' removed")

    if updates_made:
        console.print(f"[green]Updated {issue_ref}: {', '.join(updates_made)}[/green]")
    else:
        console.print("[yellow]No updates specified. Use --status, --notes, --add-tag, or --remove-tag[/yellow]")


@app.command()
def favorite_show(
    issue_ref: str = typer.Argument(
        ...,
        help="Issue reference in format 'owner/repo#number'"
    )
):
    """
    Show details of a saved favorite.

    Example:
        python main.py favorite-show facebook/react#123
    """
    from rich.panel import Panel

    # Parse issue reference
    try:
        repo_part, issue_num = issue_ref.rsplit("#", 1)
        issue_id = int(issue_num)
        repo_name = repo_part
    except (ValueError, IndexError):
        console.print("[red]Invalid format. Use 'owner/repo#number'[/red]")
        return

    fav_manager = FavoritesManager()
    fav = fav_manager.get(repo_name, issue_id)

    if not fav:
        console.print(f"[red]Issue {issue_ref} is not in favorites.[/red]")
        return

    # Display detailed view
    content_lines = [
        f"[bold]Repository:[/bold] {fav.repo_name}",
        f"[bold]Issue #:[/bold] {fav.issue_id}",
        f"[bold]Title:[/bold] {fav.title}",
        "",
        f"[bold]Difficulty:[/bold] {fav.difficulty}",
        f"[bold]Estimated Time:[/bold] {fav.estimated_time.replace('_', ' ')}",
        f"[bold]Status:[/bold] {fav.status}",
        "",
        f"[bold]Summary:[/bold]",
        f"[italic]{fav.summary}[/italic]",
        "",
        f"[bold]Tags:[/bold] {', '.join(fav.tags) if fav.tags else 'None'}",
        f"[bold]Notes:[/bold] {fav.notes if fav.notes else 'None'}",
        "",
        f"[bold]Saved at:[/bold] {fav.saved_at[:10]}",
        f"[bold]URL:[/bold] [link={fav.url}]{fav.url}[/link]"
    ]

    panel = Panel(
        "\n".join(content_lines),
        title=f"[bold]{fav.repo_name}#{fav.issue_id}[/bold]",
        border_style="blue"
    )

    console.print()
    console.print(panel)
    console.print()


@app.command()
def favorite_remove(
    issue_ref: str = typer.Argument(
        ...,
        help="Issue reference in format 'owner/repo#number'"
    )
):
    """
    Remove an issue from favorites.

    Example:
        python main.py favorite-remove facebook/react#123
    """
    # Parse issue reference
    try:
        repo_part, issue_num = issue_ref.rsplit("#", 1)
        issue_id = int(issue_num)
        repo_name = repo_part
    except (ValueError, IndexError):
        console.print("[red]Invalid format. Use 'owner/repo#number'[/red]")
        return

    fav_manager = FavoritesManager()

    if fav_manager.remove(repo_name, issue_id):
        console.print(f"[green]Removed {issue_ref} from favorites.[/green]")
    else:
        console.print(f"[yellow]Issue {issue_ref} was not in favorites.[/yellow]")


# =============================================================================
# HISTORY COMMANDS
# =============================================================================

@app.command()
def history(
    action: str = typer.Argument(
        "list",
        help="Action: 'list', 'stats', 'recent', or 'clear'"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show"),
    status_filter: str = typer.Option(None, "--status", "-s", help="Filter by status")
):
    """
    View and manage your issue viewing history.

    The history tracks all issues you've viewed in search results.

    Actions:
    - list: Show recent history (default)
    - stats: Show statistics about your history
    - recent: Show issues from the last 7 days
    - clear: Clear all history

    Examples:
        python main.py history                      # List recent
        python main.py history stats                # Show statistics
        python main.py history list --status attempted
        python main.py history clear
    """
    from rich.table import Table
    from rich import box

    hist = HistoryManager()

    if action == "list":
        # Get entries
        if status_filter:
            try:
                status = IssueStatus(status_filter)
                entries = hist.list_by_status(status)
                title = f"History (status: {status_filter})"
            except ValueError:
                console.print(f"[red]Invalid status: {status_filter}[/red]")
                console.print(f"Valid statuses: {', '.join(s.value for s in IssueStatus)}")
                return
        else:
            entries = hist.list_all(limit=limit)
            title = f"Recent History (last {limit})"

        if not entries:
            console.print("\n[yellow]No history found.[/yellow]")
            console.print("[dim]History is recorded when you view search results.[/dim]\n")
            return

        table = Table(title=title, box=box.ROUNDED)
        table.add_column("Issue", style="cyan", max_width=40)
        table.add_column("Difficulty", width=12)
        table.add_column("Status", width=12)
        table.add_column("Views", width=6, justify="right")
        table.add_column("Last Seen", width=12)

        status_colors = {
            "viewed": "dim",
            "interested": "cyan",
            "attempted": "yellow",
            "completed": "green",
            "abandoned": "red",
            "skipped": "dim"
        }

        for entry in entries[:limit]:
            status_color = status_colors.get(entry.status, "white")

            # Format date
            last_seen = entry.last_seen[:10] if entry.last_seen else "?"

            table.add_row(
                f"{entry.repo_name}#{entry.issue_id}",
                entry.difficulty or "-",
                f"[{status_color}]{entry.status}[/{status_color}]",
                str(entry.view_count),
                last_seen
            )

        console.print()
        console.print(table)
        console.print()

    elif action == "stats":
        stats = hist.get_stats()

        console.print("\n[bold blue]History Statistics[/bold blue]\n")

        console.print(f"[bold]Total Issues Viewed:[/bold] {stats['total']}")
        console.print(f"[bold]This Week:[/bold] {stats['recent_week']}")
        console.print(f"[bold]This Month:[/bold] {stats['recent_month']}")

        if stats['by_status']:
            console.print("\n[bold]By Status:[/bold]")
            for status, count in sorted(stats['by_status'].items()):
                console.print(f"  {status}: {count}")

        if stats['by_difficulty']:
            console.print("\n[bold]By Difficulty:[/bold]")
            for diff, count in sorted(stats['by_difficulty'].items()):
                console.print(f"  {diff}: {count}")

        if stats['completion_rate'] > 0:
            console.print(f"\n[bold]Completion Rate:[/bold] {stats['completion_rate']:.1%}")

        if stats['most_viewed']:
            console.print("\n[bold]Most Viewed Issues:[/bold]")
            for entry in stats['most_viewed'][:3]:
                console.print(f"  {entry.repo_name}#{entry.issue_id} ({entry.view_count} views)")

        console.print()

    elif action == "recent":
        entries = hist.list_recent(days=7)

        if not entries:
            console.print("\n[yellow]No issues viewed in the last 7 days.[/yellow]\n")
            return

        console.print(f"\n[bold]Issues viewed in the last 7 days:[/bold] {len(entries)}\n")

        for entry in entries[:limit]:
            status_indicator = {
                "completed": "[green]+[/green]",
                "attempted": "[yellow]~[/yellow]",
                "skipped": "[dim]x[/dim]",
                "viewed": "[dim].[/dim]"
            }.get(entry.status, " ")

            console.print(f"  {status_indicator} {entry.repo_name}#{entry.issue_id}: {entry.title[:50]}...")

        console.print()

    elif action == "clear":
        count = hist.count()
        if count == 0:
            console.print("[yellow]History is already empty.[/yellow]")
            return

        confirm = Prompt.ask(
            f"Are you sure you want to clear all {count} history entries?",
            choices=["yes", "no"],
            default="no"
        )

        if confirm == "yes":
            hist.clear_all()
            console.print("[green]History cleared.[/green]")
        else:
            console.print("[yellow]Cancelled.[/yellow]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Use: list, stats, recent, or clear")


@app.command()
def history_update(
    issue_ref: str = typer.Argument(..., help="Issue reference (owner/repo#number)"),
    status: str = typer.Argument(..., help="New status: viewed, interested, attempted, completed, abandoned, skipped")
):
    """
    Update the status of an issue in history.

    Status progression:
    - viewed: Just saw it in results
    - interested: Clicked/investigated further
    - attempted: Started working on it
    - completed: Submitted PR / finished
    - abandoned: Gave up on it
    - skipped: Not interested

    Examples:
        python main.py history-update facebook/react#123 attempted
        python main.py history-update owner/repo#456 completed
    """
    # Parse issue reference
    try:
        repo_part, issue_num = issue_ref.rsplit("#", 1)
        issue_id = int(issue_num)
        repo_name = repo_part
    except (ValueError, IndexError):
        console.print("[red]Invalid format. Use 'owner/repo#number'[/red]")
        return

    # Validate status
    try:
        new_status = IssueStatus(status)
    except ValueError:
        console.print(f"[red]Invalid status: {status}[/red]")
        console.print(f"Valid statuses: {', '.join(s.value for s in IssueStatus)}")
        return

    hist = HistoryManager()

    if hist.update_status(repo_name, issue_id, new_status):
        console.print(f"[green]Updated {issue_ref} status to '{status}'[/green]")
    else:
        console.print(f"[yellow]Issue {issue_ref} not found in history.[/yellow]")
        console.print("[dim]Issues are added to history when you view search results.[/dim]")


# =============================================================================
# LABEL MAPPING COMMANDS
# =============================================================================

@app.command()
def labels(
    action: str = typer.Argument(
        "list",
        help="Action: 'list' to show all mappings, 'builtin' to show pre-configured repos"
    )
):
    """
    Manage custom label-to-difficulty mappings for repositories.

    Different repos use different labels for difficulty:
    - rust-lang/rust uses "E-easy", "E-medium", "E-hard"
    - godotengine/godot uses "junior job"
    - Most repos use "good first issue"

    Custom mappings help the analyzer correctly interpret these labels.

    Examples:
        python main.py labels              # List all custom mappings
        python main.py labels builtin      # Show pre-configured repos
    """
    from rich.table import Table
    from rich import box

    mapper = LabelMappingManager()

    if action == "list":
        custom = mapper.list_custom_mappings()

        if not custom:
            console.print("\n[yellow]No custom label mappings defined.[/yellow]")
            console.print("[dim]Use 'python main.py label-add' to create one.[/dim]")
            console.print("[dim]Use 'python main.py labels builtin' to see pre-configured repos.[/dim]\n")
            return

        table = Table(title="Custom Label Mappings", box=box.ROUNDED)
        table.add_column("Repository", style="cyan")
        table.add_column("Beginner Labels", style="green")
        table.add_column("Intermediate Labels", style="yellow")
        table.add_column("Advanced Labels", style="red")

        for mapping in custom:
            table.add_row(
                mapping.repo_name,
                ", ".join(mapping.beginner_labels) or "-",
                ", ".join(mapping.intermediate_labels) or "-",
                ", ".join(mapping.advanced_labels) or "-"
            )

        console.print()
        console.print(table)
        console.print()

    elif action == "builtin":
        builtin_repos = mapper.list_builtin_mappings()

        console.print("\n[bold blue]Pre-configured Label Mappings[/bold blue]")
        console.print("[dim]These repos have known non-standard labels.[/dim]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Repository", style="cyan")
        table.add_column("Beginner", style="green")
        table.add_column("Intermediate", style="yellow")
        table.add_column("Notes", style="dim")

        for repo_name in builtin_repos:
            mapping = mapper.get_mapping(repo_name)
            table.add_row(
                repo_name,
                ", ".join(mapping.beginner_labels[:2]) + ("..." if len(mapping.beginner_labels) > 2 else ""),
                ", ".join(mapping.intermediate_labels[:2]) + ("..." if len(mapping.intermediate_labels) > 2 else ""),
                mapping.notes
            )

        console.print(table)
        console.print()
        console.print("[dim]These mappings are used automatically. Use 'label-import' to customize them.[/dim]\n")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")


@app.command()
def label_add(
    repo: str = typer.Argument(..., help="Repository name (e.g., 'owner/repo')"),
    difficulty: str = typer.Argument(..., help="Difficulty level: beginner, intermediate, or advanced"),
    label: str = typer.Argument(..., help="The GitHub label to map")
):
    """
    Add a label mapping for a repository.

    Examples:
        python main.py label-add rust-lang/rust beginner E-easy
        python main.py label-add myorg/myrepo intermediate "help wanted"
    """
    if difficulty not in ["beginner", "intermediate", "advanced"]:
        console.print(f"[red]Invalid difficulty: {difficulty}[/red]")
        console.print("Must be: beginner, intermediate, or advanced")
        return

    mapper = LabelMappingManager()
    mapper.add_label(repo, difficulty, label)

    console.print(f"[green]Added '{label}' as {difficulty} label for {repo}[/green]")


@app.command()
def label_remove(
    repo: str = typer.Argument(..., help="Repository name"),
    difficulty: str = typer.Argument(..., help="Difficulty level"),
    label: str = typer.Argument(..., help="Label to remove")
):
    """
    Remove a label mapping from a repository.

    Example:
        python main.py label-remove rust-lang/rust beginner E-easy
    """
    mapper = LabelMappingManager()

    if mapper.remove_label(repo, difficulty, label):
        console.print(f"[green]Removed '{label}' from {difficulty} labels for {repo}[/green]")
    else:
        console.print(f"[yellow]Label not found or no custom mapping for {repo}[/yellow]")


@app.command()
def label_show(
    repo: str = typer.Argument(..., help="Repository name to show mapping for")
):
    """
    Show label mapping for a specific repository.

    Example:
        python main.py label-show rust-lang/rust
    """
    from rich.panel import Panel

    mapper = LabelMappingManager()
    mapping = mapper.get_mapping(repo)

    # Determine source
    if mapper.has_custom_mapping(repo):
        source = "[green]Custom mapping[/green]"
    elif mapper.has_builtin_mapping(repo):
        source = "[cyan]Built-in mapping[/cyan]"
    else:
        source = "[dim]Default mapping[/dim]"

    content = f"""[bold]Source:[/bold] {source}

[bold]Beginner Labels:[/bold]
  {', '.join(mapping.beginner_labels) if mapping.beginner_labels else '[dim]None[/dim]'}

[bold]Intermediate Labels:[/bold]
  {', '.join(mapping.intermediate_labels) if mapping.intermediate_labels else '[dim]None[/dim]'}

[bold]Advanced Labels:[/bold]
  {', '.join(mapping.advanced_labels) if mapping.advanced_labels else '[dim]None[/dim]'}

[bold]Notes:[/bold] {mapping.notes if mapping.notes else '[dim]None[/dim]'}"""

    panel = Panel(content, title=f"[bold]{repo}[/bold]", border_style="blue")

    console.print()
    console.print(panel)
    console.print()


@app.command()
def label_import(
    repo: str = typer.Argument(..., help="Repository name to import built-in mapping for")
):
    """
    Import a built-in mapping as a custom mapping (so you can modify it).

    Example:
        python main.py label-import rust-lang/rust
    """
    mapper = LabelMappingManager()

    if mapper.import_builtin(repo):
        console.print(f"[green]Imported built-in mapping for {repo} as custom mapping.[/green]")
        console.print("[dim]You can now modify it with label-add and label-remove.[/dim]")
    else:
        console.print(f"[yellow]No built-in mapping found for {repo}[/yellow]")
        console.print("[dim]Use 'python main.py labels builtin' to see available repos.[/dim]")


@app.command()
def label_delete(
    repo: str = typer.Argument(..., help="Repository to remove custom mapping for")
):
    """
    Delete the custom mapping for a repository entirely.

    Example:
        python main.py label-delete myorg/myrepo
    """
    mapper = LabelMappingManager()

    if mapper.remove_mapping(repo):
        console.print(f"[green]Removed custom mapping for {repo}[/green]")
        if mapper.has_builtin_mapping(repo):
            console.print(f"[dim]Will fall back to built-in mapping.[/dim]")
        else:
            console.print(f"[dim]Will fall back to default labels.[/dim]")
    else:
        console.print(f"[yellow]No custom mapping found for {repo}[/yellow]")


if __name__ == "__main__":
    app()
