from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any


class GHArchiveError(RuntimeError):
    pass


class GHArchiveClient:
    """Optional historical activity source backed by the public GH Archive dataset."""

    def __init__(self) -> None:
        try:
            from google.cloud import bigquery
        except ImportError as exc:
            raise GHArchiveError(
                "Install google-cloud-bigquery to enable the GH Archive source."
            ) from exc

        self.bigquery = bigquery
        from google.api_core.exceptions import GoogleAPIError

        self.api_error = GoogleAPIError
        self.client = bigquery.Client(project=os.getenv("GH_ARCHIVE_PROJECT") or None)

    def activity(self, repo_names: list[str]) -> dict[str, dict[str, float]]:
        if not repo_names:
            return {}
        start = datetime.now(timezone.utc).date() - timedelta(days=90)
        end = datetime.now(timezone.utc).date() - timedelta(days=1)
        query = """
        SELECT
          repo.name AS repo_name,
          COUNTIF(type = 'WatchEvent' AND payload.action = 'started') AS stars,
          COUNTIF(type = 'ForkEvent') AS forks
        FROM `githubarchive.day.*`
        WHERE _TABLE_SUFFIX BETWEEN @start_date AND @end_date
          AND repo.name IN UNNEST(@repo_names)
        GROUP BY repo_name
        """
        config = self.bigquery.QueryJobConfig(
            query_parameters=[
                self.bigquery.ScalarQueryParameter("start_date", "STRING", start.strftime("%Y%m%d")),
                self.bigquery.ScalarQueryParameter("end_date", "STRING", end.strftime("%Y%m%d")),
                self.bigquery.ArrayQueryParameter("repo_names", "STRING", repo_names),
            ]
        )
        try:
            rows = self.client.query(query, job_config=config).result()
        except self.api_error as exc:
            raise GHArchiveError(f"GH Archive BigQuery query failed: {exc}") from exc
        return {
            row["repo_name"]: {
                "stars_per_day": float(row["stars"]) / 90,
                "forks_per_day": float(row["forks"]) / 90,
            }
            for row in rows
        }
