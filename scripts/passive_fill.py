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
print("window hours:", round((hi - lo) / 3.6e12, 2), " book rows:", book.height, " trades:", trades.height)

bt = book["arrival_ns"].to_numpy()
bid, bq = book["bid"].to_numpy(), book["bid_qty"].to_numpy()
ask, aq = book["ask"].to_numpy(), book["ask_qty"].to_numpy()
mid = (bid + ask) / 2
tt = trades["arrival_ns"].to_numpy()
tp, tq = trades["price"].to_numpy(), trades["qty"].to_numpy()
bm = trades["buyer_maker"].to_numpy().astype(bool)


def gap_intervals(t):
    k = np.diff(t) > GAP
    return t[:-1][k], t[1:][k]


g1 = gap_intervals(bt)
seg = trades["segment_id"].to_numpy()
cut = np.diff(seg) != 0
g2 = (tt[:-1][cut], tt[1:][cut])
gs, ge = np.concatenate([g1[0], g2[0]]), np.concatenate([g1[1], g2[1]])
print("holes: book", len(g1[0]), " trades", len(g2[0]))
print("mean mid:", round(mid.mean(), 1), " share of aggressor sells:", round(bm.mean(), 3))


def idx(t):
    return np.searchsorted(bt, t, side="right") - 1


def try_fill(side, t0):
    i = idx(t0)
    p, ahead = (bid[i], bq[i]) if side == "buy" else (ask[i], aq[i])
    j0, j1 = np.searchsorted(tt, [t0, t0 + WAIT], side="right")
    sp, sq, sm = tp[j0:j1], tq[j0:j1], bm[j0:j1]
    aggressor = sm if side == "buy" else ~sm
    through = aggressor & ((sp < p - EPS) if side == "buy" else (sp > p + EPS))
    at = aggressor & (np.abs(sp - p) < EPS)
    done = through | (np.cumsum(np.where(at, sq, 0.0)) >= ahead + SIZE)
    if not done.any():
        return p, None, 0
    first = int(np.argmax(done))
    return p, int(tt[j0 + first]), int(through[first])


rows = {"buy": [], "sell": []}
drift, posted = [], 0
for t0 in range(lo + 5 * 10**9, hi - (WAIT + 2 * HOLD + 5 * 10**9), 10**9):
    i0 = idx(t0)
    if i0 < 0 or t0 - bt[i0] > STALE:
        continue
    if np.any((gs < t0 + WAIT + 2 * HOLD) & (ge > t0 - STALE)):
        continue
    posted += 1
    drift.append(mid[idx(t0 + HOLD)] - mid[i0])
    imb = (bq[i0] - aq[i0]) / (bq[i0] + aq[i0])
    for side in ("buy", "sell"):
        p, tf, kind = try_fill(side, t0)
        if tf is None:
            rows[side].append((0, 0.0, 0.0, 0.0, 0.0, imb, 0))
            continue
        a, b = idx(tf), idx(tf + HOLD)
        sgn = 1 if side == "buy" else -1
        move = sgn * (mid[b] - mid[a])
        pnl_mid = sgn * (mid[b] - p)
        pnl_taker = (bid[b] - p) if side == "buy" else (p - ask[b])
        rows[side].append((1, (tf - t0) / 1e9, move, pnl_mid, pnl_taker, imb, kind))

drift = np.array(drift)
print("decision times used:", posted, " mean 1 s mid change at random times:", round(drift.mean(), 4))
print("std of the 1 s mid change:", round(drift.std(), 3))
for side in ("buy", "sell"):
    r = np.array(rows[side])
    f = r[:, 0] == 1
    sgn = 1 if side == "buy" else -1
    print(f"\n{side}: fill rate {f.mean():.3f} ({f.sum()} fills), mean time to fill {r[f, 1].mean():.2f} s")
    print(f"  mean move 1 s after the fill (positive = good for us): {r[f, 2].mean():+.4f}   at a random time: {sgn * drift.mean():+.4f}")
    print(f"  mean PnL, exit at the mid after 1 s:  {r[f, 3].mean():+.4f}")
    print(f"  mean PnL, exit at the opposite quote: {r[f, 4].mean():+.4f}")
    qs = np.quantile(r[:, 5], [0.2, 0.4, 0.6, 0.8])
    bucket = np.digitize(r[:, 5], qs)
    print(f"  share of fills that were trade-throughs: {r[f, 6].mean():.3f}")
    print("  by imbalance at posting time (bucket 0 = ask-heavy ... 4 = bid-heavy):")
    for k in range(5):
        m = bucket == k
        print(f"    bucket {k}: posted {m.sum():>4}  fill rate {f[m].mean():.3f}  "
              f"mean PnL per posted order {r[m, 3].mean():+.3f}  mean PnL per fill {r[m & f, 3].mean():+.3f}")