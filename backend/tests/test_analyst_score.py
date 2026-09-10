"""Tests for Phase 21g analyst_score gated component."""

import asyncio
import math
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from worker.tasks.signals.component_scores import calc_analyst_score

NOW = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)


def _analyst_session(metas, close=None):
    session = AsyncMock()
    articles_result = MagicMock()
    articles_result.scalars.return_value.all.return_value = metas
    close_result = MagicMock()
    close_result.scalar_one_or_none.return_value = close
    session.execute = AsyncMock(side_effect=[articles_result, close_result])
    return session


class TestCalcAnalystScore:
    def test_upgrade_with_target_above_close_is_positive(self):
        session = _analyst_session(
            [{"rating_change": "upgrade", "price_target": 120.0}],
            close=100.0,
        )
        score = asyncio.run(calc_analyst_score(session, 1, NOW))
        net = math.tanh(1.0 / 2.0)
        upside = math.tanh(0.20 * 5.0)
        expected = 0.6 * net + 0.4 * upside
        assert score is not None
        assert score > 0
        assert abs(score - expected) < 1e-9

    def test_downgrade_without_target_is_negative(self):
        session = _analyst_session([{"rating_change": "downgrade"}], close=100.0)
        score = asyncio.run(calc_analyst_score(session, 1, NOW))
        expected = math.tanh(-1.0 / 2.0)
        assert score is not None
        assert score < 0
        assert abs(score - expected) < 1e-9

    def test_mixed_ratings_follow_net_direction(self):
        session = _analyst_session(
            [
                {"rating_change": "upgrade"},
                {"rating_change": "upgrade"},
                {"rating_change": "downgrade"},
            ],
            close=100.0,
        )
        score = asyncio.run(calc_analyst_score(session, 1, NOW))
        # net = 1.0 + 1.0 - 1.0 = 1.0 → positive
        assert score is not None
        assert score > 0
        assert abs(score - math.tanh(1.0 / 2.0)) < 1e-9

    def test_no_articles_returns_none(self):
        session = _analyst_session([], close=100.0)
        score = asyncio.run(calc_analyst_score(session, 1, NOW))
        assert score is None
        assert session.execute.await_count == 1

    def test_only_none_rating_returns_none(self):
        session = _analyst_session(
            [{"rating_change": "none", "price_target": 150.0}],
            close=100.0,
        )
        score = asyncio.run(calc_analyst_score(session, 1, NOW))
        assert score is None
        assert session.execute.await_count == 1

    def test_many_upgrades_tanh_clamped_below_one(self):
        session = _analyst_session(
            [{"rating_change": "upgrade"}] * 20,
            close=100.0,
        )
        score = asyncio.run(calc_analyst_score(session, 1, NOW))
        assert score is not None
        assert score < 1.0
        assert abs(score - math.tanh(20.0 / 2.0)) < 1e-9
