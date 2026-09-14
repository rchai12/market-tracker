"""Pure component-score math shared by live scoring and backtests."""

import math
from datetime import date

from worker.utils.component_math import (
    SENTIMENT_HALF_LIFE_HOURS,
    SentimentPoint,
    exp_weighted_sentiment,
    price_momentum,
    rsi_score,
    signed_volume_ratio,
    trend_score,
    volume_anomaly,
)
from worker.utils.backtester.signals import (
    compute_price_momentum_from_closes,
    compute_rsi_score_from_closes,
    compute_sentiment_momentum_from_data,
    compute_sentiment_volume_from_data,
    compute_trend_score_from_closes,
    compute_volume_anomaly_from_data,
)
from worker.utils.backtester.models import SentimentRow


class TestPriceMomentum:
    def test_up_move_positive(self):
        assert price_momentum([100.0, 101.0, 102.0, 103.0, 104.0, 110.0]) > 0

    def test_down_move_negative(self):
        assert price_momentum([110.0, 108.0, 106.0, 104.0, 102.0, 90.0]) < 0

    def test_zero_oldest_none(self):
        assert price_momentum([0.0, 10.0]) is None

    def test_single_close_none(self):
        assert price_momentum([100.0]) is None

    def test_matches_backtester_wrapper(self):
        closes = [100.0, 101.0, 99.0, 102.0, 103.0, 108.0]
        assert price_momentum(closes) == compute_price_momentum_from_closes(closes)

    def test_newest_first_live_shape_agrees(self):
        oldest_first = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0]
        newest_first = list(reversed(oldest_first))
        live_style = math.tanh(((newest_first[0] - newest_first[-1]) / newest_first[-1]) * 5)
        assert abs(price_momentum(oldest_first) - live_style) < 1e-12


class TestVolumeAnomaly:
    def test_spike_up_day_positive(self):
        closes = [100.0] * 20 + [101.0]
        volumes = [1000] * 20 + [3000]
        assert volume_anomaly(closes, volumes) > 0

    def test_zero_latest_none(self):
        closes = [100.0, 101.0, 102.0]
        volumes = [1000, 1000, 0]
        assert volume_anomaly(closes, volumes) is None

    def test_matches_backtester_wrapper(self):
        closes = [100.0] * 10 + [99.0]
        volumes = [1000] * 10 + [2000]
        assert volume_anomaly(closes, volumes) == compute_volume_anomaly_from_data(closes, volumes)


class TestRsiAndTrend:
    def test_rsi_insufficient(self):
        assert rsi_score([100.0] * 10) is None

    def test_trend_insufficient(self):
        assert trend_score([100.0] * 40) is None

    def test_wrappers_delegate(self):
        closes = [100.0 + i * 0.5 for i in range(60)]
        assert rsi_score(closes) == compute_rsi_score_from_closes(closes)
        assert trend_score(closes) == compute_trend_score_from_closes(closes)


class TestSentimentKernel:
    def test_half_life_is_half(self):
        now = SentimentPoint(value=1.0, hours_ago=0.0, weight=1.0)
        aged = SentimentPoint(value=1.0, hours_ago=SENTIMENT_HALF_LIFE_HOURS, weight=1.0)
        mixed = exp_weighted_sentiment([now, aged])
        # Equal value, aged weight is half → still 1.0
        assert abs(mixed - 1.0) < 1e-12
        only_aged = exp_weighted_sentiment([aged])
        assert abs(only_aged - 1.0) < 1e-12

    def test_credibility_weight(self):
        low = SentimentPoint(value=1.0, hours_ago=0.0, weight=0.4)
        high = SentimentPoint(value=-1.0, hours_ago=0.0, weight=1.0)
        result = exp_weighted_sentiment([low, high])
        assert result < 0

    def test_empty_none(self):
        assert exp_weighted_sentiment([]) is None

    def test_daily_backtest_matches_hourly_kernel(self):
        today = date(2024, 6, 15)
        rows = [
            SentimentRow(date=today, avg_positive=0.8, avg_negative=0.1, article_count=4),
            SentimentRow(
                date=date(2024, 6, 14), avg_positive=0.6, avg_negative=0.2, article_count=2
            ),
        ]
        wrapped = compute_sentiment_momentum_from_data(rows, today)
        points = [
            SentimentPoint(value=0.7, hours_ago=0.0, weight=4.0),
            SentimentPoint(value=0.4, hours_ago=24.0, weight=2.0),
        ]
        assert abs(wrapped - exp_weighted_sentiment(points)) < 1e-12


class TestSignedVolumeRatio:
    def test_above_baseline_positive(self):
        assert signed_volume_ratio(10, 5, 0.2) > 0

    def test_signed_by_sentiment(self):
        assert signed_volume_ratio(10, 5, -0.2) < 0

    def test_zero_count_none(self):
        assert signed_volume_ratio(0, 5, 0.1) is None

    def test_zero_baseline_caps(self):
        capped = signed_volume_ratio(100, 0, 1.0)
        expected = math.tanh(5.0 - 1.0)
        assert abs(capped - expected) < 1e-12

    def test_backtester_volume_uses_kernel(self):
        today = date(2024, 6, 15)
        rows = [
            SentimentRow(date=today, avg_positive=0.8, avg_negative=0.1, article_count=10),
        ]
        assert compute_sentiment_volume_from_data(rows, today) == signed_volume_ratio(10, 0.0, 0.7)
