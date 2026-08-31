"""Article quality scoring.

Computes a 0.0–1.0 quality score for articles at scrape time.
Used to gate low-quality articles from signal scoring.
"""

import re

# ── Quality gate threshold ──
QUALITY_THRESHOLD = 0.40  # Articles below this are excluded from signal scoring

# ── Signal pipeline gates ──
SIGNAL_MIN_TICKER_CONFIDENCE = 0.70  # ArticleStock.confidence floor for signal inclusion
# Reddit scraper stores source as reddit_stocks / reddit_wallstreetbets.
# "reddit" is included for tests and any legacy rows.
SIGNAL_EXCLUDED_SOURCES = frozenset({"reddit", "reddit_stocks", "reddit_wallstreetbets"})

# Regex: presence of quantitative financial content
_QUANTITATIVE_RE = re.compile(
    r"\d+\.?\d*\s*%"  # percentages: 12.5%
    r"|\$\s*\d+"  # dollar amounts: $100
    r"|\d+\.?\d*\s*(million|billion|trillion)"  # magnitude numbers
    r"|\b\d+\.?\d*\s*(bps|basis points|cents)"  # financial units
    r"|\b(EPS|revenue|earnings|profit|loss|margin|guidance)"  # earnings keywords near numbers
    r"\s+(of\s+)?\$?\d+",
    re.IGNORECASE,
)


def compute_article_quality(
    source: str,
    raw_text: str | None,
    max_ticker_confidence: float,
    source_credibility_map: dict[str, float],
    default_credibility: float = 0.5,
) -> float:
    """Compute article quality score on a 0.0–1.0 scale.

    Factor weights (sum to 1.0):
      Source credibility       0.40  — from SOURCE_CREDIBILITY map in config
      Quantitative content     0.25  — presence of financial numbers/metrics
      Ticker confidence        0.25  — max ArticleStock.confidence for this article
      Article length (>=150w)  0.10  — proxy for substantive content

    Args:
        source: Article source name (e.g. "reuters", "reddit").
        raw_text: Full article text (or None if unavailable).
        max_ticker_confidence: Highest confidence of any ArticleStock association.
                               Pass 0.0 if the article has no ticker associations.
        source_credibility_map: The SOURCE_CREDIBILITY dict from app.config.
        default_credibility: Credibility to use for unknown sources.

    Returns:
        Float in [0.0, 1.0], rounded to 4 decimal places.
    """
    text = raw_text or ""

    # Factor 1: source credibility (already in [0, 1])
    credibility = source_credibility_map.get(source, default_credibility)

    # Factor 2: quantitative content
    has_quant = bool(_QUANTITATIVE_RE.search(text))
    quant_factor = 1.0 if has_quant else 0.0

    # Factor 3: ticker confidence (already in [0, 1])
    confidence_factor = min(max_ticker_confidence, 1.0)

    # Factor 4: article length
    word_count = len(text.split()) if text else 0
    length_factor = 1.0 if word_count >= 150 else 0.0

    score = 0.40 * credibility + 0.25 * quant_factor + 0.25 * confidence_factor + 0.10 * length_factor

    return round(min(max(score, 0.0), 1.0), 4)
