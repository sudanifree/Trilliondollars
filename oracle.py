from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from github_client import GitHubClient


DATABASE_PATH = Path("oracle_cache.sqlite3")
CACHE_TTL_SECONDS = 24 * 60 * 60
HIGH_VALUE_TERMS = {
    "ai",
    "agi",
    "llm",
    "blockchain",
    "quantum",
    "rust",
    "cuda",
    "biotech",
}
README_KEYWORDS = ("ai agent", "autonomous", "open source model")


@dataclass
class RepositoryResult:
    repo_name: str
    url: str
    created_at: str
    updated_at: str
    classification: str
    age_days: int
    stars: int
    forks: int
    open_issues: int
    watchers: int
    contributors: int
    language: str
    topics: list[str]
    readme_length: int
    license: str
    commits_90d: int
    growth_per_day: float
    fork_growth_per_day: float
    readme_keyword_bonus: bool
    trillion_score: float
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OracleService:
    def __init__(
        self,
        client: GitHubClient | None = None,
        database_path: Path | str = DATABASE_PATH,
    ) -> None:
        self.client = client or GitHubClient()
        self.database_path = Path(database_path)
        self.archive_client = None
        if os.getenv("GH_ARCHIVE_ENABLED", "").lower() in {"1", "true", "yes"}:
            from gh_archive import GHArchiveClient

            self.archive_client = GHArchiveClient()
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS repository_cache (
                    repo_name TEXT PRIMARY KEY,
                    fetched_at TEXT NOT NULL,
                    stars INTEGER NOT NULL,
                    forks INTEGER NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _growth(current: int, previous: int | None, elapsed_days: float | None) -> float:
        if previous is None or elapsed_days is None or elapsed_days <= 0:
            return 0.0
        return max(0.0, (current - previous) / elapsed_days)

    @staticmethod
    def _score(
        *,
        growth_per_day: float,
        fork_growth_per_day: float,
        stars: int,
        watchers: int,
        contributors: int,
        open_issues: int,
        language: str,
        topics: list[str],
        readme: str,
        age_days: int,
        commits_90d: int,
    ) -> float:
        growth = min(1.0, (math.tanh(growth_per_day / 10) + math.tanh(fork_growth_per_day / 2)) / 2)
        community = sum(
            (
                min(1.0, math.log1p(stars) / math.log1p(100_000)),
                min(1.0, math.log1p(watchers) / math.log1p(10_000)),
                min(1.0, math.log1p(contributors) / math.log1p(1_000)),
                min(1.0, math.log1p(open_issues) / math.log1p(2_000)),
            )
        ) / 4
        tech_terms = set(re.findall(r"[a-z0-9]+", " ".join([language, *topics]).lower()))
        tech_value = 1.0 if tech_terms & HIGH_VALUE_TERMS else 0.0
        if age_days < 180:
            freshness = 0.5 + 0.5 * growth
        else:
            freshness = min(1.0, commits_90d / 90)
        keyword_bonus = 5 if any(term in readme.lower() for term in README_KEYWORDS) else 0
        return min(
            100.0,
            round(40 * growth + 25 * community + 20 * tech_value + 15 * freshness + keyword_bonus, 2),
        )

    def _cached(self, repo_name: str) -> RepositoryResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT fetched_at, result_json FROM repository_cache WHERE repo_name = ?",
                (repo_name,),
            ).fetchone()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        if (datetime.now(timezone.utc) - fetched_at).total_seconds() >= CACHE_TTL_SECONDS:
            return None
        return RepositoryResult(**json.loads(row["result_json"]))

    def _previous_counts(self, repo_name: str) -> tuple[int | None, int | None, datetime | None]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT fetched_at, stars, forks FROM repository_cache WHERE repo_name = ?",
                (repo_name,),
            ).fetchone()
        if not row:
            return None, None, None
        return (
            row["stars"],
            row["forks"],
            datetime.fromisoformat(row["fetched_at"]),
        )

    def _analyze(self, search_result: dict[str, Any]) -> RepositoryResult:
        full_name = search_result["full_name"]
        details = self.client.repository_details(full_name)
        previous_stars, previous_forks, previous_fetched = self._previous_counts(full_name)

        fetched_at = datetime.now(timezone.utc)
        elapsed_days = (
            (fetched_at - previous_fetched).total_seconds() / 86_400 if previous_fetched else None
        )
        stars = int(details["stargazerCount"])
        forks = int(details["forkCount"])
        growth_per_day = self._growth(stars, previous_stars, elapsed_days)
        fork_growth_per_day = self._growth(forks, previous_forks, elapsed_days)
        created_at = datetime.fromisoformat(details["createdAt"].replace("Z", "+00:00"))
        age_days = max(0, (fetched_at - created_at).days)
        classification = "NEW" if age_days < 180 else "OLD"
        topics = [
            node["topic"]["name"]
            for node in details.get("repositoryTopics", {}).get("nodes", [])
        ]
        readme_object = details.get("object") or {}
        readme = readme_object.get("text") or ""
        language = (details.get("primaryLanguage") or {}).get("name") or ""
        contributors = self.client.contributor_count(full_name)
        commits_90d = (
            details.get("defaultBranchRef", {})
            .get("target", {})
            .get("history", {})
            .get("totalCount", 0)
        )
        open_issues = details.get("issues", {}).get("totalCount", 0)
        watchers = details.get("watchers", {}).get("totalCount", 0)
        score = self._score(
            growth_per_day=growth_per_day,
            fork_growth_per_day=fork_growth_per_day,
            stars=stars,
            watchers=watchers,
            contributors=contributors,
            open_issues=open_issues,
            language=language,
            topics=topics,
            readme=readme,
            age_days=age_days,
            commits_90d=commits_90d,
        )
        result = RepositoryResult(
            repo_name=full_name,
            url=details.get("url") or search_result["html_url"],
            created_at=details["createdAt"],
            updated_at=details["updatedAt"],
            classification=classification,
            age_days=age_days,
            stars=stars,
            forks=forks,
            open_issues=open_issues,
            watchers=watchers,
            contributors=contributors,
            language=language,
            topics=topics,
            readme_length=int(readme_object.get("byteSize") or 0),
            license=(details.get("licenseInfo") or {}).get("spdxId") or "NOASSERTION",
            commits_90d=int(commits_90d),
            growth_per_day=round(growth_per_day, 3),
            fork_growth_per_day=round(fork_growth_per_day, 3),
            readme_keyword_bonus=any(term in readme.lower() for term in README_KEYWORDS),
            trillion_score=score,
            verdict="WILL MAKE TRILLION $/SEC" if score >= 80 else "WILL NOT",
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO repository_cache (repo_name, fetched_at, stars, forks, result_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(repo_name) DO UPDATE SET
                    fetched_at = excluded.fetched_at,
                    stars = excluded.stars,
                    forks = excluded.forks,
                    result_json = excluded.result_json
                """,
                (full_name, fetched_at.isoformat(), stars, forks, json.dumps(result.to_dict())),
            )
        return result

    def scan(self, query: str, limit: int = 20) -> list[RepositoryResult]:
        if not query.strip():
            raise ValueError("Search query cannot be empty.")
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")
        search_results = self.client.search_repositories(query.strip(), limit)
        archive_activity = (
            self.archive_client.activity([repo["full_name"] for repo in search_results])
            if self.archive_client
            else {}
        )
        results = []
        for repository in search_results:
            cached = self._cached(repository["full_name"])
            result = cached if cached is not None else self._analyze(repository)
            activity = archive_activity.get(repository["full_name"])
            if activity:
                result.growth_per_day = round(activity["stars_per_day"], 3)
                result.fork_growth_per_day = round(activity["forks_per_day"], 3)
                result.trillion_score = self._score(
                    growth_per_day=result.growth_per_day,
                    fork_growth_per_day=result.fork_growth_per_day,
                    stars=result.stars,
                    watchers=result.watchers,
                    contributors=result.contributors,
                    open_issues=result.open_issues,
                    language=result.language,
                    topics=result.topics,
                    readme="autonomous" if result.readme_keyword_bonus else "",
                    age_days=result.age_days,
                    commits_90d=result.commits_90d,
                )
                result.verdict = (
                    "WILL MAKE TRILLION $/SEC" if result.trillion_score >= 80 else "WILL NOT"
                )
            results.append(result)
        return sorted(results, key=lambda item: item.trillion_score, reverse=True)

    @staticmethod
    def top_ten(results: list[RepositoryResult]) -> list[RepositoryResult]:
        return [result for result in results if result.verdict == "WILL MAKE TRILLION $/SEC"][:10]
