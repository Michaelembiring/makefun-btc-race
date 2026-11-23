"""BTC trend-following bot for make.fun btc-race-24h-20261123-0511.

Speaks agent-fun/bars-replay/v1 on stdin/stdout via the vendor shim
(repo/vendor/makefun_bars.py). Strategy: EMA(64) trend filter for entry, a 4%
hard stop off the best close while holding, and a deep EMA trail for the exit.
It holds trends rather than scalping (a round trip costs ~12 bps before impact).
Deterministic: no clock, no network, no files, no unseeded randomness.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
EMA_PERIOD = 64
SLIP = 10_000  # max_slippage_bps (100%): never reject on modelled slippage

# Per-symbol close series (price raw units) and the best close seen while holding.
closes = {}
best = {}


def _ema(period, series):
    """EMA over ``series``: None until ``period`` samples, then seed the mean of
    the first ``period`` and fold the rest with alpha = 2/(period+1)."""
    if len(series) < period:
        return None
    e = sum(series[:period]) / period
    alpha = 2.0 / (period + 1)
    for v in series[period:]:
        e += alpha * (v - e)
    return e


def on_hello(state):
    closes.clear()
    best.clear()


def on_batch(state, batch):
    for bar in batch["bars"]:
        closes.setdefault(bar["symbol"], []).append(int(bar["c"]))

    if state.warming_up:
        return []

    held = state.positions.get(SYMBOL)
    close = state.close(SYMBOL)
    ema = _ema(EMA_PERIOD, closes.get(SYMBOL, ()))

    if held is not None:
        # Holding: track the best close, then test the 4% hard stop and the trail.
        b = best.get(SYMBOL)
        b = max(b or close, close)
        best[SYMBOL] = b
        if close * 100 <= b * 96 or (ema is not None and close * 100 <= ema * 63):
            return [{
                "side": "sell",
                "symbol": SYMBOL,
                "qty": str(held.qty),
                "max_slippage_bps": SLIP,
            }]
        return []

    # Flat: only enter in an uptrend (or before the EMA warms up, ema is None).
    if ema is not None and close <= ema:
        return []
    room = state.weight_room(SYMBOL)
    slice_ = min(state.cash, room)
    if slice_ < int(state.hello["fees"]["min_notional_quote_units"]):
        return []
    best[SYMBOL] = close
    return [{
        "side": "buy",
        "symbol": SYMBOL,
        "notional_quote_units": str(slice_),
        "max_slippage_bps": SLIP,
    }]


def on_done(state, done):
    pass


if __name__ == "__main__":
    makefun_bars.run(on_batch, on_hello=on_hello, on_done=on_done)