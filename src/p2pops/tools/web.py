"""Fetches and extracts readable text from an external article link.

Used to enrich an HN/Reddit post that just links out, so downstream agents get
real article content instead of a bare title + URL. Deliberately not used to
scrape Reddit itself -- Reddit content comes through PRAW's OAuth API, since
Reddit deprecated unauthenticated .json scraping in 2026.
"""

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "p2pops/0.1 (portfolio project; research agent)"


def fetch_article_text(url: str, max_chars: int = 4000) -> str:
    """Fetch `url` and return its main readable text, truncated to max_chars.

    Never returns an empty string: agent frameworks pass this straight back
    as a tool-result message, and some providers' chat-completion schemas
    (Groq's OpenAI-compatible endpoint, at least) reject a message with
    empty content outright -- so a genuinely empty extraction gets an
    explicit placeholder instead, same as the fetch-failure case below.
    """
    try:
        response = httpx.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=10.0, follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"(could not fetch article: {exc})"

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    text = " ".join(soup.get_text(separator=" ").split())[:max_chars]
    return text or "(no readable text found on this page)"
