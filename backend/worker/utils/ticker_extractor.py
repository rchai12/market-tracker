import re

# Suffixes to strip when building short company names
_COMPANY_SUFFIXES = re.compile(
    r"\s+(?:Inc\.?|Corporation|Corp\.?|Company|Co\.?|Limited|Ltd\.?|plc|"
    r"Class [A-Z]|Incorporated|Group|Trust|ETF|Holdings)$",
    re.IGNORECASE,
)

# Common short words that shouldn't be used as standalone company name matches
_NAME_TOO_SHORT = {"US", "AT", "A", "I", "IT"}


def _build_company_variations(company_name: str) -> list[str]:
    """Generate matchable name variations from a company name.

    E.g. "Oracle Corporation" -> ["Oracle Corporation", "Oracle"]
         "Walt Disney Company" -> ["Walt Disney Company", "Walt Disney"]
         "Apple Inc" -> ["Apple Inc", "Apple"]
    """
    variations = [company_name]
    short = _COMPANY_SUFFIXES.sub("", company_name).strip()
    if short and short != company_name and len(short) > 2 and short not in _NAME_TOO_SHORT:
        variations.append(short)
    return variations


def extract_tickers(
    title: str,
    body: str | None,
    known_tickers: set[str],
    company_map: dict[str, str] | None = None,
) -> list[tuple[str, float]]:
    """
    Extract stock tickers from article text.

    Returns list of (ticker, confidence) tuples.

    Strategy:
    1. $TICKER patterns (confidence 0.95)
    2. Parenthetical tickers like (AAPL) (confidence 0.90)
    3. Exact ALL CAPS matches against known tickers (confidence 0.70)
    4. Company name mentions (confidence 0.60)
    """
    results: dict[str, float] = {}
    text = f"{title} {body or ''}"

    # Pattern 1: $TICKER notation (high confidence)
    dollar_tickers = re.findall(r"\$([A-Z]{1,5})\b", text)
    for ticker in dollar_tickers:
        if ticker in known_tickers:
            results[ticker] = max(results.get(ticker, 0), 0.95)

    # Pattern 2: Parenthetical tickers like (AAPL), (NVDA)
    paren_tickers = re.findall(r"\(([A-Z]{1,5})\)", text)
    for ticker in paren_tickers:
        if ticker in known_tickers:
            results[ticker] = max(results.get(ticker, 0), 0.90)

    # Pattern 3: ALL CAPS words matching known tickers
    excluded = {"A", "I", "CEO", "CFO", "CTO", "IPO", "SEC", "FDA", "GDP", "CPI",
                "ETF", "NYSE", "USA", "API", "IT", "US", "PM", "AM", "TV", "AI", "UK"}
    words = re.findall(r"\b([A-Z]{1,5})\b", text)
    for word in words:
        if word in known_tickers and word not in excluded:
            results[word] = max(results.get(word, 0), 0.70)

    # Pattern 4: Company name matching (case-insensitive)
    if company_map:
        text_lower = text.lower()
        for name, ticker in company_map.items():
            if name.lower() in text_lower:
                results[ticker] = max(results.get(ticker, 0), 0.60)

    return sorted(results.items(), key=lambda x: x[1], reverse=True)


# ── Industry keyword mapping ──
# Maps keywords/phrases to industries they're relevant to.
# Cross-cutting macro themes map to multiple industries.
KEYWORD_INDUSTRY_MAP: dict[str, list[str]] = {
    # Energy: Oil & Gas
    "crude oil": ["Oil & Gas Integrated", "Oil & Gas E&P"],
    "oil prices": ["Oil & Gas Integrated", "Oil & Gas Refining"],
    "oil sanctions": ["Oil & Gas Integrated", "Oil & Gas E&P"],
    "oil exploration": ["Oil & Gas E&P"],
    "oilfield services": ["Oil & Gas Equipment"],
    "gasoline prices": ["Oil & Gas Refining"],
    "fuel prices": ["Oil & Gas Refining"],
    "natural gas": ["Oil & Gas Midstream", "Oil & Gas E&P"],
    "gas pipeline": ["Oil & Gas Midstream"],
    "oil": ["Oil & Gas Integrated"],
    "petroleum": ["Oil & Gas Integrated"],
    "opec": ["Oil & Gas Integrated", "Oil & Gas E&P"],
    "brent": ["Oil & Gas Integrated"],
    "wti": ["Oil & Gas Integrated"],
    "shale": ["Oil & Gas E&P"],
    "drilling": ["Oil & Gas E&P", "Oil & Gas Equipment"],
    "fracking": ["Oil & Gas E&P"],
    "rig count": ["Oil & Gas Equipment"],
    "refinery": ["Oil & Gas Refining"],
    "pipeline": ["Oil & Gas Midstream"],
    "lng": ["Oil & Gas Midstream"],
    # Financials
    "interest rate": ["Banks", "Capital Markets", "Insurance"],
    "fed rate": ["Banks", "Capital Markets"],
    "rate hike": ["Banks", "Capital Markets", "Insurance"],
    "rate cut": ["Banks", "Capital Markets", "Insurance"],
    "digital payments": ["Payments"],
    "credit card": ["Payments"],
    "banking": ["Banks"],
    "bank": ["Banks"],
    "loan": ["Banks"],
    "mortgage": ["Banks"],
    "deposit": ["Banks"],
    "insurance": ["Insurance"],
    "underwriting": ["Insurance"],
    "reinsurance": ["Insurance"],
    "asset management": ["Capital Markets"],
    "credit rating": ["Capital Markets"],
    "stock exchange": ["Capital Markets"],
    "payment": ["Payments"],
    "fintech": ["Payments", "Banks"],
    # Technology
    "chip shortage": ["Semiconductors", "Consumer Electronics"],
    "ai chip": ["Semiconductors"],
    "cloud computing": ["Software"],
    "enterprise software": ["Software"],
    "semiconductor": ["Semiconductors"],
    "chip": ["Semiconductors"],
    "gpu": ["Semiconductors"],
    "wafer": ["Semiconductors"],
    "foundry": ["Semiconductors"],
    "saas": ["Software"],
    "cybersecurity": ["Cybersecurity"],
    "data breach": ["Cybersecurity"],
    "ransomware": ["Cybersecurity"],
    # Comms / Media
    "online advertising": ["Social Media"],
    "social media": ["Social Media"],
    "digital ads": ["Social Media"],
    "ad revenue": ["Social Media"],
    "streaming": ["Streaming & Entertainment"],
    "box office": ["Streaming & Entertainment"],
    "subscriber": ["Streaming & Entertainment"],
    "5g": ["Telecom"],
    "wireless": ["Telecom"],
    "broadband": ["Telecom"],
    "telecom": ["Telecom"],
    # Consumer
    "online retail": ["E-Commerce", "Retail"],
    "online shopping": ["E-Commerce"],
    "e-commerce": ["E-Commerce"],
    "electric vehicle": ["EV & Auto"],
    "autonomous driving": ["EV & Auto"],
    "charging station": ["EV & Auto"],
    "ev": ["EV & Auto"],
    "battery": ["EV & Auto"],
    "retail sales": ["Retail"],
    "home improvement": ["Retail"],
    "consumer spending": ["Retail", "Restaurants", "E-Commerce", "Streaming & Entertainment"],
    "restaurant": ["Restaurants"],
    "fast food": ["Restaurants"],
    # Cross-cutting macro themes
    "tariff": ["Semiconductors", "Consumer Electronics", "Retail", "EV & Auto", "E-Commerce"],
    "trade war": ["Semiconductors", "Consumer Electronics", "Retail", "EV & Auto"],
    "sanctions": ["Oil & Gas Integrated", "Oil & Gas E&P", "Banks"],
    "inflation": ["Retail", "Restaurants", "Consumer Electronics"],
    "china": ["Semiconductors", "Consumer Electronics", "Software"],
    "supply chain": ["Semiconductors", "Consumer Electronics", "EV & Auto", "Retail"],
    "regulation": ["Banks", "Capital Markets", "Payments", "Social Media"],
    "antitrust": ["Software", "Social Media", "E-Commerce"],
}

# Pre-sort keywords by length (longest first) to match specific phrases before generic ones
_SORTED_KEYWORDS = sorted(KEYWORD_INDUSTRY_MAP.keys(), key=len, reverse=True)


def match_industry_keywords(title: str, body: str | None) -> set[str]:
    """Scan article text for industry-relevant keywords.

    Returns set of matched industry names. Matches longer phrases first
    to prefer "crude oil" over "oil".
    """
    text = f"{title} {body or ''}".lower()
    matched_industries: set[str] = set()

    for keyword in _SORTED_KEYWORDS:
        if keyword in text:
            matched_industries.update(KEYWORD_INDUSTRY_MAP[keyword])

    return matched_industries


def build_company_map(stocks: list[tuple[str, str]]) -> dict[str, str]:
    """Build a company name -> ticker map from (ticker, company_name) pairs.

    Generates variations for better matching.
    """
    name_map: dict[str, str] = {}
    for ticker, company_name in stocks:
        for variation in _build_company_variations(company_name):
            # Longer names take priority to avoid false positives
            if variation not in name_map or len(ticker) < len(name_map[variation]):
                name_map[variation] = ticker
    return name_map
