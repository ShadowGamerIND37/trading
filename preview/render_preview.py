"""
Renders an illustrative preview of indicators/SmartStructurePro.pine.

It re-implements the indicator's logic (pivots -> BOS/CHoCH -> order blocks ->
fair value gaps -> signals -> ATR stop/target) on a synthetic OHLC series so you
can see the layout without opening TradingView.

    python3 preview/render_preview.py
    -> preview/SmartStructurePro-preview.png
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import LineCollection

# ───────────────────────────── synthetic OHLC ──────────────────────────────
rng = np.random.default_rng(11)
N = 260
drift = np.concatenate([
    np.full(35, 0.0009), np.full(30, -0.0013), np.full(55, 0.0012),
    np.full(28, -0.0016), np.full(70, 0.0011), np.full(42, -0.0009),
])
drift = np.resize(drift, N)
ret = drift + rng.normal(0, 0.0042, N)
close = 100 * np.exp(np.cumsum(ret))
open_ = np.empty(N)
open_[0] = close[0] * 0.999
open_[1:] = close[:-1] * (1 + rng.normal(0, 0.0008, N - 1))
body_hi = np.maximum(open_, close)
body_lo = np.minimum(open_, close)
high = body_hi * (1 + np.abs(rng.normal(0, 0.0022, N)))
low = body_lo * (1 - np.abs(rng.normal(0, 0.0022, N)))

# ───────────────────────────── indicator logic ─────────────────────────────
SWING, OB_LOOK, OB_EXT, MAX_OB = 4, 12, 34, 6
FVG_EXT, MAX_FVG, FVG_MIN_ATR = 34, 6, 0.15
EMA_LEN, ATR_LEN, SL_MULT, RR = 50, 14, 1.5, 2.0

tr = np.empty(N)
tr[0] = high[0] - low[0]
for i in range(1, N):
    tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
atr = np.full(N, np.nan)
for i in range(ATR_LEN, N):
    atr[i] = tr[i - ATR_LEN:i].mean()

ema = np.empty(N)
ema[0] = close[0]
k = 2 / (EMA_LEN + 1)
for i in range(1, N):
    ema[i] = close[i] * k + ema[i - 1] * (1 - k)

def pivot_high(i, left=SWING, right=SWING):
    if i - left < 0 or i + right >= N:
        return False
    return high[i] > max(high[i - left:i]) and high[i] > max(high[i + 1:i + right + 1])

def pivot_low(i, left=SWING, right=SWING):
    if i - left < 0 or i + right >= N:
        return False
    return low[i] < min(low[i - left:i]) and low[i] < min(low[i + 1:i + right + 1])

lastPH = lastPHb = None
lastPL = lastPLb = None
phBroken = plBroken = True
trend = 0
breaks, obs, fvgs, signals = [], [], [], []

for b in range(N):
    # pivots confirmed SWING bars after they formed
    p = b - SWING
    if p >= 0 and pivot_high(p):
        lastPH, lastPHb, phBroken = high[p], p, False
    if p >= 0 and pivot_low(p):
        lastPL, lastPLb, plBroken = low[p], p, False

    bull = lastPH is not None and not phBroken and close[b] > lastPH
    bear = lastPL is not None and not plBroken and close[b] < lastPL

    if bull:
        ev = "CHoCH" if trend == -1 else "BOS"
        breaks.append((lastPHb, lastPH, b, ev, 1))
        phBroken, trend = True, 1
        found = None
        for i in range(1, OB_LOOK + 1):
            if b - i >= 0 and close[b - i] < open_[b - i]:
                found = b - i
                break
        if found is not None:
            obs.append(dict(bot=low[found], top=high[found], left=found, right=b + OB_EXT, side=1))
        if not np.isnan(atr[b]):
            sl = min(low[b], low[b - 1]) - atr[b] * SL_MULT
            signals.append(dict(dir=1, bar=b, price=close[b], sl=sl, tp=close[b] + (close[b] - sl) * RR))
            trend_at = 1

    if bear:
        ev = "CHoCH" if trend == 1 else "BOS"
        breaks.append((lastPLb, lastPL, b, ev, -1))
        plBroken, trend = True, -1
        found = None
        for i in range(1, OB_LOOK + 1):
            if b - i >= 0 and close[b - i] > open_[b - i]:
                found = b - i
                break
        if found is not None:
            obs.append(dict(bot=low[found], top=high[found], left=found, right=b + OB_EXT, side=-1))
        if not np.isnan(atr[b]):
            sl = max(high[b], high[b - 1]) + atr[b] * SL_MULT
            signals.append(dict(dir=-1, bar=b, price=close[b], sl=sl, tp=close[b] - (sl - close[b]) * RR))

    # fair value gaps
    if b >= 2 and not np.isnan(atr[b]):
        gb = low[b] - high[b - 2]
        gr = low[b - 2] - high[b]
        if gb > 0 and gb >= atr[b] * FVG_MIN_ATR:
            fvgs.append(dict(bot=high[b - 2], top=low[b], left=b - 2, right=b + FVG_EXT, side=1, dead=None))
        if gr > 0 and gr >= atr[b] * FVG_MIN_ATR:
            fvgs.append(dict(bot=high[b], top=low[b - 2], left=b - 2, right=b + FVG_EXT, side=-1, dead=None))

    # mitigation / right-edge extension
    for z in obs:
        if z["right"] is None:
            continue
        if (z["side"] == 1 and close[b] < z["bot"]) or (z["side"] == -1 and close[b] > z["top"]):
            z["dead"] = b
            z["right"] = b
        elif z.get("dead") is None:
            z["right"] = b + OB_EXT
    for z in fvgs:
        if (z["side"] == 1 and close[b] < z["bot"]) or (z["side"] == -1 and close[b] > z["top"]):
            z["dead"] = b
            z["right"] = b
        elif z.get("dead") is None:
            z["right"] = b + FVG_EXT

obs = [z for z in obs if z.get("dead") is None][-MAX_OB:]
fvgs = [z for z in fvgs if z.get("dead") is None][-MAX_FVG:]

# keep only signals that agree with the EMA filter
signals = [s for s in signals if (s["dir"] == 1 and s["price"] > ema[s["bar"]])
           or (s["dir"] == -1 and s["price"] < ema[s["bar"]])]

# ───────────────────────────────── plot ────────────────────────────────────
BG, GRID, TXT = "#131722", "#1e222d", "#b2b5be"
UP, DN, MIT = "#26a69a", "#ef5350", "#787b86"
VIS = 150          # bars shown in the window
x0 = N - VIS

fig, ax = plt.subplots(figsize=(16, 8.6), dpi=110)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(x0 - 2, N + 20)
pad = (max(high[x0:]) - min(low[x0:])) * 0.06
ax.set_ylim(min(low[x0:]) - pad, max(high[x0:]) + pad * 1.5)

ax.grid(True, color=GRID, linewidth=0.7)
ax.set_axisbelow(True)
for sp in ax.spines.values():
    sp.set_color(GRID)
ax.tick_params(colors=TXT, labelsize=9)

# candles
w = 0.62
for i in range(x0, N):
    c = UP if close[i] >= open_[i] else DN
    ax.plot([i, i], [low[i], high[i]], color=c, linewidth=1.0, zorder=3)
    lo, hi = min(open_[i], close[i]), max(open_[i], close[i])
    ax.add_patch(Rectangle((i - w / 2, lo), w, max(hi - lo, 1e-6),
                           facecolor=c, edgecolor=c, linewidth=0.6, zorder=4))

# EMA
ax.plot(range(x0, N), ema[x0:], color="#ffb74d", linewidth=1.4, zorder=2, label=f"EMA {EMA_LEN}")

# fair value gaps
for z in fvgs:
    col = UP if z["side"] == 1 else DN
    ax.add_patch(Rectangle((z["left"], z["bot"]), z["right"] - z["left"], z["top"] - z["bot"],
                           facecolor=col, alpha=0.12, edgecolor=col, linewidth=0.8, zorder=1))

# order blocks
for z in obs:
    col = UP if z["side"] == 1 else DN
    ax.add_patch(Rectangle((z["left"], z["bot"]), z["right"] - z["left"], z["top"] - z["bot"],
                           facecolor=col, alpha=0.24, edgecolor=col, linewidth=1.0, zorder=1))

# structure lines + labels
for (pb, pv, bb, ev, side) in breaks:
    if pb < x0 - 10:
        continue
    col = UP if side == 1 else DN
    ax.plot([pb, bb + 16], [pv, pv], color=col, linewidth=1.6, zorder=2)
    ax.annotate(ev, xy=(bb, pv), xytext=(0, 14 if side == 1 else -18), textcoords="offset points",
                ha="center", fontsize=7.5, color=col, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.22", fc=BG, ec=col, lw=0.8, alpha=0.9), zorder=6)

# signals
for s in signals:
    if s["bar"] < x0:
        continue
    col = UP if s["dir"] == 1 else DN
    y = low[s["bar"]] - pad * 0.35 if s["dir"] == 1 else high[s["bar"]] + pad * 0.35
    mark = "^" if s["dir"] == 1 else "v"
    ax.plot(s["bar"], y, marker=mark, color=col, markersize=11, zorder=6)
    ax.annotate("BUY" if s["dir"] == 1 else "SELL", xy=(s["bar"], y),
                xytext=(0, -13 if s["dir"] == 1 else 13), textcoords="offset points",
                ha="center", fontsize=7.5, color=col, fontweight="bold", zorder=6)

# last signal risk levels
if signals:
    s = signals[-1]
    ax.plot([s["bar"], N + 6], [s["sl"]] * 2, color=DN, linestyle="--", linewidth=1.1, zorder=2)
    ax.plot([s["bar"], N + 6], [s["tp"]] * 2, color=UP, linestyle="--", linewidth=1.1, zorder=2)
    ax.text(N + 7, s["sl"], " SL", color=DN, fontsize=8, va="center", ha="left")
    ax.text(N + 7, s["tp"], " TP", color=UP, fontsize=8, va="center", ha="left")

# dashboard
trend_txt = "BULLISH" if trend == 1 else "BEARISH" if trend == -1 else "NEUTRAL"
last_ev = f"{breaks[-1][3]} {'▲' if breaks[-1][4] == 1 else '▼'}" if breaks else "—"
last_sig = ("BUY" if signals[-1]["dir"] == 1 else "SELL") if signals else "None"
rows = [("Trend", trend_txt, UP if trend == 1 else DN),
        ("Last event", last_ev, UP if trend == 1 else DN),
        ("Close vs EMA", "Above" if close[-1] > ema[-1] else "Below", TXT),
        ("Last signal", last_sig, UP if last_sig == "BUY" else DN if last_sig == "SELL" else TXT)]

ax.text(0.012, 0.975, "SMART STRUCTURE PRO", transform=ax.transAxes, color="white",
        fontsize=10.5, fontweight="bold", va="top")
ax.text(0.012, 0.938, "BOS · CHoCH · order blocks · FVG · ATR stops   |   demo chart, synthetic data",
        transform=ax.transAxes, color=TXT, fontsize=8.2, va="top")
for j, (k_, v_, c_) in enumerate(rows):
    yy = 0.885 - j * 0.038
    ax.text(0.012, yy, k_, transform=ax.transAxes, color=TXT, fontsize=8.2, va="top")
    ax.text(0.088, yy, v_, transform=ax.transAxes, color=c_, fontsize=8.2, va="top", fontweight="bold")

# legend
handles = [
    plt.Line2D([], [], color=UP, alpha=0.5, linewidth=7, label="bullish block / FVG"),
    plt.Line2D([], [], color=DN, alpha=0.5, linewidth=7, label="bearish block / FVG"),
    plt.Line2D([], [], color="#ffb74d", linewidth=1.5, label=f"EMA {EMA_LEN} (trend filter)"),
]
leg = ax.legend(handles=handles, loc="upper right", facecolor=BG, edgecolor=GRID, fontsize=8.5,
                labelcolor=TXT, framealpha=0.95)
leg.get_frame().set_linewidth(0.8)

ax.set_title("", pad=0)
plt.tight_layout()
fig.savefig("preview/SmartStructurePro-preview.png", facecolor=BG, bbox_inches="tight")
print("saved preview/SmartStructurePro-preview.png", len(obs), "OBs", len(fvgs), "FVGs", len(signals), "signals")
