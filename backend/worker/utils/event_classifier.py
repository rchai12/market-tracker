"""Rule-based event classification for financial articles.

Classifies articles into categories based on keyword patterns in title and body text.
Follows the same longest-first matching approach as KEYWORD_INDUSTRY_MAP in ticker_extractor.py.
"""

# Keyword phrases mapped to event categories, sorted longest-first at runtime for specificity.
EVENT_KEYWORD_MAP: dict[str, str] = {
    # Earnings / Financial Results
    "earnings per share": "earnings",
    "earnings surprise": "earnings",
    "earnings report": "earnings",
    "earnings beat": "earnings",
    "earnings miss": "earnings",
    "quarterly results": "earnings",
    "quarterly earnings": "earnings",
    "quarterly revenue": "earnings",
    "annual results": "earnings",
    "annual earnings": "earnings",
    "revenue beat": "earnings",
    "revenue miss": "earnings",
    "profit warning": "earnings",
    "profit margin": "earnings",
    "fiscal quarter": "earnings",
    "guidance": "earnings",
    "eps": "earnings",
    "10-q": "earnings",
    "10-k": "earnings",
    # Mergers & Acquisitions
    "merger agreement": "merger_acquisition",
    "acquisition of": "merger_acquisition",
    "takeover bid": "merger_acquisition",
    "hostile takeover": "merger_acquisition",
    "acquisition": "merger_acquisition",
    "merger": "merger_acquisition",
    "takeover": "merger_acquisition",
    "buyout": "merger_acquisition",
    "acquires": "merger_acquisition",
    "acquiring": "merger_acquisition",
    # Regulatory
    "sec investigation": "regulatory",
    "fda approval": "regulatory",
    "fda rejection": "regulatory",
    "fda clearance": "regulatory",
    "antitrust": "regulatory",
    "regulatory approval": "regulatory",
    "regulatory filing": "regulatory",
    "compliance": "regulatory",
    "regulation": "regulatory",
    # Product Launches
    "product launch": "product_launch",
    "new product": "product_launch",
    "launches": "product_launch",
    "unveils": "product_launch",
    "announces new": "product_launch",
    "rolls out": "product_launch",
    # Analyst Ratings
    "price target": "analyst_rating",
    "rating change": "analyst_rating",
    "upgrades": "analyst_rating",
    "downgrades": "analyst_rating",
    "initiates coverage": "analyst_rating",
    "overweight": "analyst_rating",
    "underweight": "analyst_rating",
    "outperform": "analyst_rating",
    "underperform": "analyst_rating",
    "buy rating": "analyst_rating",
    "sell rating": "analyst_rating",
    "hold rating": "analyst_rating",
    # Insider Trading
    "insider trading": "insider_trade",
    "insider buying": "insider_trade",
    "insider selling": "insider_trade",
    "insider purchase": "insider_trade",
    "insider sale": "insider_trade",
    "form 4": "insider_trade",
    "8-k": "material_event",
    # Macro Economic
    "interest rate": "macro_economic",
    "federal reserve": "macro_economic",
    "fed rate": "macro_economic",
    "rate hike": "macro_economic",
    "rate cut": "macro_economic",
    "inflation": "macro_economic",
    "unemployment": "macro_economic",
    "gdp": "macro_economic",
    "consumer price index": "macro_economic",
    "cpi": "macro_economic",
    "treasury yield": "macro_economic",
    "yield curve": "macro_economic",
    "jobs report": "macro_economic",
    "nonfarm payroll": "macro_economic",
    # Legal
    "lawsuit": "legal",
    "class action": "legal",
    "settlement": "legal",
    "litigation": "legal",
    "court ruling": "legal",
    "indictment": "legal",
    "subpoena": "legal",
    # Dividend
    "dividend increase": "dividend",
    "dividend cut": "dividend",
    "special dividend": "dividend",
    "dividend yield": "dividend",
    "dividend": "dividend",
    "stock buyback": "dividend",
    "share repurchase": "dividend",
}

# Source-level overrides: these sources always produce a specific category.
SOURCE_CATEGORY_OVERRIDES: dict[str, str] = {
    "fred": "macro_economic",
}

# Pre-sort keywords by length (longest first) for greedy matching.
_SORTED_KEYWORDS = sorted(EVENT_KEYWORD_MAP.keys(), key=len, reverse=True)


def classify_event(title: str, body: str | None = None, source: str | None = None) -> str:
    """Classify an article into an event category based on keywords.

    Args:
        title: Article headline (required).
        body: Article body text (optional).
        source: Scraper source name (optional), for source-level overrides.

    Returns:
        Event category string. Defaults to "general_news" if no keywords match.
    """
    # Source-level override
    if source and source in SOURCE_CATEGORY_OVERRIDES:
        return SOURCE_CATEGORY_OVERRIDES[source]

    # Build searchable text (lowercase for case-insensitive matching)
    text = title.lower()
    if body:
        text += " " + body.lower()

    # Longest-first keyword matching
    for keyword in _SORTED_KEYWORDS:
        if keyword in text:
            return EVENT_KEYWORD_MAP[keyword]

    return "general_news"
