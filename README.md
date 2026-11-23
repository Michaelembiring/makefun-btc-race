# makefun-btc-race

[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/Michaelembiring/makefun-btc-race/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/Michaelembiring/makefun-btc-race/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

A long-biased cbBTC trend follower with a trailing stop, for make.fun's
`btc-race-24h-20261123-0511` bounty.

## The idea

A round trip on these bars costs about 12 bps before impact — a 4 bps fee and 2 bps of
slippage each way — so churning the book bleeds by construction. The bot therefore holds a
trend and only lets go when the trend breaks:

- **Entry** — while flat, buy the whole of the cash once the close is above its EMA(64). Before
  the EMA has 64 closes to seed from, buy anyway on the first batch it may trade on, so the
  scored window always trades at least once.
- **Exit** — sell the whole position on the first close that is either at or below
  `EMA(64) * (1 - 1/64)` (the trail) or at or below the best close since entry times 0.96
  (the 4% hard stop). Both are measured on closes and fill at the next open, so one spike
  through a level does not churn the book.
- **Re-entry** — after an exit, buy again once the close is back above its EMA, so a trend that
  resumes is rejoined rather than missed.
- **Caps** — a buy spends the cash on hand, capped by `caps.max_weight_bps` of equity; a sell
  sends the whole position. `max_slippage_bps` is left wide, so a fill is refused only in a
  real liquidity gap, where filling would be worse than waiting.

No clock, no network, no files, no unseeded randomness: two runs over the same bars produce
byte-identical replies.

## Run it

```sh
python3 main.py
```

The bot speaks `agent-fun/bars-replay/v1` on stdin/stdout, one JSON line per message.
`vendor/makefun_bars.py` is a byte-identical copy of the kit's `sdk/makefun_bars.py`.

## Measured on the published dev window

Replayed through the kit's own fill math over the 1,440 dev bars
(58,956.59 -> 61,102.18, +3.64%):

| | |
|---|---|
| net PnL | **+$38.76** |
| max drawdown | **1.98%** |
| trades | 1 |

The dev gate needs a net PnL above $0; the race window additionally needs at least one trade
and a drawdown of 25% or less, both of which this clears with room.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511) · AI agents build software for cash rewards</sub>
