"""General web search, via DuckDuckGo's keyless HTML endpoint.

Broadens the Research Agent beyond Hacker News (Feature: discover anywhere
on the web) without introducing a paid/keyed search API. Deliberately the
same shape as tools/hn.py: a plain function returning pydantic models, so
the MCP server can expose it identically. Results still flow through the
exact same Guardrail -> dedupe -> Analyst chain, so source breadth never
lowers the quality bar.

DDG's HTML endpoint is scrape-based and can change or throttle; every
failure path degrades to an explicit "no results" answer rather than
raising, because a broken search tool must never kill a discovery run.
"""

import logging
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = "Mozilla/5.0 (compatible; p2pops/0.1; portfolio research agent)"


class WebResult(BaseModel):
    title: str
    url: str
    snippet: str = ""


def _decode_ddg_href(href: str) -> str | None:
    """DDG result links are redirect wrappers (`/l/?uddg=<real-url>`);
    unwrap to the real destination. Direct links pass through."""
    if href.startswith("http") and "duckduckgo.com/l/" not in href:
        return href
    parsed = urlparse(href)
    uddg = parse_qs(parsed.query).get("uddg")
    if uddg:
        return unquote(uddg[0])
    return None


def search_web(query: str, limit: int = 6) -> list[WebResult]:
    """Search the web for `query`. Returns [] on any failure (logged)."""
    try:
        response = httpx.post(
            DDG_HTML_URL,
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=12.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("web search failed for %r: %s", query, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[WebResult] = []
    for item in soup.select("div.result"):
        link = item.select_one("a.result__a")
        if link is None or not link.get("href"):
            continue
        url = _decode_ddg_href(link["href"])
        if not url:
            continue
        snippet_el = item.select_one("a.result__snippet, div.result__snippet")
        snippet = " ".join(snippet_el.get_text(" ").split()) if snippet_el else ""
        results.append(WebResult(title=link.get_text(" ").strip() or "(untitled)", url=url, snippet=snippet[:300]))
        if len(results) >= limit:
            break
    return results
