# GitHub Issue Analyzer

An AI-powered CLI tool that helps developers find open-source contribution opportunities matching their interests, skill level, and available time.

## Features

- **Smart Search**: Query GitHub for open issues by topic and programming language
- **AI Analysis**: Uses Claude to assess actual difficulty, estimate completion time, and evaluate issue clarity
- **Personalized Matching**: Filters and ranks issues based on your skill level and available time
- **Beautiful Output**: Rich terminal interface with color-coded results

## How It Works

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
1. Go to GitHub → Settings → Developer Settings → Personal Access Tokens
2. Generate new token (classic) with `public_repo` scope
3. Without a token: 60 requests/hour. With token: 5,000 requests/hour

**Anthropic API Key** (required):
1. Sign up at [console.anthropic.com](https://console.anthropic.com/)
2. Create a new API key

## Usage

### Interactive Mode (recommended)

```bash
python main.py
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

### Check Setup

Verify your API keys are configured correctly:

```bash
python main.py check-setup
```

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

╭──────── #1 scikit-learn/scikit-learn ────────╮
│                                              │
│  Difficulty: Beginner    Time: 2-4 hours     │
│                                              │
│  Summary:                                    │
│  Add example showing custom distance metric  │
│  for KNeighborsClassifier...                 │
│                                              │
│  Technical Requirements: Python, sklearn     │
│                                              │
│  Link: https://github.com/scikit-learn/...   │
│                                              │
│  Match: 94%                                  │
╰──────────────────────────────────────────────╯
```

## Project Structure

```
github-issue-analyzer/
├── main.py              # CLI entry point
├── src/
│   ├── config.py        # Configuration constants
│   ├── github_client.py # GitHub API interactions
│   ├── analyzer.py      # Claude/LangChain analysis
│   ├── scorer.py        # Ranking algorithm
│   └── presenter.py     # Rich terminal output
├── requirements.txt
├── .env.example
└── README.md
```

## Technologies

- **LangChain** - AI orchestration framework
- **Anthropic Claude** - LLM for issue analysis
- **PyGithub** - GitHub API wrapper
- **Rich** - Beautiful terminal output
- **Typer** - CLI framework

## Configuration

Key parameters can be adjusted in `src/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_RESULTS_PER_SEARCH` | 50 | Issues to fetch from GitHub |
| `ISSUES_TO_ANALYZE` | 20 | Issues to send to Claude |
| `MIN_REPO_STARS` | 50 | Minimum repository stars |
| `MODEL_NAME` | claude-haiku-4-5 | Claude model to use |

## License

MIT
