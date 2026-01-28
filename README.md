# GitHub Issue Analyzer

An AI-powered CLI tool that helps developers find open-source contribution opportunities matching their interests, skill level, and available time.

## Features

### Core Features
- **Smart Search**: Query GitHub for open issues by topic and programming language
- **AI Analysis**: Uses Claude to assess actual difficulty, estimate completion time, and evaluate issue clarity
- **Personalized Matching**: Filters and ranks issues based on your skill level and available time
- **Beautiful Output**: Rich terminal interface with color-coded results

### Enhanced Features
- **Caching**: Reduce API calls and costs with intelligent caching of GitHub and LLM responses
- **Favorites**: Save interesting issues for later with notes and tags
- **Confidence Scores**: See detailed breakdowns of why issues match your criteria
- **Custom Label Mappings**: Configure repository-specific label interpretations
- **History Tracking**: Track viewed issues and filter out previously seen results

## How It Works

```
User Input → GitHub Search → AI Analysis → Scoring → Rich Output
     ↓            ↓              ↓           ↓          ↓
 Preferences   50 issues    Claude Haiku   Ranked    Panels with
 (topic,       fetched      analyzes top   by match  difficulty,
  language,    via API      20 issues      score     time, links
  skill, time)
```

1. **You provide preferences**: Topic, language, skill level, available time
2. **GitHub Search**: Finds open, unassigned issues matching your criteria
3. **Claude Analysis**: Each issue is analyzed for:
   - Actual difficulty (may differ from labels)
   - Realistic time estimate
   - Technical requirements
   - Clarity and actionability
4. **Smart Ranking**: Issues are scored and ranked by how well they match your profile
5. **Curated Results**: Top matches displayed with summaries and direct links

## Installation

### Prerequisites

- Python 3.9+
- GitHub account (for API token)
- Anthropic API key (for Claude)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/github-issue-analyzer.git
   cd github-issue-analyzer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your API keys:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and add your keys:
   ```
   GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
   ```

### Getting API Keys

**GitHub Token** (optional but recommended):
1. Go to GitHub Settings → Developer Settings → Personal Access Tokens
2. Generate new token (classic) with `public_repo` scope
3. Without a token: 60 requests/hour. With token: 5,000 requests/hour

**Anthropic API Key** (required):
1. Sign up at [console.anthropic.com](https://console.anthropic.com/)
2. Create a new API key

## Usage

### Interactive Mode (recommended)

```bash
python main.py find
```

You'll be prompted to select:
- Topic (ai, web, backend, devops, mobile, data, security, any)
- Programming language
- Skill level (beginner, intermediate, advanced)
- Available time (quick_win, half_day, full_day, weekend, deep_dive)

### Command Line Mode

```bash
python main.py find --topic ai --language python --skill beginner --time half_day --no-interactive
```

### All Find Options

```bash
python main.py find [OPTIONS]

Options:
  -t, --topic TEXT         Topic area (ai, web, backend, devops, mobile, data, security, any)
  -l, --language TEXT      Programming language
  -s, --skill TEXT         Skill level (beginner, intermediate, advanced)
  -T, --time TEXT          Available time (quick_win, half_day, full_day, weekend, deep_dive)
  -n, --results INTEGER    Number of results to show [default: 5]
  -i, --interactive        Use interactive prompts [default: True]
  --cache / --no-cache     Use caching to reduce API calls [default: cache]
  --confidence / --no-confidence  Show confidence score breakdown [default: confidence]
  -H, --hide-seen          Hide issues you've already viewed
  --track / --no-track     Track viewed issues in history [default: track]
```

### Check Setup

Verify your API keys are configured correctly:

```bash
python main.py check-setup
```

## Feature Details

### Caching

Caching reduces API costs and speeds up repeated searches:

```bash
# View cache statistics
python main.py cache stats

# Clear the cache
python main.py cache clear

# Run search without cache
python main.py find --no-cache
```

Cache stores:
- GitHub search results (15 minute TTL)
- Claude analysis results (24 hour TTL)

### Favorites

Save issues you're interested in for later:

```bash
# After search, you'll be prompted to save favorites
# Or manage them directly:

python main.py favorites              # List all favorites
python main.py favorites stats        # View statistics
python main.py favorite-show owner/repo#123    # Show details
python main.py favorite-update owner/repo#123 --status in_progress
python main.py favorite-update owner/repo#123 --add-tag "weekend-project"
python main.py favorite-remove owner/repo#123
```

Status workflow: `saved` → `in_progress` → `completed` / `abandoned`

### Confidence Scores

See why issues match your criteria with detailed breakdowns:

```
Score Breakdown:
  Difficulty Match  ████████░░  80%  ●
  Time Match        ██████████ 100%  ●
  Repo Health       ██████░░░░  60%  ◐
  Issue Clarity     █████████░  90%  ●
  Confidence: high ●
```

Confidence indicators:
- `●` (green) - High confidence
- `◐` (yellow) - Medium confidence
- `○` (red) - Low confidence

### Custom Label Mappings

Different repositories use different labels. Configure custom mappings:

```bash
# View pre-configured repos (rust-lang/rust, godotengine/godot, etc.)
python main.py labels builtin

# Show mapping for a specific repo
python main.py label-show rust-lang/rust

# Add custom mapping
python main.py label-add myorg/myrepo beginner "easy-fix"
python main.py label-add myorg/myrepo intermediate "help-wanted"

# Import and customize a built-in mapping
python main.py label-import rust-lang/rust
```

Pre-configured repositories include:
- `rust-lang/rust` (E-easy, E-medium, E-hard)
- `godotengine/godot` (junior job)
- `python/cpython` (easy)
- `django/django` (easy pickings)
- And more...

### History Tracking

Track which issues you've viewed and their status:

```bash
# View history
python main.py history              # List recent
python main.py history stats        # Statistics
python main.py history recent       # Last 7 days

# Update status
python main.py history-update owner/repo#123 attempted
python main.py history-update owner/repo#123 completed

# Hide previously seen issues in search
python main.py find --hide-seen

# Clear history
python main.py history clear
```

Status options: `viewed`, `interested`, `attempted`, `completed`, `abandoned`, `skipped`

## Example Output

```
╭─────────────────── Search Results ───────────────────╮
│                                                      │
│  GitHub Issue Analyzer                               │
│                                                      │
│  Topic: ai | Language: python | Level: beginner      │
│  Time: half_day                                      │
│                                                      │
│  Found 15 matching issues                            │
│                                                      │
╰──────────────────────────────────────────────────────╯

╭──────────── #1 scikit-learn/scikit-learn ────────────╮
│                                                      │
│  Difficulty: Beginner    Time: 2-4 hours             │
│                                                      │
│  Summary:                                            │
│  Add example showing custom distance metric          │
│  for KNeighborsClassifier...                         │
│                                                      │
│  Score Breakdown:                                    │
│    Difficulty Match  ████████░░  80%  ●              │
│    Time Match        ██████████ 100%  ●              │
│    Repo Health       ████████░░  80%  ●              │
│    Issue Clarity     █████████░  90%  ●              │
│    Confidence: high ●                                │
│                                                      │
│  Technical Requirements: Python, sklearn, numpy      │
│                                                      │
│  Why this issue:                                     │
│  Clear scope, active maintainers, good first issue   │
│                                                      │
│  Link: https://github.com/scikit-learn/...           │
│                                                      │
╰────────────────────── Match: 94% ● ──────────────────╯

Cache: 5 hits, 15 API calls (saved ~$0.015 in API costs)
```

## Project Structure

```
github-issue-analyzer/
├── main.py                 # CLI entry point
├── src/
│   ├── config.py           # Configuration constants
│   ├── github_client.py    # GitHub API interactions
│   ├── analyzer.py         # Claude/LangChain analysis
│   ├── scorer.py           # Ranking algorithm
│   ├── presenter.py        # Rich terminal output
│   ├── cache.py            # Caching layer
│   ├── favorites.py        # Favorites management
│   ├── history.py          # History tracking
│   └── label_mappings.py   # Custom label configurations
├── requirements.txt
├── .env.example
└── README.md
```

## Technologies

- **LangChain** - AI orchestration framework
- **Anthropic Claude** - LLM for issue analysis (Haiku 4.5)
- **PyGithub** - GitHub API wrapper
- **Rich** - Beautiful terminal output
- **Typer** - CLI framework
- **Pydantic** - Data validation and structured outputs
- **diskcache** - Persistent caching

## Configuration

Key parameters can be adjusted in `src/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_RESULTS_PER_SEARCH` | 50 | Issues to fetch from GitHub |
| `ISSUES_TO_ANALYZE` | 20 | Issues to send to Claude |
| `MIN_REPO_STARS` | 50 | Minimum repository stars |
| `MODEL_NAME` | claude-haiku-4-5-20251001 | Claude model to use |
| `GITHUB_CACHE_TTL_MINUTES` | 15 | GitHub cache duration |
| `LLM_CACHE_TTL_HOURS` | 24 | LLM cache duration |

## All Commands Reference

| Command | Description |
|---------|-------------|
| `find` | Search for matching issues |
| `check-setup` | Verify API configuration |
| `cache stats` | View cache statistics |
| `cache clear` | Clear all caches |
| `favorites` | List saved favorites |
| `favorites stats` | Favorites statistics |
| `favorite-show` | Show favorite details |
| `favorite-update` | Update favorite status/notes |
| `favorite-remove` | Remove from favorites |
| `history` | View issue history |
| `history stats` | History statistics |
| `history-update` | Update issue status |
| `labels` | List custom label mappings |
| `labels builtin` | Show pre-configured repos |
| `label-show` | Show repo label mapping |
| `label-add` | Add label mapping |
| `label-remove` | Remove label mapping |
| `label-import` | Import built-in as custom |
| `label-delete` | Delete custom mapping |

## License

MIT
