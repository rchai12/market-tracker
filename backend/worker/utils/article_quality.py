"""Article quality scoring.

Computes a 0.0–1.0 quality score for articles at scrape time.
Used to gate low-quality articles from signal scoring.
"""

import re

# ── Quality gate threshold ──
QUALITY_THRESHOLD = 0.40  # Articles below this are excluded from signal scoring

# ── Signal pipeline gates ──
SIGNAL_MIN_TICKER_CONFIDENCE = 0.70  # ArticleStock.confidence floor for signal inclusion
# UI floor for ticker-specific article lists. Keeps company-name matches (0.60)
# and drops industry-keyword sector spray (0.45).
ARTICLE_UI_MIN_TICKER_CONFIDENCE = 0.60
# Reddit scraper stores source as reddit_stocks / reddit_wallstreetbets.
# "reddit" is included for tests and any legacy rows.
SIGNAL_EXCLUDED_SOURCES = frozenset({"reddit", "reddit_stocks", "reddit_wallstreetbets"})

# ── Macro / multi-stock dilution (Phase 25a) ──
DILUTION_SINGLE_STOCK_MAX = 3  # ≤ this many tickers → full weight
DILUTION_FLOOR = 0.20
DILUTION_EXPONENT = 0.35
# Spec names plus live classifier keys (analyst_rating, macro_economic, …).
EVENT_CATEGORY_WEIGHTS: dict[str, float] = {
    "earnings": 1.0,
    "analyst": 1.0,
    "analyst_rating": 1.0,
    "insider": 1.0,
    "insider_trade": 1.0,
    "product": 1.0,
    "product_launch": 1.0,
    "m_a": 1.0,
    "merger_acquisition": 1.0,
    "material_event": 1.0,
    "dividend": 1.0,
    "legal": 0.80,
    "regulatory": 0.60,
    "macro": 0.50,
    "macro_economic": 0.50,
    "general": 0.85,
    "general_news": 0.85,
}


def article_dilution_weight(associated_stock_count: int) -> float:
    """Full weight for company-specific articles, diminishing for sector-wide ones."""
    if associated_stock_count <= DILUTION_SINGLE_STOCK_MAX:
        return 1.0
    weight = 1.0 / (associated_stock_count**DILUTION_EXPONENT)
    return max(weight, DILUTION_FLOOR)


def event_category_weight(category: str | None) -> float:
    """Macro/regulatory events contribute less than company-specific ones."""
    if not category:
        return 1.0
    return EVENT_CATEGORY_WEIGHTS.get(category, 1.0)


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
