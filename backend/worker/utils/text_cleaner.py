import re

from bs4 import BeautifulSoup


def strip_html(html: str) -> str:
    """Remove HTML tags and return plain text."""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator=" ", strip=True)


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, max_length: int = 10000) -> str:
    """Truncate text to max_length characters."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def clean_article_text(text: str | None) -> str | None:
    """Full cleaning pipeline for article text."""
    if not text:
        return None
    text = strip_html(text)
    text = normalize_whitespace(text)
    text = truncate(text)
    return text
