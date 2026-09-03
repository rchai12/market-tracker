"""Tests for Phase 21d Claude Haiku earnings-context extraction."""

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from worker.beat_schedule import beat_schedule
from worker.tasks.sentiment.llm_extraction_task import (
    EARNINGS_MATCH_DAYS,
    LLM_MIN_QUALITY_SCORE,
    _run_extraction_async,
    _update_earnings_guidance,
    run_llm_extraction,
)
from worker.utils.llm_extractor import CLAUDE_MODEL, extract_earnings_context

NOW = datetime(2026, 8, 31, 16, 0, tzinfo=timezone.utc)
VALID_JSON = '{"guidance_change": "raised", "management_tone": "confident"}'


def _install_anthropic(response_text: str | None = VALID_JSON, error: Exception | None = None):
    """Inject a fake anthropic module matching extract_earnings_context imports."""
    anthropic_mod = MagicMock()
    client = MagicMock()
    if error is not None:
        client.messages.create.side_effect = error
    else:
        block = MagicMock()
        block.text = response_text
        resp = MagicMock()
        resp.content = [block]
        client.messages.create.return_value = resp
    anthropic_mod.Anthropic.return_value = client
    sys.modules["anthropic"] = anthropic_mod
    return client.messages


def _extract(
    text="Apple raised full-year guidance.",
    title="AAPL earnings",
    max_chars=1500,
    api_key="fake-key",
    workspace_id=None,
):
    with patch("app.config.settings") as settings:
        settings.anthropic_api_key = api_key
        settings.anthropic_workspace_id = workspace_id
        return extract_earnings_context(title, text, max_chars=max_chars)


class TestExtractEarningsContext:
    def teardown_method(self):
        sys.modules.pop("anthropic", None)

    def test_valid_json_parsed(self):
        _install_anthropic(VALID_JSON)
        result = _extract()
        assert result == {"guidance_change": "raised", "management_tone": "confident"}

    def test_uses_haiku_model(self):
        messages = _install_anthropic(VALID_JSON)
        _extract()
        assert messages.create.call_args.kwargs["model"] == CLAUDE_MODEL
        assert CLAUDE_MODEL == "claude-haiku-4-5-20251001"

    def test_workspace_id_sent_as_header(self):
        _install_anthropic(VALID_JSON)
        anthropic_mod = sys.modules["anthropic"]
        _extract(workspace_id="wrkspc_test123")
        kwargs = anthropic_mod.Anthropic.call_args.kwargs
        assert kwargs["default_headers"]["anthropic-workspace-id"] == "wrkspc_test123"

    def test_no_workspace_header_when_unset(self):
        _install_anthropic(VALID_JSON)
        anthropic_mod = sys.modules["anthropic"]
        _extract(workspace_id=None)
        assert "default_headers" not in anthropic_mod.Anthropic.call_args.kwargs

    def test_api_exception_returns_none(self):
        _install_anthropic(error=RuntimeError("boom"))
        assert _extract() is None

    def test_invalid_guidance_rejected(self):
        _install_anthropic('{"guidance_change": "soared", "management_tone": "confident"}')
        result = _extract()
        assert result["guidance_change"] is None
        assert result["management_tone"] == "confident"

    def test_invalid_tone_rejected(self):
        _install_anthropic('{"guidance_change": "raised", "management_tone": "ecstatic"}')
        result = _extract()
        assert result["guidance_change"] == "raised"
        assert result["management_tone"] is None

    def test_none_guidance_sentinel_returned(self):
        _install_anthropic('{"guidance_change": "none", "management_tone": "neutral"}')
        result = _extract()
        assert result["guidance_change"] == "none"
        assert result["management_tone"] == "neutral"

    def test_empty_article_text_no_crash(self):
        messages = _install_anthropic(VALID_JSON)
        result = _extract(text="")
        assert result is not None
        prompt = messages.create.call_args.kwargs["messages"][0]["content"]
        assert "Article text (may be truncated): " in prompt

    def test_text_truncated_to_max_chars(self):
        messages = _install_anthropic(VALID_JSON)
        long_text = "A" * 500
        _extract(text=long_text, max_chars=20)
        prompt = messages.create.call_args.kwargs["messages"][0]["content"]
        assert ("A" * 20) in prompt
        assert ("A" * 21) not in prompt

    def test_empty_api_key_returns_none(self):
        _install_anthropic(error=ValueError("Missing API key"))
        assert _extract(api_key="") is None

    def test_markdown_fences_stripped(self):
        fenced = "```json\n" + VALID_JSON + "\n```"
        _install_anthropic(fenced)
        result = _extract()
        assert result["guidance_change"] == "raised"


def _cm(session):
    class CM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    return CM()


class TestRunLlmExtractionGuards:
    def test_disabled_skips_without_db(self):
        with (
            patch("worker.tasks.sentiment.llm_extraction_task.settings") as s,
            patch("worker.tasks.sentiment.llm_extraction_task.run_async") as run_async,
        ):
            s.llm_extraction_enabled = False
            s.anthropic_api_key = "present"
            result = run_llm_extraction.run()
        assert result == {"skipped": True, "reason": "llm_extraction_disabled"}
        run_async.assert_not_called()

    def test_empty_key_skips_without_api(self):
        with (
            patch("worker.tasks.sentiment.llm_extraction_task.settings") as s,
            patch("worker.tasks.sentiment.llm_extraction_task.run_async") as run_async,
            patch("worker.tasks.sentiment.llm_extraction_task.extract_earnings_context") as extract,
        ):
            s.llm_extraction_enabled = True
            s.anthropic_api_key = ""
            result = run_llm_extraction.run()
        assert result == {"skipped": True, "reason": "no_api_key"}
        run_async.assert_not_called()
        extract.assert_not_called()


def _article(**overrides):
    base = dict(
        id=11,
        title="AAPL beats and raises",
        raw_text="Apple raised full-year guidance.",
        summary=None,
        published_at=NOW,
        metadata_={},
        llm_extracted=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class UpdateSession:
    """Session used after extract_earnings_context returns."""

    def __init__(self, art, stock_ids=None, estimates=None):
        self.art = art
        self.stock_ids = stock_ids or []
        self.estimates = list(estimates or [])
        self.committed = False
        self.stmts = []
        self._execute_i = 0

    async def get(self, _model, pk):
        return self.art if pk == self.art.id else None

    async def execute(self, stmt):
        self.stmts.append(stmt)
        self._execute_i += 1
        result = MagicMock()
        if self._execute_i == 1:
            result.all.return_value = [SimpleNamespace(stock_id=s) for s in self.stock_ids]
            return result
        ee = self.estimates.pop(0) if self.estimates else None
        result.scalar_one_or_none.return_value = ee
        return result

    async def commit(self):
        self.committed = True


class ListSession:
    def __init__(self, articles, quality_skipped=0):
        self.articles = articles
        self.quality_skipped = quality_skipped
        self.stmts = []

    async def execute(self, stmt):
        self.stmts.append(stmt)
        result = MagicMock()
        result.scalars.return_value.unique.return_value.all.return_value = self.articles
        result.scalar_one.return_value = self.quality_skipped
        return result


def _run_loop(articles, extract_result, update_session, **setting_overrides):
    settings_ns = SimpleNamespace(
        llm_max_article_chars=1500,
        llm_rate_limit_seconds=0,
        **setting_overrides,
    )
    sessions = [_cm(ListSession(articles)), _cm(update_session)]

    with (
        patch("worker.tasks.sentiment.llm_extraction_task.async_session", side_effect=sessions),
        patch(
            "worker.tasks.sentiment.llm_extraction_task.extract_earnings_context",
            return_value=extract_result,
        ),
        patch("worker.tasks.sentiment.llm_extraction_task.settings", settings_ns),
        patch("worker.tasks.sentiment.llm_extraction_task.time.sleep"),
    ):
        return asyncio.run(_run_extraction_async())


class TestRunExtractionAsync:
    def test_guidance_raised_updates_estimate(self):
        art = _article()
        ee = SimpleNamespace(id=1, stock_id=7, earnings_date=date(2026, 9, 1), guidance_change=None)
        update = UpdateSession(art, stock_ids=[7], estimates=[ee])
        result = _run_loop(
            [art],
            {"guidance_change": "raised", "management_tone": "confident"},
            update,
        )
        assert result["extracted"] == 1
        assert result["errors"] == 0
        assert ee.guidance_change == "raised"
        assert art.llm_extracted is True
        assert art.metadata_["management_tone"] == "confident"
        assert update.committed is True

    def test_tone_stored_in_metadata(self):
        art = _article()
        update = UpdateSession(art, stock_ids=[])
        _run_loop(
            [art],
            {"guidance_change": "none", "management_tone": "cautious"},
            update,
        )
        assert art.metadata_["management_tone"] == "cautious"
        assert art.llm_extracted is True

    def test_existing_guidance_not_overwritten(self):
        art = _article()
        # SQL filters IS NULL, so no row is returned for an already-set estimate
        update = UpdateSession(art, stock_ids=[7], estimates=[])
        _run_loop(
            [art],
            {"guidance_change": "raised", "management_tone": "confident"},
            update,
        )
        sql = str(update.stmts[-1].compile(compile_kwargs={"literal_binds": True})).lower()
        assert "guidance_change" in sql
        assert "is null" in sql or "isnull" in sql.replace(" ", "")

    def test_extract_none_marks_failed(self):
        art = _article()
        update = UpdateSession(art)
        result = _run_loop([art], None, update)
        assert art.llm_extracted is False
        assert result["errors"] == 1
        assert result["extracted"] == 0
        assert update.stmts == []  # no EarningsEstimate lookup

    def test_no_article_stocks_still_marks_extracted(self):
        art = _article()
        update = UpdateSession(art, stock_ids=[])
        result = _run_loop(
            [art],
            {"guidance_change": "raised", "management_tone": "neutral"},
            update,
        )
        assert art.llm_extracted is True
        assert result["extracted"] == 1
        assert len(update.stmts) == 1  # ArticleStock lookup only

    def test_guidance_none_does_not_update_estimate(self):
        art = _article()
        ee = SimpleNamespace(id=1, stock_id=7, earnings_date=date(2026, 9, 1), guidance_change=None)
        update = UpdateSession(art, stock_ids=[7], estimates=[ee])
        result = _run_loop(
            [art],
            {"guidance_change": "none", "management_tone": "neutral"},
            update,
        )
        assert ee.guidance_change is None
        assert art.llm_extracted is True
        assert result["extracted"] == 1
        assert result["skipped"] == 1
        assert update.stmts == []  # skipped _update_earnings_guidance

    def test_empty_text_increments_skipped_without_api(self):
        art = _article(raw_text="", summary=None)
        update = UpdateSession(art)
        result = _run_loop([art], {"guidance_change": "raised", "management_tone": "confident"}, update)
        assert art.llm_extracted is False
        assert result["skipped"] == 1
        assert result["extracted"] == 0
        assert result["errors"] == 0

    def test_query_filters_quality_score_at_least_060(self):
        art = _article()
        list_session = ListSession([art], quality_skipped=4)
        update = UpdateSession(art, stock_ids=[])
        settings_ns = SimpleNamespace(llm_max_article_chars=1500, llm_rate_limit_seconds=0)
        sessions = [_cm(list_session), _cm(update)]
        with (
            patch("worker.tasks.sentiment.llm_extraction_task.async_session", side_effect=sessions),
            patch(
                "worker.tasks.sentiment.llm_extraction_task.extract_earnings_context",
                return_value={"guidance_change": "none", "management_tone": "neutral"},
            ),
            patch("worker.tasks.sentiment.llm_extraction_task.settings", settings_ns),
            patch("worker.tasks.sentiment.llm_extraction_task.time.sleep"),
        ):
            result = asyncio.run(_run_extraction_async())

        assert LLM_MIN_QUALITY_SCORE == 0.60
        assert result["quality_skipped"] == 4
        select_sql = str(list_session.stmts[0].compile(compile_kwargs={"literal_binds": True})).lower()
        assert "quality_score" in select_sql
        assert "0.6" in select_sql
        count_sql = str(list_session.stmts[1].compile(compile_kwargs={"literal_binds": True})).lower()
        assert "quality_score" in count_sql
        assert "0.6" in count_sql


class TestUpdateEarningsGuidance:
    def test_null_published_at_returns_early(self):
        session = MagicMock()
        session.execute = AsyncMock()
        art = _article(published_at=None)
        asyncio.run(_update_earnings_guidance(session, art, "raised"))
        session.execute.assert_not_called()

    def test_within_window_updates(self):
        ee = SimpleNamespace(id=3, stock_id=7, earnings_date=date(2026, 9, 2), guidance_change=None)
        session = UpdateSession(_article(), stock_ids=[7], estimates=[ee])
        asyncio.run(_update_earnings_guidance(session, _article(), "lowered"))
        assert ee.guidance_change == "lowered"
        sql = str(session.stmts[-1].compile(compile_kwargs={"literal_binds": True}))
        window_start = NOW.date() - timedelta(days=EARNINGS_MATCH_DAYS)
        window_end = NOW.date() + timedelta(days=EARNINGS_MATCH_DAYS)
        assert str(window_start) in sql
        assert str(window_end) in sql

    def test_outside_window_no_match(self):
        session = UpdateSession(_article(), stock_ids=[7], estimates=[])
        asyncio.run(_update_earnings_guidance(session, _article(), "raised"))
        sql = str(session.stmts[-1].compile(compile_kwargs={"literal_binds": True}))
        assert str(NOW.date() - timedelta(days=8)) not in sql
        assert EARNINGS_MATCH_DAYS == 7

    def test_multi_stock_updates_both(self):
        ee1 = SimpleNamespace(id=1, stock_id=7, earnings_date=date(2026, 9, 1), guidance_change=None)
        ee2 = SimpleNamespace(id=2, stock_id=8, earnings_date=date(2026, 9, 1), guidance_change=None)
        session = UpdateSession(_article(), stock_ids=[7, 8], estimates=[ee1, ee2])
        asyncio.run(_update_earnings_guidance(session, _article(), "maintained"))
        assert ee1.guidance_change == "maintained"
        assert ee2.guidance_change == "maintained"


class TestBeatSchedule:
    def test_llm_extraction_at_minute_20(self):
        assert "run-llm-extraction" in beat_schedule
        entry = beat_schedule["run-llm-extraction"]
        assert entry["task"] == "worker.tasks.sentiment.llm_extraction_task.run_llm_extraction"
        assert entry["schedule"].minute == {20}
        assert entry["schedule"].hour == set(range(0, 24, 2))
