"""Pure technical indicator calculations.

All functions take chronologically-ordered lists (oldest first) and return
lists of the same length, with None for entries with insufficient data.
"""

import math


def compute_sma(closes: list[float], period: int) -> list[float | None]:
    """Simple moving average."""
    result: list[float | None] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = sum(closes[i - period + 1 : i + 1]) / period
    return result


def compute_ema(closes: list[float], period: int) -> list[float | None]:
    """Exponential moving average. Uses SMA as seed for the first value."""
    result: list[float | None] = [None] * len(closes)
    if len(closes) < period:
        return result

    # Seed with SMA
    sma_seed = sum(closes[:period]) / period
    result[period - 1] = sma_seed

    multiplier = 2.0 / (period + 1)
    for i in range(period, len(closes)):
        prev = result[i - 1]
        if prev is not None:
            result[i] = (closes[i] - prev) * multiplier + prev

    return result


def compute_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Wilder's RSI using exponential moving average of gains/losses."""
    result: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    # Calculate price changes
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0.0) for c in changes]
    losses = [abs(min(c, 0.0)) for c in changes]

    # Initial average gain/loss (simple average of first `period` values)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # First RSI value
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    # Subsequent values using Wilder's smoothing
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return result


def compute_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> list[dict[str, float | None]]:
    """MACD: macd_line = EMA(fast) - EMA(slow), signal = EMA(signal) of macd_line."""
    result: list[dict[str, float | None]] = [
        {"macd_line": None, "signal_line": None, "histogram": None}
        for _ in closes
    ]

    if len(closes) < slow:
        return result

    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)

    # MACD line
    macd_values: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_values[i] = ema_fast[i] - ema_slow[i]

    # Signal line = EMA of MACD values
    # Find first non-None MACD index
    first_macd = next((i for i, v in enumerate(macd_values) if v is not None), None)
    if first_macd is None:
        return result

    macd_for_signal = [v for v in macd_values[first_macd:] if v is not None]
    if len(macd_for_signal) < signal:
        # Not enough MACD values for signal line, still output MACD line
        for i in range(len(closes)):
            if macd_values[i] is not None:
                result[i] = {"macd_line": macd_values[i], "signal_line": None, "histogram": None}
        return result

    signal_ema = compute_ema(macd_for_signal, signal)

    # Map signal EMA back to original indices
    macd_indices = [i for i, v in enumerate(macd_values) if v is not None]
    for j, idx in enumerate(macd_indices):
        ml = macd_values[idx]
        sl = signal_ema[j] if j < len(signal_ema) else None
        hist = (ml - sl) if ml is not None and sl is not None else None
        result[idx] = {"macd_line": ml, "signal_line": sl, "histogram": hist}

    return result


def compute_bollinger_bands(
    closes: list[float], period: int = 20, num_std: float = 2.0
) -> list[dict[str, float | None]]:
    """Bollinger Bands: SMA ± num_std * standard deviation."""
    result: list[dict[str, float | None]] = [
        {"upper": None, "middle": None, "lower": None} for _ in closes
    ]

    if len(closes) < period:
        return result

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = math.sqrt(variance)

        result[i] = {
            "upper": mean + num_std * std,
            "middle": mean,
            "lower": mean - num_std * std,
        }

    return result
