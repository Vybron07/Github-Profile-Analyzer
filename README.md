# GitHub Profile Analyzer

A Python tool for analyzing public GitHub profiles — available as a
command-line tool and a full desktop GUI app. Enter any GitHub username
and get a polished, Instagram-style profile view, top repositories with
per-repo language breakdowns, and visual charts.

---

## Features

**Core (CLI + GUI)**
- Profile overview — name, bio, location, followers, following, public
  repo count, account age
- Repository stats — total stars and forks across all public repos
- Language breakdown — by repo count (fast) and, per-repo, by actual
  byte count (precise)
- Top repositories — ranked by stars, any count you choose
- Charts — language donut chart + top-repos bar chart
- Works without a token (60 requests/hour) or with a personal access
  token (5,000 requests/hour)

**GUI-only**
- Three-screen flow: Home (search) → Loading → Results
- Home screen: split gradient/terminal-style panel, moving dot-grid
  background, recent searches saved between runs, show/hide token toggle
- Loading screen: retro Windows-95-style chunky block progress bar with
  live percentage, animated terminal spinner, and 20 rotating GitHub/Git
  facts to read while it works
- Results screen: black & grey monochrome theme with a real circular
  avatar photo, a single-page Instagram-style Overview (profile header,
  stats, featured top repo), and a "⋮" menu to jump to Top Repos or
  Charts
- Click any repo to open a full detail page: stars, forks, watchers,
  open issues, size, default branch, and a byte-accurate language pie
  chart fetched just for that repo
- Click a repo's name (or its card on the Overview page) to open it
  directly on GitHub in your browser
- Recent searches and app data are stored in a proper persistent folder
  (`%APPDATA%\GitHubProfileAnalyzer`), so they survive even when the app
  is packaged as a standalone `.exe`

---

## Project structure

```
github_analyzer/
├── analyzer.py           Core logic: GitHub API calls + stat calculations
├── cli.py                 Command-line interface
├── gui.py                  Desktop GUI (tkinter)
├── requirements.txt      Python dependencies
├── build_exe.bat          One-click script to package gui.py as a .exe
└── README.md               This file
```

`analyzer.py` contains all the GitHub API and data-processing logic, with
no printing or UI code in it. Both `cli.py` and `gui.py` import from it —
fix a bug or add a stat once, and both interfaces benefit.

---

## Setup

1. Open this folder in VSCode (or any editor/terminal).
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   Dependencies: `requests` (API calls), `matplotlib` (charts), `Pillow`
   (avatar image processing).

---

## Getting a GitHub token (recommended)

Without a token you get 60 requests/hour from GitHub's API. Each profile
analysis uses several requests (profile + paginated repo list + avatar),
so this runs out fast if you're testing repeatedly.

1. Go to https://github.com/settings/tokens
2. Click **Generate new token** → **Generate new token (classic)**
3. No scopes are needed for public data — just name it and generate.
4. Paste it into the GUI's **Token** field (click 👁 to check it typed
   correctly), or pass it to the CLI with `--token`.

---

## Using the CLI (`cli.py`)

```
python cli.py <username>
python cli.py <username> --charts
python cli.py <username> --charts --top 10
python cli.py <username> --token ghp_xxxxxxxxxxxx
```

| Flag         | Description                                      | Default |
|--------------|---------------------------------------------------|---------|
| `username`   | GitHub username to analyze (required)             | —       |
| `--token`    | Personal access token, raises rate limit          | none    |
| `--charts`   | Generate and display matplotlib charts            | off     |
| `--top N`    | Number of top repos to display                    | 5       |

---

## Using the GUI (`gui.py`)

```
python gui.py
```

**Home** — search screen with username, optional token, and a top-repos
counter (1–20). Recent searches appear as clickable chips.

**Loading** — a chunky retro progress bar with a live percentage, an
animated spinner, and rotating GitHub/Git facts while your data is
fetched in the background.

**Results** — the Overview tab is one continuous page: circular avatar,
Instagram-style stat row, bio, extended stats, and a featured top repo
card (click it to open that repo on GitHub). Use the **⋮** menu in the
header to switch to **Top Repos** (click any repo for its full detail
page + language chart) or **Charts** (language donut + top-repos bar
chart). **← New Search** returns to Home.

---

## Packaging as a standalone `.exe`

If you want to run this without opening a terminal or having Python
installed, package it with PyInstaller:

1. Make sure `build_exe.bat`, `gui.py`, and `analyzer.py` are all in the
   same folder.
2. Double-click `build_exe.bat` (or run it from a terminal).
3. Find your app at `dist\GitHubProfileAnalyzer.exe`.

That single file runs standalone on any Windows machine — no Python
required. See the **Publishing to GitHub** section below for how to
share it as a downloadable release.

---

## Publishing to GitHub (so others can download it)

### 1. Create a GitHub account and a new repository
- Sign up at https://github.com if you don't have an account.
- Click the **+** in the top-right → **New repository**.
- Name it (e.g. `github-profile-analyzer`), leave it **Public**, and
  click **Create repository**. Don't initialize it with a README —
  you already have one.

### 2. Add a `.gitignore`
Create a file named `.gitignore` in this folder (a template is included
alongside this README) so build artifacts and personal data don't get
uploaded.

### 3. Push your code
Open a terminal in this folder and run:
```
git init
git add .
git commit -m "Initial commit: GitHub Profile Analyzer"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/github-profile-analyzer.git
git push -u origin main
```
Replace `YOUR-USERNAME` with your actual GitHub username. If `git` isn't
installed, get it from https://git-scm.com/downloads first.

Your code is now live at:
```
https://github.com/YOUR-USERNAME/github-profile-analyzer
```
Anyone can visit that page and click **Code → Download ZIP** to get the
source, or clone it with:
```
git clone https://github.com/YOUR-USERNAME/github-profile-analyzer.git
```

### 4. (Optional but recommended) Share the `.exe` as a Release
Source code downloads still require Python + `pip install`. If you want
people to just download and run the app with zero setup:

1. Build the `.exe` first (see **Packaging** above).
2. On your repo's GitHub page, click **Releases** (right sidebar) →
   **Create a new release**.
3. Give it a tag (e.g. `v1.0`) and a title.
4. Drag `dist\GitHubProfileAnalyzer.exe` into the "Attach binaries" box.
5. Click **Publish release**.

Now anyone can go to your repo's **Releases** page and download the
`.exe` directly — no Python, no terminal, just double-click and run.

### 5. Keep it updated
Whenever you make changes locally:
```
git add .
git commit -m "Describe what you changed"
git push
```
If you rebuild the `.exe`, upload the new version as a new Release
(e.g. `v1.1`) so people can get the update.

---

## Extending this project

- **Compare two users** — fetch two profiles and show them side by side.
- **Commit activity over time** — the
  `/repos/{owner}/{repo}/stats/commit_activity` endpoint returns weekly
  commit counts, which could become a line chart.
- **Caching** — save fetched profile data locally so re-analyzing the
  same user within a short time doesn't burn API calls.
- **Cross-platform builds** — PyInstaller can also build for macOS/Linux,
  but you have to run it *on* that OS — a Windows build won't produce a
  Mac app and vice versa.

---

## Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| `ModuleNotFoundError` for `requests`, `matplotlib`, or `PIL` | Run `pip install -r requirements.txt` |
| "User not found" error | Double-check the username spelling/case |
| Rate limit exceeded | Add a token (see above), or wait for the reset time shown in the error |
| GUI window opens blank | Run `python gui.py` from inside the `github_analyzer` folder, so it can find `analyzer.py` |
| Increasing "top repos" past 5 shows no more | Fixed — make sure you're on the latest `analyzer.py` |
| `.exe` won't build | Make sure PyInstaller installed correctly (`pip install pyinstaller`) and you're running `build_exe.bat` from inside the project folder |
| `git push` asks for a password and fails | GitHub no longer accepts account passwords for this — use a [Personal Access Token](https://github.com/settings/tokens) as the password instead, or set up SSH keys |
