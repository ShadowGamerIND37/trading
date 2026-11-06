"""
Renders an illustrative preview of indicators/TrendPilotPro.pine.

Re-implements the indicator's logic (Supertrend engine -> EMA filter -> trigger
-> entry, ATR stop, 1R/2R/3R targets) on a synthetic OHLC series.

    python3 preview/render_trend_preview.py
    -> preview/TrendPilotPro-preview.png
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

# ───────────────────────────── synthetic OHLC ──────────────────────────────
rng = np.random.default_rng(23)
N = 240
drift = np.resize(np.concatenate([
    np.full(45, 0.0011), np.full(30, -0.0009), np.full(60, 0.0016),
    np.full(25, -0.0019), np.full(80, -0.0011),
]), N)
ret = drift + rng.normal(0, 0.0040, N)
close = 100 * np.exp(np.cumsum(ret))
open_ = np.empty(N)
open_[0] = close[0] * 0.999
open_[1:] = close[:-1] * (1 + rng.normal(0, 0.0008, N - 1))
high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.0020, N)))
low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.0020, N)))

# ───────────────────────────── indicator logic ─────────────────────────────
ST_ATR, ST_FACTOR = 10, 2.5
EMA_FILT, EMA_LEN = 50, 50
SL_ATR, TARGETS, COOLDOWN = 1.5, (1.0, 2.0, 3.0), 3

tr = np.empty(N)
tr[0] = high[0] - low[0]
for i in range(1, N):
    tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
atr = np.full(N, np.nan)
atr[ST_ATR] = tr[1:ST_ATR + 1].mean()
for i in range(ST_ATR + 1, N):
    atr[i] = (atr[i - 1] * (ST_ATR - 1) + tr[i]) / ST_ATR

ema = np.empty(N)
ema[0] = close[0]
k = 2 / (EMA_FILT + 1)
for i in range(1, N):
    ema[i] = close[i] * k + ema[i - 1] * (1 - k)

hl2 = (high + low) / 2
up = np.full(N, np.nan)
dn = np.full(N, np.nan)
trend = np.ones(N, dtype=int)
for i in range(1, N):
    if np.isnan(atr[i]):
        continue
    up_raw = hl2[i] - ST_FACTOR * atr[i]
    dn_raw = hl2[i] + ST_FACTOR * atr[i]
    up_prev = up[i - 1] if not np.isnan(up[i - 1]) else up_raw
    dn_prev = dn[i - 1] if not np.isnan(dn[i - 1]) else dn_raw
    up[i] = max(up_raw, up_prev) if close[i - 1] > up_prev else up_raw
    dn[i] = min(dn_raw, dn_prev) if close[i - 1] < dn_prev else dn_raw
    t = trend[i - 1]
    if t == -1 and close[i] < up_prev:
        t = 1
    elif t == 1 and close[i] > dn_prev:
        t = -1
    trend[i] = t

# ── signals + trade management (mirrors the Pine script) ──
trades, open_trade, last_sig = [], None, -99

for i in range(1, N):
    if open_trade:
        t = open_trade
        if t["dir"] == 1:
            for j in range(3):
                if not t["hits"][j] and high[i] >= t["tp"][j]:
                    t["hits"][j] = True
            if low[i] <= t["sl"]:
                t["end"] = i
                open_trade = None
        else:
            for j in range(3):
                if not t["hits"][j] and low[i] <= t["tp"][j]:
                    t["hits"][j] = True
            if high[i] >= t["sl"]:
                t["end"] = i
                open_trade = None
        if open_trade:
            open_trade["end"] = i

    if np.isnan(atr[i]) or i - last_sig < COOLDOWN:
        continue

    state_l, state_s = trend[i] == -1, trend[i] == 1
    prev_l, prev_s = trend[i - 1] == -1, trend[i - 1] == 1
    filt_l, filt_s = close[i] > ema[i], close[i] < ema[i]
    pfilt_l, pfilt_s = close[i - 1] > ema[i - 1], close[i - 1] < ema[i - 1]
    trig_l = state_l and filt_l and not (prev_l and pfilt_l)
    trig_s = state_s and filt_s and not (prev_s and pfilt_s)

    if trig_l and (open_trade is None or open_trade["dir"] != 1):
        sl = min(low[i], low[i - 1]) - atr[i] * SL_ATR
        risk = close[i] - sl
        t = dict(dir=1, bar=i, entry=close[i], sl=sl,
                 tp=[close[i] + risk * r for r in TARGETS], hits=[False] * 3, end=i, closed=False)
        trades.append(t)
        open_trade, last_sig = t, i
    elif trig_s and (open_trade is None or open_trade["dir"] != -1):
        sl = max(high[i], high[i - 1]) + atr[i] * SL_ATR
        risk = sl - close[i]
        t = dict(dir=-1, bar=i, entry=close[i], sl=sl,
                 tp=[close[i] - risk * r for r in TARGETS], hits=[False] * 3, end=i, closed=False)
        trades.append(t)
        open_trade, last_sig = t, i

# ───────────────────────────────── plot ────────────────────────────────────
BG, GRID, TXT = "#131722", "#1e222d", "#b2b5be"
UP, DN, ENT, DONE, EMA_C = "#26a69a", "#ef5350", "#2962ff", "#787b86", "#ffb74d"
VIS = 165
x0 = N - VIS

fig, ax = plt.subplots(figsize=(16, 8.6), dpi=110)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(x0 - 2, N + 30)
pad = (max(high[x0:]) - min(low[x0:])) * 0.07
ax.set_ylim(min(low[x0:]) - pad * 1.2, max(high[x0:]) + pad * 1.4)
ax.grid(True, color=GRID, linewidth=0.7)
ax.set_axisbelow(True)
for sp in ax.spines.values():
    sp.set_color(GRID)
ax.tick_params(colors=TXT, labelsize=9)

w = 0.62
for i in range(x0, N):
    c = UP if close[i] >= open_[i] else DN
    ax.plot([i, i], [low[i], high[i]], color=c, linewidth=1.0, zorder=3)
    lo, hi = min(open_[i], close[i]), max(open_[i], close[i])
    ax.add_patch(Rectangle((i - w / 2, lo), w, max(hi - lo, 1e-6),
                           facecolor=c, edgecolor=c, linewidth=0.6, zorder=4))

# supertrend line
for i in range(x0 + 1, N):
    if np.isnan(up[i]):
        continue
    y0 = up[i - 1] if trend[i - 1] == -1 else dn[i - 1]
    y1 = up[i] if trend[i] == -1 else dn[i]
    ax.plot([i - 1, i], [y0, y1], color=UP if trend[i] == -1 else DN, linewidth=2.0, zorder=3)

ax.plot(range(x0, N), ema[x0:], color=EMA_C, linewidth=1.3, zorder=2, alpha=0.9)

# trades: entry / stop / targets  (the Pine script keeps only the current trade)
for t in trades[-1:]:
    if t["bar"] < x0 - 25:
        continue
    right = (t["end"] + 12) if t["closed"] else (N + 24)
    right = min(right, N + 26)
    ax.plot([t["bar"], right], [t["entry"]] * 2, color=ENT, linewidth=2.0, zorder=2)
    ax.plot([t["bar"], right], [t["sl"]] * 2, color=DN, linestyle="--", linewidth=1.1, zorder=2)
    for j, ls in enumerate(["--", ":", ":"]):
        ax.plot([t["bar"], right], [t["tp"][j]] * 2, color=UP, linestyle=ls, linewidth=1.0, zorder=2)

    def tag(y, text, fc):
        ax.text(right + 0.5, y, text, color="white", fontsize=7.0, va="center", ha="left",
                family="monospace", zorder=8,
                bbox=dict(boxstyle="round,pad=0.28", fc=fc, ec=fc, lw=0.6))

    tag(t["entry"], f"ENTRY {t['entry']:.2f}", ENT)
    tag(t["sl"], f"SL {t['sl']:.2f}", DN if not t["closed"] else DONE)
    for j in range(3):
        tag(t["tp"][j], f"TP{j + 1} {t['tp'][j]:.2f}" + (" ✓" if t["hits"][j] else ""),
            UP if t["hits"][j] else "#2f7d74")

    below = t["dir"] == 1
    y = low[t["bar"]] - pad * 0.5 if below else high[t["bar"]] + pad * 0.5
    ax.plot(t["bar"], y, marker="^" if below else "v", color=UP if below else DN,
            markersize=13, markeredgecolor="white", markeredgewidth=0.6, zorder=7)
    ax.annotate("BUY" if below else "SELL", xy=(t["bar"], y),
                xytext=(0, -15 if below else 15), textcoords="offset points",
                ha="center", va="center", color="white", fontsize=6.8, fontweight="bold", zorder=8,
                bbox=dict(boxstyle="round,pad=0.22", fc=UP if below else DN, ec="none"))

# arrows for every signal visible in the window
for t in trades:
    if t["bar"] < x0:
        continue
    below = t["dir"] == 1
    y = low[t["bar"]] - pad * 0.5 if below else high[t["bar"]] + pad * 0.5
    ax.plot(t["bar"], y, marker="^" if below else "v", color=UP if below else DN,
            markersize=13, markeredgecolor="white", markeredgewidth=0.6, zorder=7)
    ax.annotate("BUY" if below else "SELL", xy=(t["bar"], y),
                xytext=(0, -15 if below else 15), textcoords="offset points",
                ha="center", va="center", color="white", fontsize=6.8, fontweight="bold", zorder=8,
                bbox=dict(boxstyle="round,pad=0.22", fc=UP if below else DN, ec="none"))

# ── dashboard panel ──
last = trades[-1] if trades else None
if last:
    panel = FancyBboxPatch((0.006, 0.60), 0.265, 0.385, transform=ax.transAxes,
                           boxstyle="round,pad=0.008", fc=BG, ec="#434651", lw=0.9, alpha=0.92, zorder=9)
    ax.add_patch(panel)
    ax.text(0.014, 0.965, "TREND PILOT PRO", transform=ax.transAxes, color="white",
            fontsize=10.2, fontweight="bold", va="top", zorder=10)
    ax.text(0.014, 0.928, "Supertrend · EMA filter · entry / SL / TP1-TP3", transform=ax.transAxes,
            color=TXT, fontsize=7.6, va="top", zorder=10)
    pos = "LONG" if last["dir"] == 1 and not last["closed"] else "SHORT" if last["dir"] == -1 and not last["closed"] else "Flat / closed"
    status = f"TP{sum(last['hits'])} hit" if all(last["hits"]) else f"TP{sum(last['hits'])} of 3 hit" if any(last["hits"]) else "open"
    rows = [("Engine", "Supertrend", TXT),
            ("Trend", "BULLISH" if trend[-1] == -1 else "BEARISH", UP if trend[-1] == -1 else DN),
            ("Position", pos, UP if pos == "LONG" else DN if pos == "SHORT" else DONE),
            ("Entry", f"{last['entry']:.2f}", "white"),
            ("Stop", f"{last['sl']:.2f}", DN),
            ("Targets", " / ".join(f"{v:.2f}" for v in last["tp"]), UP),
            ("Status", status, UP if not last["closed"] else DONE)]
    for j, (k_, v_, c_) in enumerate(rows):
        yy = 0.878 - j * 0.036
        ax.text(0.014, yy, k_, transform=ax.transAxes, color=TXT, fontsize=7.8, va="top", zorder=10)
        ax.text(0.088, yy, v_, transform=ax.transAxes, color=c_, fontsize=7.8, va="top",
                fontweight="bold", zorder=10)

handles = [
    plt.Line2D([], [], color=UP, linewidth=2, label="Supertrend bullish"),
    plt.Line2D([], [], color=DN, linewidth=2, label="Supertrend bearish"),
    plt.Line2D([], [], color=ENT, linewidth=2, label="entry"),
    plt.Line2D([], [], color=DN, linewidth=1.2, linestyle="--", label="stop-loss"),
    plt.Line2D([], [], color=UP, linewidth=1.2, linestyle=":", label="targets 1R / 2R / 3R"),
]
leg = ax.legend(handles=handles, loc="lower left", facecolor=BG, edgecolor=GRID, fontsize=8.0,
                labelcolor=TXT, framealpha=0.95, ncol=5)
leg.get_frame().set_linewidth(0.8)

plt.tight_layout()
fig.savefig("preview/TrendPilotPro-preview.png", facecolor=BG, bbox_inches="tight")
print("saved preview/TrendPilotPro-preview.png", len(trades), "trades",
      [t["dir"] for t in trades])
