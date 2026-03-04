import re


def extract_tickers(title: str, body: str | None, known_tickers: set[str]) -> list[tuple[str, float]]:
    """
    Extract stock tickers from article text.

    Returns list of (ticker, confidence) tuples.

    Strategy:
    1. $TICKER patterns (confidence 0.95)
    2. Exact ALL CAPS matches against known tickers (confidence 0.70)
    """
    results: dict[str, float] = {}
    text = f"{title} {body or ''}"

    # Pattern 1: $TICKER notation (high confidence)
    dollar_tickers = re.findall(r"\$([A-Z]{1,5})\b", text)
    for ticker in dollar_tickers:
        if ticker in known_tickers:
            results[ticker] = max(results.get(ticker, 0), 0.95)

    # Pattern 2: ALL CAPS words matching known tickers
    # Exclude common words that happen to be short caps
    excluded = {"A", "I", "CEO", "CFO", "CTO", "IPO", "SEC", "FDA", "GDP", "CPI", "ETF", "NYSE", "USA", "API"}
    words = re.findall(r"\b([A-Z]{1,5})\b", text)
    for word in words:
        if word in known_tickers and word not in excluded:
            results[word] = max(results.get(word, 0), 0.70)

    return sorted(results.items(), key=lambda x: x[1], reverse=True)
