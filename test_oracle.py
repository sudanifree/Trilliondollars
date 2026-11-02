from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from oracle import OracleService


class FakeGitHubClient:
    def __init__(self) -> None:
        self.details_calls = 0

    def search_repositories(self, query: str, limit: int) -> list[dict]:
        return [{"full_name": "example/project", "html_url": "https://github.com/example/project"}]

    def repository_details(self, full_name: str) -> dict:
        self.details_calls += 1
        created = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        return {
            "nameWithOwner": full_name,
            "url": "https://github.com/example/project",
            "createdAt": created,
            "updatedAt": created,
            "stargazerCount": 100,
            "forkCount": 20,
            "watchers": {"totalCount": 80},
            "issues": {"totalCount": 5},
            "primaryLanguage": {"name": "Rust"},
            "repositoryTopics": {"nodes": [{"topic": {"name": "llm"}}]},
            "licenseInfo": {"spdxId": "MIT"},
            "object": {"byteSize": 128, "text": "An autonomous AI agent"},
            "defaultBranchRef": {"target": {"history": {"totalCount": 12}}},
        }

    def contributor_count(self, full_name: str) -> int:
        return 3


class OracleServiceTests(unittest.TestCase):
    def test_scans_and_caches_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            client = FakeGitHubClient()
            service = OracleService(
                client=client,
                database_path=Path(temporary_directory) / "cache.sqlite3",
            )

            first = service.scan("topic:llm", 1)
            second = service.scan("topic:llm", 1)

            self.assertEqual(len(first), 1)
            self.assertEqual(first[0].classification, "NEW")
            self.assertEqual(first[0].readme_length, 128)
            self.assertTrue(first[0].readme_keyword_bonus)
            self.assertEqual(second[0].repo_name, "example/project")
            self.assertEqual(client.details_calls, 1)

    def test_score_is_bounded(self) -> None:
        score = OracleService._score(
            growth_per_day=1_000,
            fork_growth_per_day=1_000,
            stars=1_000_000,
            watchers=1_000_000,
            contributors=1_000_000,
            open_issues=1_000_000,
            language="Rust",
            topics=["AGI"],
            readme="open source model",
            age_days=1,
            commits_90d=90,
        )
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


if __name__ == "__main__":
    unittest.main()
