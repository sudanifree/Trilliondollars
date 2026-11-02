from __future__ import annotations

import pandas as pd
import streamlit as st

from gh_archive import GHArchiveError
from github_client import GitHubAPIError
from oracle import OracleService

st.set_page_config(page_title="Trillion Dollar Oracle", layout="wide")
st.title("Trillion Dollar Oracle")
st.caption("A playful, heuristic ranking—not financial advice or a real prediction.")

with st.sidebar:
    query = st.text_input("GitHub search query", value="stars:>1000")
    limit = st.slider("Repositories to scan", min_value=1, max_value=30, value=10)
    run_scan = st.button("Scan repositories", type="primary")

if run_scan:
    try:
        results = OracleService().scan(query, limit)
    except (ValueError, GitHubAPIError, GHArchiveError) as exc:
        st.error(str(exc))
    else:
        if not results:
            st.info("No repositories matched that query.")
        else:
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
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.subheader("Top 10 candidates")
            top_ten = OracleService.top_ten(results)
            if top_ten:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Repository": result.repo_name,
                                "TrillionScore": result.trillion_score,
                                "Verdict": result.verdict,
                            }
                            for result in top_ten
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.write("No repositories crossed the candidate threshold.")
