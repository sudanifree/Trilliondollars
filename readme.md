# Trillion Dollar Oracle

A playful GitHub repository scanner with a CLI, FastAPI backend, and Streamlit dashboard. Its score is a heuristic, not a financial forecast or investment advice.

The scanner uses GitHub's REST repository Search API to find a bounded set of candidates, then GraphQL to collect repository metadata. It does not attempt to crawl every GitHub repository. Results are cached in SQLite for 24 hours.

## GitHub Pages

The static browser interface lives in `docs/` (`index.html`, `style.css`, and `app.js`) and is deployed by the GitHub Actions workflow on pushes to `main`. Enable GitHub Pages in the repository settings and select **GitHub Actions** as the build and deployment source. The site will be available at `https://sudanifree.github.io/Trilliondollars/`.

GitHub Pages cannot run the Python API. Deploy the FastAPI app separately, then enter its base URL in the Pages interface before scanning. Set `CORS_ORIGINS=https://sudanifree.github.io` on the API host (or add other comma-separated origins) so the browser can call it. Keep GitHub and cloud credentials on the API host; do not put secrets in the Pages site.

## Setup

Requires Python 3.10 or later.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `GITHUB_TOKEN` in `.env` to a GitHub token with public repository read access. A token is required for the GraphQL repository details used by scans; unauthenticated REST search also has a much lower rate limit. Multiple tokens can be supplied comma- or space-separated; the client rotates tokens when the API reports an authentication or rate-limit failure. Keep the token on the API host, never in the Pages frontend.

## Run

CLI scan (writes full results to `results.json`):

```bash
python cli.py 'topic:llm stars:>1000' --limit 20 --json results.json
```

FastAPI backend:

```bash
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000/docs` or call (the Pages UI can use this URL when running locally):

```text
http://127.0.0.1:8000/scan?query=topic%3Allm&limit=10
```

For the browser interface locally, start a second terminal and run:

```bash
python -m http.server 8443 --directory docs
```

Open `http://127.0.0.1:8443`. The API address is prefilled for localhost and Codespaces; Codespaces uses ports 8443 for the page and 8000 for the API. The API's default CORS settings allow the Pages site, localhost, and Codespaces previews on port 8443.

Streamlit dashboard:

```bash
streamlit run dashboard.py
```

## Optional GH Archive data

By default, star and fork growth is measured from cached snapshots. A first observation has a growth rate of zero; subsequent scans use the change since the preceding snapshot. To use historical activity estimates instead, install the BigQuery client:

```bash
pip install google-cloud-bigquery
```

Configure Google Application Default Credentials and a billable Google Cloud project, then set `GH_ARCHIVE_ENABLED=true` and `GH_ARCHIVE_PROJECT=your-project-id` in `.env`. The optional source counts GH Archive star/watch and fork events from the past 90 days. BigQuery usage may incur charges.

## Scoring and output

- **NEW** means repository age is under 180 days; **OLD** means 180 days or more.
- TrillionScore ranges from 0 to 100: growth velocity (40%), community (25%), technology tags/language (20%), freshness or commit activity (15%), plus up to five README-keyword bonus points.
- A score of 80 or more gets the playful `WILL MAKE TRILLION $/SEC` verdict; all others get `WILL NOT`.
- Output is sorted by score and includes the top ten repositories over the verdict threshold. Scores above 95 trigger the requested retirement joke.

Growth rates are estimates, not predictions. Without GH Archive, meaningful growth requires repeat scans separated in time. GitHub Search and GraphQL are subject to API availability and rate limits.

Example table shape:

```text
Repo Name       NEW/OLD  Age  Stars  Growth/Day  TrillionScore  Verdict
owner/project   OLD      420  25000  0.000       61.72          WILL NOT
```