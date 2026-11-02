from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dotenv import load_dotenv


class GitHubAPIError(RuntimeError):
    pass


class GitHubClient:
    REST_URL = "https://api.github.com"
    GRAPHQL_URL = "https://api.github.com/graphql"

    def __init__(self, tokens: list[str] | None = None) -> None:
        load_dotenv()
        configured_tokens = tokens
        if configured_tokens is None:
            configured_tokens = os.getenv("GITHUB_TOKEN", "").replace(",", " ").split()
        self.tokens = [token.strip() for token in configured_tokens if token.strip()]
        self.token_index = 0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "trillion-dollar-oracle",
            }
        )

    def _headers(self) -> dict[str, str]:
        if not self.tokens:
            return {}
        return {"Authorization": f"Bearer {self.tokens[self.token_index]}"}

    def _rotate_token(self) -> bool:
        if len(self.tokens) < 2:
            return False
        self.token_index = (self.token_index + 1) % len(self.tokens)
        return True

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> requests.Response:
        attempts = max(1, len(self.tokens)) + 1
        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method, url, params=params, json=json, headers=self._headers(), timeout=30
                )
            except requests.RequestException as exc:
                raise GitHubAPIError(f"GitHub request failed: {exc}") from exc

            if response.status_code in (401, 403):
                rate_limited = response.status_code == 403 and (
                    response.headers.get("X-RateLimit-Remaining") == "0"
                    or "rate limit" in response.text.lower()
                )
                if self._rotate_token() and attempt + 1 < attempts:
                    continue
                if rate_limited:
                    reset = response.headers.get("X-RateLimit-Reset")
                    if reset:
                        wait_seconds = int(reset) - int(time.time())
                        if 0 < wait_seconds <= 5:
                            time.sleep(wait_seconds)
                            continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < attempts:
                    time.sleep(min(2**attempt, 4))
                    continue
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                detail = response.text[:300]
                raise GitHubAPIError(
                    f"GitHub returned HTTP {response.status_code}: {detail}"
                ) from exc
            return response
        raise GitHubAPIError("GitHub request failed after retrying available credentials.")

    def search_repositories(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        repositories: list[dict[str, Any]] = []
        page = 1
        while len(repositories) < limit:
            response = self._request(
                "GET",
                f"{self.REST_URL}/search/repositories",
                params={
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": min(100, limit - len(repositories)),
                    "page": page,
                },
            )
            payload = response.json()
            repositories.extend(payload.get("items", []))
            if len(payload.get("items", [])) == 0:
                break
            page += 1
        return repositories[:limit]

    def repository_details(self, full_name: str) -> dict[str, Any]:
        owner, name = full_name.split("/", 1)
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        query = """
        query($owner: String!, $name: String!, $since: GitTimestamp!) {
          repository(owner: $owner, name: $name) {
            nameWithOwner
            url
            createdAt
            updatedAt
            stargazerCount
            forkCount
            watchers { totalCount }
            issues(states: OPEN) { totalCount }
            primaryLanguage { name }
            repositoryTopics(first: 20) { nodes { topic { name } } }
            licenseInfo { spdxId }
            object(expression: "HEAD:README.md") {
              ... on Blob { byteSize text }
            }
            defaultBranchRef {
              target {
                ... on Commit { history(since: $since) { totalCount } }
              }
            }
          }
        }
        """
        response = self._request(
            "POST",
            self.GRAPHQL_URL,
            json={"query": query, "variables": {"owner": owner, "name": name, "since": since}},
        )
        payload = response.json()
        if payload.get("errors"):
            message = "; ".join(error.get("message", "Unknown GraphQL error") for error in payload["errors"])
            raise GitHubAPIError(f"GitHub GraphQL error for {full_name}: {message}")
        repository = payload.get("data", {}).get("repository")
        if not repository:
            raise GitHubAPIError(f"GitHub did not return repository details for {full_name}.")
        return repository

    def contributor_count(self, full_name: str) -> int:
        from github import Auth, Github
        from github.GithubException import GithubException

        attempts = max(1, len(self.tokens))
        for attempt in range(attempts):
            auth = Auth.Token(self.tokens[self.token_index]) if self.tokens else None
            github = Github(auth=auth, per_page=1)
            try:
                return github.get_repo(full_name).get_contributors(anon="true").totalCount
            except GithubException as exc:
                if attempt + 1 < attempts:
                    self._rotate_token()
                    continue
                raise GitHubAPIError(
                    f"Could not count contributors for {full_name}: {exc}"
                ) from exc
            finally:
                github.close()
        raise GitHubAPIError(f"Could not count contributors for {full_name}.")
