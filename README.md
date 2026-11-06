# Smart Structure Pro — TradingView indicator

A single-file Pine Script indicator that draws the classic "smart money" toolkit
that most trading reels demo, and gives you clean entry/exit levels:

| Feature | What it does |
|---|---|
| **BOS / CHoCH** | Marks market-structure breaks. `BOS` = continuation, `CHoCH` = change of character (possible reversal). |
| **Order blocks** | On every structure break it highlights the last opposite-colour candle before the move — the classic supply/demand zone. Auto-deleted when price closes through them. |
| **Fair value gaps (FVG)** | 3-candle imbalance, drawn as a box and auto-removed once filled. Has a minimum-size filter in ATR units so you don't get noise. |
| **BUY / SELL arrows** | Fires when a structure break, an EMA trend filter and (optionally) a fresh FVG agree. |
| **ATR stop / target** | Dashed stop-loss and take-profit lines from the last signal (stop = ATR × 1.5, target = risk × 2 by default). |
| **Dashboard** | Small table showing trend, last event, price vs EMA and the last signal. |
| **Alerts** | 4 ready-made alerts: BUY, SELL, bullish break, bearish break. |

![Smart Structure Pro preview](preview/SmartStructurePro-preview.png)

*Preview rendered from the indicator's own logic on synthetic data
(`preview/render_preview.py`) — your live chart will look the same, just with real prices.*

File: [`indicators/SmartStructurePro.pine`](indicators/SmartStructurePro.pine)

---

## Install (2 minutes)

1. Open TradingView → **Pine Editor** (bottom panel).
2. Click **Open → New blank indicator**.
3. Delete everything, then paste the whole contents of `indicators/SmartStructurePro.pine`.
4. Click **Save**, give it a name, then **Add to chart**.
5. Open the indicator's **Settings** gear to tune it (6 sections, all documented with tooltips).

## Recommended starting settings

| Timeframe | Swing length | Notes |
|---|---|---|
| 1m – 5m (scalping) | 3 – 4 | Faster signals, more noise. Keep EMA filter ON. |
| 15m – 1h (intraday) | 5 (default) | Balanced. |
| 4h – 1D (swing) | 8 – 12 | Fewer, stronger zones. |

- **Signal on** — `All breaks` gives more trades; `CHoCH only` only takes reversals.
- **EMA trend filter** — leave ON for trending markets, turn OFF in tight ranges.
- **Only signal at a fresh FVG** — the strictest, highest-quality mode.

## Alerts

Right-click the chart → **Add alert** → *Condition* = **Smart Structure Pro** →
pick `SSP · BUY` / `SSP · SELL` / `SSP · Bullish BOS/CHoCH` / `SSP · Bearish BOS/CHoCH`.
Set the trigger to **Once per bar close** so a signal can't flip after the candle closes.

## How it works (short version)

1. A **pivot high/low** is confirmed after `swing length` bars on each side.
2. A close above the last pivot high (below the last pivot low) is a **structure break**.
   If the previous trend was the opposite direction it's labelled **CHoCH**, otherwise **BOS**.
3. On a break the script looks back up to `search depth` bars for the last opposite-colour
   candle and stores it as an **order block**.
4. Separately, any candle whose low is above the high of two bars ago (or the mirror
   for bearish) is a **fair value gap**, provided the gap is at least `min gap × ATR`.
5. A **signal** = structure break **+** trend filter **+** optional fresh FVG.
   From there the ATR stop/target are projected.

### About repainting

Structure breaks are evaluated on **bar close**, and pivots are only confirmed after
`swing length` bars — so the arrows do **not** repaint, but they do arrive
`swing length` bars after the actual swing point. That lag is the price of a
non-repainting pivot. Lower the swing length if you want faster arrows.

## Disclaimers

This is an educational tool, not financial advice or a guarantee of profit. Past
patterns do not repeat reliably. Test on a demo account first, and always size
positions from your own risk rules (the ATR stop is a starting point, not a promise).

---

### Was your reel something else?

The Instagram link (`instagram.com/reel/DfUi0luT9Qz`) cannot be opened from this
environment — Instagram returns HTTP 403 to anything that isn't a logged-in browser,
so the exact indicator in the video couldn't be viewed. This build covers the most
common "reel indicator" stack (BOS/CHoCH + order blocks + FVG + buy/sell arrows).
If the reel showed something different — e.g. **Supertrend/UT Bot**, **VWAP bands +
volume**, **RSI divergence**, **liquidity sweeps / equal highs–lows**, **a scalping
EMA-ribbon system** or **options-style CE/PE signals** — say which one (or drop a
screenshot of the chart) and this file will be reworked to match it.
