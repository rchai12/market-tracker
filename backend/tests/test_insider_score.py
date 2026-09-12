"""Phase 23b: insider Form 4 scoring."""

import asyncio
import math
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from worker.tasks.signals.component_scores import (
    INSIDER_NORMALIZATION,
    INSIDER_SELL_DISCOUNT,
    _insider_role_weight,
    calc_insider_score,
    score_insider_rows,
)

NOW = datetime(2026, 9, 11, 18, 0, tzinfo=UTC)


def _tx(**overrides):
    base = dict(insider_title="CEO", transaction_type="P", transaction_value=500_000)
    base.update(overrides)
    return SimpleNamespace(**base)


class TestInsiderRoleWeight:
    def test_ceo_is_1_5(self):
        assert _insider_role_weight("Chief Executive Officer") == 1.5
        assert _insider_role_weight("CEO") == 1.5

    def test_vp_does_not_match_evp_first(self):
        assert _insider_role_weight("EVP") == 1.2
        assert _insider_role_weight("SVP, Finance") == 1.1
        assert _insider_role_weight("VP") == 1.0

    def test_vice_president_is_not_president(self):
        assert _insider_role_weight("Vice President") == 1.0
        assert _insider_role_weight("President") == 1.5

    def test_ten_percent_owner(self):
        assert _insider_role_weight("10% Owner") == 1.5
        assert _insider_role_weight("10 percent owner") == 1.5

    def test_unknown_defaults(self):
        assert _insider_role_weight("") == 0.8
        assert _insider_role_weight("Engineer") == 0.8


class TestScoreInsiderRows:
    def test_buy_is_positive(self):
        score = score_insider_rows([_tx()])
        assert score is not None
        assert abs(score - math.tanh(500_000 * 1.5 / INSIDER_NORMALIZATION)) < 1e-9

    def test_sells_are_discounted(self):
        score = score_insider_rows([_tx(transaction_type="S")])
        expected = math.tanh(-500_000 * 1.5 * INSIDER_SELL_DISCOUNT / INSIDER_NORMALIZATION)
        assert score is not None
        assert abs(score - expected) < 1e-9

    def test_awards_not_in_rows_do_not_score(self):
        assert score_insider_rows([]) is None

    def test_none_when_no_transactions(self):
        assert score_insider_rows([]) is None

    def test_tanh_clamps_large_cluster(self):
        rows = [_tx(transaction_value=5_000_000) for _ in range(5)]
        score = score_insider_rows(rows)
        assert score is not None
        assert score > 0.99
        assert score <= 1.0

    def test_director_weighs_less_than_ceo(self):
        ceo = score_insider_rows([_tx(insider_title="CEO")])
        director = score_insider_rows([_tx(insider_title="Director")])
        assert ceo is not None and director is not None
        assert ceo > director


class TestCalcInsiderScore:
    def test_disabled_returns_none(self):
        session = AsyncMock()
        with patch("worker.tasks.signals.component_scores.settings") as settings:
            settings.insider_flow_enabled = False
            score = asyncio.run(calc_insider_score(session, 1, NOW))
        assert score is None
        session.execute.assert_not_called()

    def test_empty_window_returns_none(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)
        with patch("worker.tasks.signals.component_scores.settings") as settings:
            settings.insider_flow_enabled = True
            score = asyncio.run(calc_insider_score(session, 1, NOW))
        assert score is None
