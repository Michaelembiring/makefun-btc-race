"""BTC race entry (v4). Long-biased cbBTC trend follower for make.fun's btc-race-24h-20261123-0511.

Speaks agent-fun/bars-replay/v1 via the vendored makefun_bars shim. A round trip
on these bars costs about 12 bps before impact (a 4 bps fee and 2 bps of slippage
each way), so the bot holds a trend and only lets go when the trend breaks:

- Entry, while flat: buy the cash on hand (capped by the max weight) once the
  close is above its EMA(64); before the EMA can be seeded, buy on the first
  batch the bot may trade on, so the scored window always trades.
- Exit, while held: sell the whole position on the first close at or below the
  best close since entry times 0.96 (the 4% hard stop) or at or below
  EMA(64) * 0.63 (the trail). Both are measured on closes and fill at the next
  open, so one spike through a level does not churn the book.
- Re-entry: after an exit, buy again once the close is back above its EMA.

No clock, no environment, no unseeded randomness: two runs over the same bars
produce byte-identical replies.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

closes = {}
best = {}


def ema64(series):
    """The EMA(64) of the whole series, seeded with the SMA of the first 64 closes; None before that."""
    if len(series) < 64:
        return None
    seed = sum(series[:64]) / 64
    for v in series[64:]:
        seed += (2 / 65) * (v - seed)
    return seed


def on_hello(state):
    closes.clear()
    best.clear()


def on_batch(state, batch):
    for bar in batch["bars"]:
        closes.setdefault(bar["symbol"], []).append(int(bar["c"]))
    if state.warming_up:
        return []

    series = closes["CBBTC"]
    close = state.close("CBBTC")
    held = state.positions.get("CBBTC")

    if held:
        best["CBBTC"] = max(best.get("CBBTC") or close, close)
        e = ema64(series)
        if close * 100 <= best["CBBTC"] * 96 or (e is not None and close * 100 <= e * 63):
            best["CBBTC"] = None
            return [dict(side="sell", symbol="CBBTC", qty=str(held.qty), max_slippage_bps=10000)]
        return []

    e = ema64(series)
    if e is not None and close <= e:
        return []
    room = state.weight_room("CBBTC")
    slc = min(state.cash, room)
    if slc < int(state.hello["fees"]["min_notional_quote_units"]):
        return []
    best["CBBTC"] = close
    return [dict(side="buy", symbol="CBBTC", notional_quote_units=str(slc), max_slippage_bps=10000)]


def on_done(state, done):
    pass


if __name__ == "__main__":
    makefun_bars.run(on_batch, on_hello=on_hello, on_done=on_done)

# end of bot
