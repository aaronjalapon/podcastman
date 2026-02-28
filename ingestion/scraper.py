"""Web scraping: URL → clean article text."""

from __future__ import annotations

import httpx
from newspaper import Article

from utils.helpers import get_logger

log = get_logger(__name__)


def scrape_url(url: str) -> dict:
    """Extract article content from a URL.

    Returns a dict with keys: title, text, authors, publish_date.
    Uses newspaper3k as primary extractor, httpx + BS4 as fallback.
    """
    log.info("Scraping URL: %s", url)

    try:
        return _scrape_with_newspaper(url)
    except Exception as exc:
        log.warning("newspaper3k failed (%s), falling back to httpx+BS4", exc)
        return _scrape_with_bs4(url)


def _scrape_with_newspaper(url: str) -> dict:
    """Primary extraction using newspaper3k."""
    article = Article(url)
    article.download()
    article.parse()

    if not article.text or len(article.text.strip()) < 100:
        raise ValueError("Extracted text too short – likely extraction failure")

    return {
        "title": article.title or "Untitled",
        "text": article.text,
        "authors": article.authors,
        "publish_date": str(article.publish_date or ""),
    }


def _scrape_with_bs4(url: str) -> dict:
    """Fallback extraction using httpx + BeautifulSoup."""
    from bs4 import BeautifulSoup

    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove unwanted elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "ad"]):
        tag.decompose()

    # Try common article containers
    article_el = (
        soup.find("article")
        or soup.find("div", class_="post-content")
        or soup.find("div", class_="entry-content")
        or soup.find("main")
    )
    container = article_el or soup.body or soup

    # Extract text from paragraphs
    paragraphs = container.find_all("p")
    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    title = h1_tag.get_text(strip=True) if h1_tag else (title_tag.get_text(strip=True) if title_tag else "Untitled")

    if len(text.strip()) < 100:
        # Last resort: grab all visible text
        text = container.get_text(separator="\n", strip=True)

    return {
        "title": title,
        "text": text,
        "authors": [],
        "publish_date": "",
    }
