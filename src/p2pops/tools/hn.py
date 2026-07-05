"""Hacker News discovery, via the keyless Algolia HN Search API.

No auth or rate-limit registration needed, which is why HN is the primary
discovery source (Reddit's own OAuth API is a secondary source, added once
a Reddit app is registered).
"""

import httpx
from pydantic import BaseModel

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


class HNStory(BaseModel):
    title: str
    url: str | None = None
    points: int
    num_comments: int
    hn_url: str
    created_at: str


def search_hn(query: str, limit: int = 10) -> list[HNStory]:
    """Search Hacker News stories matching `query`, ranked by relevance."""
    response = httpx.get(
        HN_SEARCH_URL,
        params={"query": query, "tags": "story", "hitsPerPage": limit},
        timeout=10.0,
    )
    response.raise_for_status()
    hits = response.json().get("hits", [])

    stories = []
    for hit in hits:
        stories.append(
            HNStory(
                title=hit.get("title") or "(untitled)",
                url=hit.get("url"),
                points=hit.get("points") or 0,
                num_comments=hit.get("num_comments") or 0,
                hn_url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
                created_at=hit.get("created_at") or "",
            )
        )
    return stories
