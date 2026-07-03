# GitHub Profile Analyzer

A Python tool for analyzing public GitHub profiles — available as both a
command-line tool and a desktop GUI. Enter any GitHub username and get
followers/stars/forks stats, a language breakdown, top repositories, and
visual charts.

---

## Features

- **Profile overview** — name, bio, location, followers, following, public
  repo count, account age
- **Repository stats** — total stars and forks across all public repos
- **Language breakdown** — primary language per repo, shown as counts and
  as a pie chart
- **Top repositories** — ranked by stars, with fork count and description
- **Charts** — language pie chart + top-repos bar chart (matplotlib)
- **Rate-limit friendly** — works without a token (60 requests/hour) or
  with a personal access token (5,000 requests/hour)
- **GUI extras**:
  - Three-screen flow: Search → Loading → Results
  - Split-screen home layout with a gradient illustration panel
  - Token field with a show/hide (👁) toggle
  - Recent searches saved between runs, shown as clickable chips
  - Animated loading screen so the app never looks frozen while fetching

---

## Project structure

```
github_analyzer/
├── analyzer.py           Core logic: GitHub API calls + stat calculations
├── cli.py                 Command-line interface
├── gui.py                  Desktop GUI (tkinter)
├── requirements.txt      Python dependencies
├── recent_searches.json  Auto-created by the GUI to remember recent usernames
└── README.md               This file
```

`analyzer.py` contains all the GitHub API and data-processing logic, with
no printing or UI code in it. Both `cli.py` and `gui.py` import from it —
if you ever fix a bug or add a stat, you only need to change it in one
place.

---

## Setup

1. Open this folder in VSCode (or any editor/terminal).
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   Dependencies: `requests` (API calls) and `matplotlib` (charts).

---

## Getting a GitHub token (recommended)

Without a token you get 60 requests/hour from GitHub's API — each profile
analysis uses several requests (profile + paginated repo list), so this
runs out fast if you're testing repeatedly.

1. Go to https://github.com/settings/tokens
2. Click **Generate new token** → **Generate new token (classic)**
3. No scopes are needed for public data — just name it and generate.
4. Copy the token. You can:
   - Paste it into the **Token** field in the GUI (click the 👁 icon to
     check it was typed correctly), or
   - Pass it on the command line with `--token`

---

## Using the CLI (`cli.py`)

```
python cli.py <username>
python cli.py <username> --charts
python cli.py <username> --charts --top 10
python cli.py <username> --token ghp_xxxxxxxxxxxx
```

**Arguments:**

| Flag         | Description                                      | Default |
|--------------|---------------------------------------------------|---------|
| `username`   | GitHub username to analyze (required)             | —       |
| `--token`    | Personal access token, raises rate limit          | none    |
| `--charts`   | Generate and display matplotlib charts            | off     |
| `--top N`    | Number of top repos to display                    | 5       |

With `--charts`, a chart window opens showing the language pie chart and
top-repos bar chart, and a PNG (`<username>_github_report.png`) is saved
in the same folder.

**Error handling:** the CLI prints a clear message and exits (rather than
crashing) if the username doesn't exist, the rate limit is hit, or there's
a network problem.

---

## Using the GUI (`gui.py`)

```
python gui.py
```

The GUI has three screens:

### 1. Home (search)
Split-screen layout:
- **Left panel** — a gradient illustration panel (lavender → pink → peach)
  with the app title, a short feature list, and decorative star/commit
  doodles.
- **Right panel** — the actual form: username, optional token (with a
  show/hide toggle), a "top repos to show" spinbox, and the **Analyze
  Profile** button.
- **Recent searches** — after your first successful search, up to 6
  recent usernames appear as clickable chips under the form. Clicking one
  re-runs that search immediately. This list is saved to
  `recent_searches.json` and persists between runs of the app.

### 2. Loading
Shown while data is being fetched in the background (the window stays
responsive — fetching happens on a separate thread). Displays an animated
progress bar and the username being fetched.

### 3. Results
- **Overview tab** — bio, location, and stat cards for followers,
  following, public repos, total stars, total forks, and account age.
- **Top Repos tab** — a sortable table with stars, forks, and description
  for each top repo.
- **Charts tab** — the language pie chart and top-repos bar chart,
  embedded directly in the window.
- A **← New Search** button in the header returns to the Home screen.

If something goes wrong (bad username, rate limit, network error), the
app shows a popup with the error and returns you to the Home screen
rather than getting stuck on the Loading screen.

---

## Extending this project

Ideas for next steps, roughly easiest → hardest:

- **Remember the token too** — currently only usernames are saved between
  runs; the token field resets each time. Could save it (encrypted or in
  an env var) so you don't retype it.
- **Compare two users** — fetch two profiles and show them side by side.
- **Byte-accurate language stats** — currently language breakdown counts
  *primary* language per repo. The `/repos/{owner}/{repo}/languages`
  endpoint gives actual byte counts per language per repo, which would be
  more precise (at the cost of one extra API call per repo).
- **Commit activity over time** — the
  `/repos/{owner}/{repo}/stats/commit_activity` endpoint returns weekly
  commit counts, which could be turned into a line chart.
- **Caching** — save fetched profile data locally (e.g. as JSON) so
  re-analyzing the same user within a short time doesn't burn API calls.
- **Package as a `.exe`** — using something like PyInstaller so the GUI
  can be shared/run without needing Python installed.

---

## Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'requests'` (or `matplotlib`) | Run `pip install -r requirements.txt` |
| "User not found" error | Double-check the username spelling/case |
| Rate limit exceeded | Add a token (see above), or wait for the reset time shown in the error |
| GUI window opens blank/frozen | Make sure you're running `python gui.py` from inside the `github_analyzer` folder, so `gui.py` can find `analyzer.py` |
| Doodles/gradient look cut off oddly | Try resizing the window — the left panel redraws itself on resize |
