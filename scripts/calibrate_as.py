import numpy as np
import polars as pl

book = pl.read_parquet("data/btcusdt_2*.parquet")
book = book.filter(pl.col("session_id") == book["session_id"].max()).sort("arrival_ns")
lo, hi = book["arrival_ns"].min(), book["arrival_ns"].max()
trades = (pl.read_parquet("data/trades_*.parquet")
          .filter(pl.col("arrival_ns").is_between(lo, hi))
          .sort("arrival_ns"))

bt = book["arrival_ns"].to_numpy()
mid = ((book["bid"] + book["ask"]) / 2).to_numpy()
tt = trades["arrival_ns"].to_numpy()
tp = trades["price"].to_numpy()
buy = ~trades["buyer_maker"].to_numpy().astype(bool)

i = np.searchsorted(bt, tt, side="right") - 1
ok = i >= 0
tt, tp, buy, i = tt[ok], tp[ok], buy[ok], i[ok]
delta = np.maximum(np.where(buy, tp - mid[i], mid[i] - tp), 0.0)
seconds = (hi - lo) / 1e9

grid = np.arange(lo + 5 * 10**9, hi - 5 * 10**9, 10**9)
gi = np.searchsorted(bt, grid, side="right") - 1
fresh = (grid - bt[gi]) < 2 * 10**9
dm = np.diff(mid[gi])[fresh[:-1] & fresh[1:]]
sigma = dm.std()

deltas = np.array([0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0])
for name, mask in (("buyers hitting asks", buy), ("sellers hitting bids", ~buy)):
    d = delta[mask]
    counts = np.array([(d >= x).sum() for x in deltas])
    rate = counts / seconds
    print(f"\n{name}: {len(d)} trades, {len(d) / seconds:.2f} per second")
    print("  delta   count   rate/s   local k from the previous delta")
    prev = None
    for x, c, r in zip(deltas, counts, rate):
        k_loc = ""
        if prev is not None and c > 0 and prev[1] > 0:
            k_loc = f"{-(np.log(r) - np.log(prev[2])) / (x - prev[0]):.3f}"
        print(f"  {x:5.1f} {c:7d} {r:8.4f}   {k_loc}")
        prev = (x, c, r)
    use = (counts >= 30) & (deltas >= 0.5)
    slope, icpt = np.polyfit(deltas[use], np.log(rate[use]), 1)
    y = np.log(rate[use])
    fit = icpt + slope * deltas[use]
    r2 = 1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"  exponential fit for delta >= 0.5: A = {np.exp(icpt):.3f} per second, k = {-slope:.4f} per dollar, R^2 of the log fit {r2:.3f}")

print(f"\nsigma: {sigma:.3f} dollars per sqrt(second), from {len(dm)} one-second mid changes")