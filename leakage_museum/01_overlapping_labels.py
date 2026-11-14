"""Leakage 1: overlapping labels.
A model that only knows the clock time scores R^2 = 0.845 on a random split and -0.131
on a time-ordered split, because the label of each bar covers the next 10 seconds and
neighbouring bars share 9 of them. Fix: split by time, and leave an embargo at least as
long as the label horizon plus the decay of the features' autocorrelation."""

import numpy as np
import polars as pl
from sklearn.neighbors import KNeighborsRegressor

g = ["session_id", "segment_id"]
bars = pl.read_parquet("data/bars_1s.parquet").sort(g + ["sec"])

print("autocorrelation at lags 1, 2, 3, 5, 10, 30 rows")
for name in ["ofi_sum", "imb_last", "y"]:
    v = bars[name].to_numpy()
    print(name.ljust(9), [round(np.corrcoef(v[:-k], v[k:])[0, 1], 3) for k in (1, 2, 3, 5, 10, 30)])

H = 10
b = bars.with_columns(
    (pl.col("mid_last").shift(-H).over(g) - pl.col("mid_last")).alias("yH"),
    (pl.col("sec").shift(-H).over(g) - pl.col("sec")).alias("span"),
).filter(pl.col("span") == H).sort("sec")
t = b["sec"].to_numpy().astype(float).reshape(-1, 1)
y = b["yH"].to_numpy()
n = len(y)


def score(tr, te):
    p = KNeighborsRegressor(n_neighbors=5).fit(t[tr], y[tr]).predict(t[te])
    return 1 - ((y[te] - p) ** 2).sum() / ((y[te] - y[tr].mean()) ** 2).sum()


cut = int(n * 0.7)
idx = np.random.default_rng(0).permutation(n)
print("\nrows with a clean 10-second label:", n)
print("random 70/30 split, model sees only the clock time:", round(score(idx[:cut], idx[cut:]), 4))
print("time-ordered 70/30 split, same model:", round(score(np.arange(cut), np.arange(cut, n)), 4))