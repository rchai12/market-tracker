"""LLM-based structured extraction from financial news articles.

Uses Anthropic Claude Haiku to extract:
- earnings: guidance_change + management_tone
- analyst_rating: rating_change + price_target + analyst_firm

Cost control:
- Only called for earnings and analyst_rating articles
- Article text capped at settings.llm_max_article_chars (default 1500 chars)
- Rate limited by caller (llm_rate_limit_seconds, default 1.0s)
- Fails silently — earnings returns None; analyst returns empty sentinels
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5-20251001"

ANALYST_EMPTY = {"rating_change": "none", "price_target": None, "analyst_firm": None}

EXTRACTION_PROMPT = """\
You are extracting structured data from a financial earnings news article.

Article title: {title}
Article text (may be truncated): {text}

Reply ONLY with a JSON object matching this exact schema:
{{
  "guidance_change": "raised" | "lowered" | "maintained" | "none" | null,
  "management_tone": "confident" | "cautious" | "neutral" | null
}}

Definitions:
- guidance_change:
  "raised"      = company explicitly raised full-year earnings or revenue guidance
  "lowered"     = company explicitly lowered or withdrew guidance
  "maintained"  = company reaffirmed existing guidance without change
  "none"        = guidance is not mentioned in this article
  null          = cannot determine from the text

- management_tone: overall tone of management commentary
  "confident"   = optimistic language, strong outlook, positive forward statements
  "cautious"    = hedging, uncertainty, headwinds, macro concerns mentioned
  "neutral"     = balanced or factual, no strong directional language
  null          = management commentary not present

Output ONLY the JSON object. No explanation, no markdown, no extra text.\
"""

ANALYST_PROMPT = """\
You are extracting structured data from a financial analyst-rating news article.

Article title: {title}
Article text (may be truncated): {text}

Reply ONLY with a JSON object matching this exact schema:
{{
  "rating_change": "upgrade" | "downgrade" | "initiate" | "reiterate" | "maintain" | "none",
  "price_target": <number or null>,
  "analyst_firm": <string or null>
}}

Definitions:
- rating_change:
  "upgrade"    = firm raised its rating (e.g. hold → buy, equal-weight → overweight)
  "downgrade"  = firm lowered its rating (e.g. buy → hold, overweight → underweight)
  "initiate"   = firm initiated / started coverage
  "reiterate"  = firm restated an existing rating without changing it
  "maintain"   = firm kept the rating unchanged (target may still change)
  "none"       = no rating action is described

- price_target: the analyst's price target as a bare number in USD (no $ sign).
  null if no target is mentioned.

- analyst_firm: name of the bank or research firm (e.g. "Goldman Sachs", "J.P. Morgan").
  null if not mentioned.

Output ONLY the JSON object. No explanation, no markdown, no extra text.\
"""


def _haiku_json(prompt: str, max_tokens: int = 64) -> dict | None:
    """Call Claude Haiku and parse a JSON object. Returns None on any failure."""
    try:
        import anthropic

        from app.config import settings

        client_kwargs: dict = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_workspace_id:
            client_kwargs["default_headers"] = {
                "anthropic-workspace-id": settings.anthropic_workspace_id,
            }
        client = anthropic.Anthropic(**client_kwargs)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return parsed

    except Exception as e:
        logger.warning(f"LLM extraction failed: {type(e).__name__}: {e}")
        return None


def extract_earnings_context(
    title: str,
    article_text: str,
    max_chars: int = 1500,
) -> dict | None:
    """Call Claude Haiku to extract guidance_change and management_tone.

    Returns dict with keys 'guidance_change' and 'management_tone', or None on failure.
    All exceptions are caught and logged — never raises to caller.
    """
    text_snippet = (article_text or "")[:max_chars]
    prompt = EXTRACTION_PROMPT.format(title=title, text=text_snippet)
    result = _haiku_json(prompt, max_tokens=64)
    if result is None:
        return None

    valid_guidance = {"raised", "lowered", "maintained", "none", None}
    valid_tone = {"confident", "cautious", "neutral", None}

    guidance = result.get("guidance_change")
    tone = result.get("management_tone")

    if guidance not in valid_guidance:
        guidance = None
    if tone not in valid_tone:
        tone = None

    return {"guidance_change": guidance, "management_tone": tone}


def _parse_price_target(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def extract_analyst_data(
    title: str,
    article_text: str,
    max_chars: int = 1500,
) -> dict:
    """Extract rating_change, price_target, and analyst_firm from an analyst article.

    Always returns a dict. Parse/API failures yield ANALYST_EMPTY sentinels.
    """
    valid_rating = {"upgrade", "downgrade", "initiate", "reiterate", "maintain", "none"}

    text_snippet = (article_text or "")[:max_chars]
    if not title.strip() and not text_snippet.strip():
        return dict(ANALYST_EMPTY)

    prompt = ANALYST_PROMPT.format(title=title, text=text_snippet)
    result = _haiku_json(prompt, max_tokens=96)
    if result is None:
        return dict(ANALYST_EMPTY)

    rating = result.get("rating_change")
    if rating not in valid_rating:
        rating = "none"

    firm = result.get("analyst_firm")
    if not isinstance(firm, str) or not firm.strip():
        firm = None
    else:
        firm = firm.strip()

    return {
        "rating_change": rating,
        "price_target": _parse_price_target(result.get("price_target")),
        "analyst_firm": firm,
    }
