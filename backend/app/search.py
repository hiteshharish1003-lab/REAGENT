import hashlib
import json
import re
from urllib.parse import urlparse

import httpx

from . import mock
from .config import settings
from .llm import BudgetExceeded, Usage

# Cheap, transparent source-quality heuristic. Explainable beats clever here.
HIGH = (".gov", ".edu", ".int", "who.int", "worldbank.org", "iea.org", "oecd.org", "nature.com", "arxiv.org")
MID = ("reuters.com", "bbc.com", "ft.com", "economist.com", "wikipedia.org", "bloomberg.com", "mckinsey.com")
LOW = ("medium.com", "blogspot", "quora.com", "reddit.com", "substack.com")


def score_domain(domain: str) -> tuple[float, str]:
    if any(h in domain for h in HIGH):
        return 0.9, "Official / academic domain"
    if any(m in domain for m in MID):
        return 0.7, "Established publisher"
    if any(low in domain for low in LOW):
        return 0.3, "User-generated or opinion platform"
    return 0.5, "General web source"


def _cache_path(query: str):
    return settings.cache_dir / (hashlib.sha1(query.encode()).hexdigest() + ".json")


async def search(query: str, usage: Usage) -> list[dict]:
    """Return [{title, url, content}]. Cached on disk so reruns are free and reproducible."""
    if settings.mock_search:
        return mock.search_results(query)

    path = _cache_path(query)
    if path.exists():
        return json.loads(path.read_text())

    if usage.searches >= settings.max_searches_per_run:
        raise BudgetExceeded("search budget exhausted")
    usage.searches += 1

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": settings.results_per_search,
                "search_depth": "advanced",
                "include_answer": False,
            },
        )
        r.raise_for_status()
        results = [
            {"title": x["title"], "url": x["url"], "content": x.get("content", "")}
            for x in r.json().get("results", [])
        ]
    path.write_text(json.dumps(results))
    return results


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return re.sub(r"^www\.", "", host)
