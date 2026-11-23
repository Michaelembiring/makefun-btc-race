#!/usr/bin/env python3
"""BTC race entry: long-biased trend follower with a trailing stop.

The market this races in is one asset (cbBTC against USDC) on 1-minute bars, and a round trip
costs about 12 bps before impact: a 4 bps fee each way and 2 bps of slippage each way. Chasing
every wiggle therefore bleeds, so this bot holds a trend and only lets go when the trend breaks.

Rules, in order:

  - History. Every bar's close is appended to the symbol's own series; a gap in the bars adds
    nothing and no bar is invented. EMA(TREND_SPAN) is seeded with the mean of its first
    TREND_SPAN closes and then moves 2 / (span + 1) of the way to each new close, in float64 on
    + - * / alone, so the same bars give the same orders run after run.
  - Entry. While flat, buy the whole of the cash when the close is above its EMA and the bot is
    past the warm-up. Before the EMA has TREND_SPAN closes to seed from, buy anyway on the first
    batch it may trade on: the race window is scored on net PnL and needs at least one trade, and
    a bot that sat the whole window out would have neither.
  - Exit, the whole position, on the close that first shows any of:
      * the trail: the close at or below EMA * (100 - TRAIL_PCT) / 100,
      * the hard stop: the close at or below the highest close since entry times
        (100 - STOP_PCT) / 100.
    Both are measured on closes, and the order fills at the next open, so a single spike through
    the level does not churn the book.
  - Re-entry. After an exit the bot buys again once the close is back above its EMA, so a trend
    that resumes is rejoined rather than missed.
  - Sizing and caps. A buy spends the cash on hand, capped by caps.max_weight_bps of equity; a
    sell sends the whole position. max_slippage_bps is left wide (MAX_SLIPPAGE_BPS) so a fill is
    refused only in a real liquidity gap, where filling would be worse than waiting.
  - No clock, no network, no files, no unseeded randomness: two runs on the same bars produce
    byte-identical replies.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

#: EMA span of the trend, in bars.
TREND_SPAN = 64
#: How far under its EMA a close must be to give up the position, in percent.
TRAIL_PCT = 100.0 / 64.0
#: Hard stop from the best close since entry, in percent.
STOP_PCT = 4.0
#: Slippage cap on every order: wide, so only a real gap refuses a fill.
MAX_SLIPPAGE_BPS = 10_000

#: Each symbol's closes so far, in order.
closes = {}
#: The highest close since the position was opened, in raw price units (None while flat).
best = None


def ema(series, span):
    """EMA of `series` over `span`, or None while it has fewer than `span` values."""
    if len(series) < span:
        return None
    k = 2.0 / (span + 1)
    e = sum(series[:span]) / span
    for v in series[span:]:
        e += k * (v - e)
    return e


def on_hello(state):
    for s in state.hello["symbols"]:
        closes.setdefault(s["symbol"], [])


def on_batch(state, batch):
    global best

    # Fold this batch's bars into history first: the decision is made on their closes.
    for bar in batch["bars"]:
        closes.setdefault(bar["symbol"], []).append(int(bar["c"]))

    if state.warming_up:
        return []

    caps = state.hello["caps"]
    fees = state.hello["fees"]
    held = state.positions.get(SYMBOL)
    series = closes.get(SYMBOL) or []
    close = state.close(SYMBOL)

    if held is not None:
        # --- exit? ---
        reason = None
        if close is not None:
            if best is None or close > best:
                best = close
            trend = ema(series, TREND_SPAN)
            if best is not None and close * 100 <= best * (100 - STOP_PCT):
                reason = "stop"
            elif trend is not None and close * 100 <= trend * (100 - TRAIL_PCT):
                reason = "trail"
        if reason is not None:
            best = None
            return [
                {
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": str(held.qty),
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []

    # --- flat: entry? ---
    if close is None:
        return []

    trend = ema(series, TREND_SPAN)
    # Before the EMA is seeded, take the position anyway: the window must trade at least once.
    if trend is not None and close <= trend:
        return []

    room = state.weight_room(SYMBOL)
    slice_ = state.cash if state.cash < room else room
    if slice_ <= 0 or slice_ < int(fees["min_notional_quote_units"]):
        return []
    best = close
    return [
        {
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": str(slice_),
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }
    ]


def on_done(state, done):
    pass


if __name__ == "__main__":
    makefun_bars.run(on_batch, on_hello=on_hello, on_done=on_done)