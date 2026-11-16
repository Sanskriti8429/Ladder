import numpy as np
import polars as pl

SIZE = 0.01
WAIT, HOLD = 10 * 10**9, 1 * 10**9
STALE, GAP, EPS = 2 * 10**9, 3 * 10**9, 1e-9

book = pl.read_parquet("data/btcusdt_2*.parquet")
book = book.filter(pl.col("session_id") == book["session_id"].max()).sort("arrival_ns")
lo, hi = book["arrival_ns"].min(), book["arrival_ns"].max()
trades = (pl.read_parquet("data/trades_*.parquet")
          .filter(pl.col("arrival_ns").is_between(lo, hi))
          .sort("arrival_ns"))

bt = book["arrival_ns"].to_numpy()
bid, bq = book["bid"].to_numpy(), book["bid_qty"].to_numpy()
ask, aq = book["ask"].to_numpy(), book["ask_qty"].to_numpy()
mid = (bid + ask) / 2
tt = trades["arrival_ns"].to_numpy()
tp, tq = trades["price"].to_numpy(), trades["qty"].to_numpy()
bm = trades["buyer_maker"].to_numpy().astype(bool)

big = np.diff(bt) > GAP
g1 = (bt[:-1][big], bt[1:][big])
cut = np.diff(trades["segment_id"].to_numpy()) != 0
g2 = (tt[:-1][cut], tt[1:][cut])
gs, ge = np.concatenate([g1[0], g2[0]]), np.concatenate([g1[1], g2[1]])


def idx(t):
    return np.searchsorted(bt, t, side="right") - 1


def try_fill(side, t0, keep):
    i = idx(t0)
    p, ahead = (bid[i], bq[i]) if side == "buy" else (ask[i], aq[i])
    j0, j1 = np.searchsorted(tt, [t0, t0 + WAIT], side="right")
    sp, sq, sm = tp[j0:j1], tq[j0:j1], bm[j0:j1]
    aggressor = sm if side == "buy" else ~sm
    through = aggressor & ((sp < p - EPS) if side == "buy" else (sp > p + EPS))
    at = aggressor & (np.abs(sp - p) < EPS)
    done = through | (np.cumsum(np.where(at, sq, 0.0)) >= ahead * keep + SIZE)
    if not done.any():
        return p, None, 0
    first = int(np.argmax(done))
    return p, int(tt[j0 + first]), int(through[first])


times = []
for t0 in range(lo + 5 * 10**9, hi - (WAIT + 2 * HOLD + 5 * 10**9), 10**9):
    i0 = idx(t0)
    if i0 < 0 or t0 - bt[i0] > STALE:
        continue
    if np.any((gs < t0 + WAIT + 2 * HOLD) & (ge > t0 - STALE)):
        continue
    times.append(t0)
print("decision times used:", len(times))

for c in [0.0, 0.25, 0.5, 0.75, 1.0]:
    print(f"\nshare of the queue ahead that cancels before our fill: {c:.2f}")
    for side in ("buy", "sell"):
        sgn = 1 if side == "buy" else -1
        out = []
        for t0 in times:
            p, tf, kind = try_fill(side, t0, 1 - c)
            if tf is None:
                out.append((0, 0.0, 0))
            else:
                out.append((1, sgn * (mid[idx(tf + HOLD)] - p), kind))
        r = np.array(out)
        f = r[:, 0] == 1
        print(f"  {side:<4} fill rate {f.mean():.3f}  trade-through share {r[f, 2].mean():.3f}  "
              f"PnL per fill {r[f, 1].mean():+.3f}  PnL per posted order {r[:, 1].mean():+.3f}")