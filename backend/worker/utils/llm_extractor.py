"""LLM-based structured extraction from financial news articles.

Uses Google Gemini Flash to extract earnings guidance changes and management tone
from earnings-related articles. Returns structured JSON.

Cost control:
- Only called for articles with event_category = "earnings"
- Article text capped at settings.llm_max_article_chars (default 1500 chars)
- Rate limited by caller (llm_rate_limit_seconds, default 2.0s → ~30 RPM max,
  safely under the free-tier limit of 15 RPM with 2s delay)
- Fails silently (returns None) on any API or parsing error

Output schema:
  {
    "guidance_change": "raised" | "lowered" | "maintained" | "none" | null,
    "management_tone": "confident" | "cautious" | "neutral" | null
  }
"""

import json
import logging

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-1.5-flash"

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


def extract_earnings_context(
    title: str,
    article_text: str,
    max_chars: int = 1500,
) -> dict | None:
    """Call Gemini Flash to extract guidance_change and management_tone.

    Returns dict with keys 'guidance_change' and 'management_tone', or None on failure.
    All exceptions are caught and logged — never raises to caller.
    """
    try:
        from google import genai
        from google.genai import types
        from app.config import settings

        client = genai.Client(api_key=settings.gemini_api_key)

        text_snippet = (article_text or "")[:max_chars]
        prompt = EXTRACTION_PROMPT.format(title=title, text=text_snippet)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=64,
                temperature=0.0,  # deterministic output for structured extraction
            ),
        )

        raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)

        valid_guidance = {"raised", "lowered", "maintained", "none", None}
        valid_tone = {"confident", "cautious", "neutral", None}

        guidance = result.get("guidance_change")
        tone = result.get("management_tone")

        # Validate — reject unexpected values rather than storing garbage
        if guidance not in valid_guidance:
            guidance = None
        if tone not in valid_tone:
            tone = None

        return {"guidance_change": guidance, "management_tone": tone}

    except Exception as e:
        logger.warning(f"LLM extraction failed: {type(e).__name__}: {e}")
        return None
