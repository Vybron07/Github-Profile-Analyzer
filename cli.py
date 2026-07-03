"""
cli.py
Command-line interface for the GitHub Profile Analyzer.

Usage examples:
    python cli.py torvalds
    python cli.py octocat --token ghp_xxx
    python cli.py octocat --charts
    python cli.py octocat --top 10 --charts
"""

import argparse
import sys
import requests
import matplotlib.pyplot as plt

from analyzer import GitHubAnalyzer, GitHubAPIError


def print_report(data: dict, top_n: int):
    line = "=" * 60
    print(line)
    print(f"  GITHUB PROFILE REPORT: {data['username']}")
    print(line)

    if data["name"]:
        print(f"Name:            {data['name']}")
    if data["bio"]:
        print(f"Bio:             {data['bio']}")
    if data["location"]:
        print(f"Location:        {data['location']}")

    print(f"Followers:       {data['followers']}")
    print(f"Following:       {data['following']}")
    print(f"Public repos:    {data['public_repos']}")
    print(f"Account age:     {data['account_age_years']} years")
    print(f"Total stars:     {data['total_stars']}")
    print(f"Total forks:     {data['total_forks']}")

    print("\n--- Language breakdown (by repo count) ---")
    langs = data["language_breakdown"]
    if langs:
        for lang, count in langs.items():
            print(f"  {lang:<15} {count}")
    else:
        print("  No language data available.")

    print(f"\n--- Top {top_n} repos by stars ---")
    for i, repo in enumerate(data["top_repos"][:top_n], 1):
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        print(f"  {i}. {repo['name']:<30} ⭐ {stars:<6} 🍴 {forks}")
        if repo.get("description"):
            print(f"     {repo['description']}")

    print(line)


def make_charts(data: dict, username: str):
    langs = data["language_breakdown"]
    top_repos = data["top_repos"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle(f"GitHub Analysis: {username}", fontsize=14, fontweight="bold")

    # --- Language pie chart ---
    if langs:
        axes[0].pie(
            langs.values(),
            labels=langs.keys(),
            autopct="%1.0f%%",
            startangle=90,
        )
        axes[0].set_title("Language Breakdown (by repo count)")
    else:
        axes[0].text(0.5, 0.5, "No language data", ha="center", va="center")
        axes[0].set_title("Language Breakdown")

    # --- Top repos bar chart ---
    if top_repos:
        names = [r["name"] for r in top_repos[:5]]
        stars = [r.get("stargazers_count", 0) for r in top_repos[:5]]
        axes[1].barh(names[::-1], stars[::-1], color="#4c8bf5")
        axes[1].set_title("Top Repos by Stars")
        axes[1].set_xlabel("Stars")
    else:
        axes[1].text(0.5, 0.5, "No repos found", ha="center", va="center")

    plt.tight_layout()
    out_path = f"{username}_github_report.png"
    plt.savefig(out_path, dpi=150)
    print(f"\nChart saved to: {out_path}")
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Analyze a GitHub user's public profile.")
    parser.add_argument("username", help="GitHub username to analyze")
    parser.add_argument("--token", help="GitHub personal access token (raises rate limit from 60/hr to 5000/hr)")
    parser.add_argument("--charts", action="store_true", help="Generate matplotlib charts")
    parser.add_argument("--top", type=int, default=5, help="Number of top repos to show (default: 5)")
    args = parser.parse_args()

    analyzer = GitHubAnalyzer(args.username, token=args.token)

    try:
        print(f"Fetching data for '{args.username}'...")
        data = analyzer.summary()
    except GitHubAPIError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("\nError: could not connect to GitHub. Check your internet connection.", file=sys.stderr)
        sys.exit(1)

    print_report(data, args.top)

    if args.charts:
        make_charts(data, args.username)


if __name__ == "__main__":
    main()
