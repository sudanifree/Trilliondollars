from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gh_archive import GHArchiveError
from github_client import GitHubAPIError
from oracle import OracleService

load_dotenv()

app = FastAPI(title="Trillion Dollar Oracle", version="1.0.0")
cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "https://sudanifree.github.io,http://localhost:8443,http://127.0.0.1:8443",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=os.getenv(
        "CORS_ORIGIN_REGEX",
        r"https://[a-z0-9-]+-8443\.app\.github\.dev",
    ),
    allow_methods=["GET"],
    allow_headers=["Accept"],
)
oracle = OracleService()


class ScanResponse(BaseModel):
    results: list[dict]
    top_ten: list[dict]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/scan", response_model=ScanResponse)
def scan(
    query: str = Query(min_length=1, description="GitHub repository search query"),
    limit: int = Query(default=20, ge=1, le=100),
) -> ScanResponse:
    try:
        results = oracle.scan(query, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GitHubAPIError, GHArchiveError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ScanResponse(
        results=[result.to_dict() for result in results],
        top_ten=[result.to_dict() for result in oracle.top_ten(results)],
    )
