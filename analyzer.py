"""
analyzer.py
Core logic for the GitHub Profile Analyzer.
Keeps all GitHub API + data-processing logic separate from the CLI/GUI
so this same class can be reused later in a tkinter GUI.
"""

import requests
from datetime import datetime
from collections import defaultdict


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns an error we can't recover from."""
    pass


class GitHubAnalyzer:
    BASE_URL = "https://api.github.com"

    def __init__(self, username: str, token: str = None):
        self.username = username
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json"})
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

        self.profile = None
        self.repos = []

    # ------------------------------------------------------------------
    # Low-level request helper
    # ------------------------------------------------------------------
    def _get(self, url, params=None):
        response = self.session.get(url, params=params)

        if response.status_code == 404:
            raise GitHubAPIError(f"User '{self.username}' not found on GitHub.")

        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining == "0":
                reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
                reset_time = datetime.fromtimestamp(reset_ts).strftime("%H:%M:%S")
                raise GitHubAPIError(
                    f"GitHub API rate limit exceeded. Resets at {reset_time}. "
                    f"Tip: pass a personal access token with --token to get a much higher limit."
                )
            raise GitHubAPIError("GitHub API returned 403 Forbidden.")

        if not response.ok:
            raise GitHubAPIError(f"GitHub API error {response.status_code}: {response.text[:200]}")

        return response

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------
    def fetch_profile(self) -> dict:
        url = f"{self.BASE_URL}/users/{self.username}"
        self.profile = self._get(url).json()
        return self.profile

    def fetch_repos(self) -> list:
        """Fetches ALL public repos for the user, handling pagination."""
        repos = []
        page = 1
        while True:
            url = f"{self.BASE_URL}/users/{self.username}/repos"
            params = {"per_page": 100, "page": page, "type": "owner", "sort": "updated"}
            data = self._get(url, params=params).json()
            if not data:
                break
            repos.extend(data)
            page += 1
        self.repos = repos
        return repos

    # ------------------------------------------------------------------
    # Derived stats (computed from already-fetched data, no extra API calls)
    # ------------------------------------------------------------------
    def total_stars(self) -> int:
        return sum(r.get("stargazers_count", 0) for r in self.repos)

    def total_forks(self) -> int:
        return sum(r.get("forks_count", 0) for r in self.repos)

    def language_breakdown(self) -> dict:
        """Counts primary language per repo. Returns {language: count}, sorted desc."""
        counts = defaultdict(int)
        for repo in self.repos:
            lang = repo.get("language")
            if lang:
                counts[lang] += 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def top_repos(self, n: int = 5, by: str = "stars") -> list:
        key_map = {
            "stars": "stargazers_count",
            "forks": "forks_count",
            "updated": "updated_at",
        }
        key = key_map.get(by, "stargazers_count")
        return sorted(self.repos, key=lambda r: r.get(key) or 0, reverse=True)[:n]

    def account_age_years(self) -> float:
        if not self.profile or not self.profile.get("created_at"):
            return 0.0
        created = datetime.strptime(self.profile["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        return round((datetime.utcnow() - created).days / 365.25, 1)

    def summary(self) -> dict:
        """Convenience method: fetches everything and returns one combined dict."""
        if self.profile is None:
            self.fetch_profile()
        if not self.repos:
            self.fetch_repos()

        return {
            "username": self.profile.get("login"),
            "name": self.profile.get("name"),
            "bio": self.profile.get("bio"),
            "followers": self.profile.get("followers"),
            "following": self.profile.get("following"),
            "public_repos": self.profile.get("public_repos"),
            "account_created": self.profile.get("created_at"),
            "account_age_years": self.account_age_years(),
            "location": self.profile.get("location"),
            "avatar_url": self.profile.get("avatar_url"),
            "total_stars": self.total_stars(),
            "total_forks": self.total_forks(),
            "language_breakdown": self.language_breakdown(),
            "top_repos": self.top_repos(),
        }

    def fetch_avatar_bytes(self) -> bytes:
        """Downloads the user's avatar image and returns the raw bytes,
        or None if it can't be fetched (e.g. no network, missing avatar)."""
        if self.profile is None:
            self.fetch_profile()
        url = self.profile.get("avatar_url")
        if not url:
            return None
        try:
            response = self.session.get(url, timeout=10)
            if response.ok:
                return response.content
        except requests.exceptions.RequestException:
            pass
        return None

    def fetch_repo_languages(self, owner: str, repo_name: str) -> dict:
        """Returns byte-accurate {language: bytes} for a single repo.
        Unlike language_breakdown() (which just counts each repo's primary
        language), this reflects actual code volume per language."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/languages"
        try:
            return self._get(url).json()
        except (GitHubAPIError, requests.exceptions.RequestException):
            return {}

    def fetch_repo_languages(self, owner: str, repo_name: str) -> dict:
        """Returns byte-accurate language breakdown for a single repo,
        e.g. {'Python': 48213, 'HTML': 1023}. This is a separate,
        more precise endpoint than the primary-language-per-repo count
        used for the overall profile breakdown."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/languages"
        return self._get(url).json()

    def fetch_repo_languages(self, owner: str, repo_name: str) -> dict:
        """Returns byte-accurate language breakdown for a single repo,
        e.g. {"Python": 48213, "HTML": 2044}. Unlike language_breakdown()
        (which just counts primary language per repo across the whole
        account), this hits GitHub's per-repo languages endpoint."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/languages"
        try:
            return self._get(url).json()
        except GitHubAPIError:
            return {}
