from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from gh_archive import GHArchiveError
from github_client import GitHubAPIError
from oracle import OracleService


def main() -> None:
    parser = argparse.ArgumentParser(description="Score GitHub repositories with the Trillion Dollar Oracle.")
    parser.add_argument("query", help='GitHub repository search query, e.g. "topic:llm stars:>1000"')
    parser.add_argument("--limit", type=int, default=20, help="Maximum repositories to inspect (1-100).")
    parser.add_argument("--json", dest="json_path", default="results.json", help="Output JSON file path.")
    args = parser.parse_args()

    try:
        results = OracleService().scan(args.query, args.limit)
    except (GitHubAPIError, GHArchiveError) as exc:
        parser.error(str(exc))
    if not results:
        print("No repositories matched the query.")
        return

    rows = [
        {
            "Repo Name": result.repo_name,
            "NEW/OLD": result.classification,
            "Age": result.age_days,
            "Stars": result.stars,
            "Growth/Day": result.growth_per_day,
            "TrillionScore": result.trillion_score,
            "Verdict": result.verdict,
        }
        for result in results
    ]
    print(pd.DataFrame(rows).to_string(index=False))
    for result in results:
        if result.trillion_score > 95:
            print(f"{result.repo_name}: This project will make you $1T/sec, retire immediately.")

    output_path = Path(args.json_path)
    output_path.write_text(
        json.dumps([asdict(result) for result in results], indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved {len(results)} results to {output_path}.")
    print("\nTop 10 candidates:")
    candidates = OracleService.top_ten(results)
    if candidates:
        for result in candidates[:10]:
            print(f"- {result.repo_name}: {result.trillion_score:.2f}")
    else:
        print("No repositories crossed the candidate threshold.")


if __name__ == "__main__":
    main()
