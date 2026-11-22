import sys

import numpy as np
import polars as pl
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression

CUTOFF = 1794762753096358322
MIN_HOURS, MIN_SESSIONS = 20, 3
EMBARGO, BLOCK, RESAMPLES = 30, 60, 1000
G = ["session_id", "segment_id"]
TWO = ["ofi_sum", "imb_last"]
NOVOL = ["ofi_sum", "imb_last", "spread_last", "log_n"]
FORCE = "--force" in sys.argv

bars = (
    pl.read_parquet("data/bars_1s.parquet")
    .sort(G + ["sec"])
    .drop_nulls("vol")
    .filter(pl.col("vol") > 0)
    .with_columns(pl.col("n").cast(pl.Float64).log1p().alias("log_n"))
)
old = bars.filter(pl.col("session_id") <= CUTOFF).sort("sec")
new = bars.filter(pl.col("session_id") > CUTOFF).sort("sec")
hours = new.height / 3600
sessions = sorted(new["session_id"].unique().to_list())
print("training bars:", old.height, " held-out bars:", new.height, f"(about {hours:.1f} hours)", " held-out sessions:", len(sessions))
ready = hours >= MIN_HOURS and len(sessions) >= MIN_SESSIONS
if not ready:
    print(f"stopping rule not met: needs {MIN_HOURS} hours in at least {MIN_SESSIONS} sessions.")
    if not FORCE:
        sys.exit(0)
    print("EXPLORATORY RUN: this is not the pre-registered evaluation.")


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


def spearman(y, p):
    return float(np.corrcoef(rankdata(y), rankdata(p))[0, 1])


def boosted(iters):
    return HistGradientBoostingRegressor(
        learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=10.0,
        max_iter=iters, early_stopping=False, random_state=0,
    )


cut = int(old.height * 0.85)
inner = old[:cut]
val = old[cut:].filter(pl.col("sec") > inner["sec"].max() + EMBARGO)
yin, yva = inner["y"].to_numpy(), val["y"].to_numpy()
probe = boosted(600).fit(inner.select(NOVOL).to_numpy(), yin)
scores = [r2(yva, p, yin.mean()) for p in probe.staged_predict(val.select(NOVOL).to_numpy())]
trees = int(np.argmax(scores)) + 1
print(f"boosted tree count chosen on the validation block: {trees} (validation R^2 {max(scores):+.4f})")

ytr = old["y"].to_numpy()
base = ytr.mean()
linear = LinearRegression().fit(old.select(TWO).to_numpy(), ytr)
gb = boosted(trees).fit(old.select(NOVOL).to_numpy(), ytr)
models = [
    ("linear, 2 features", lambda t: linear.predict(t.select(TWO).to_numpy())),
    (f"boosted, no vol ({trees} trees)", lambda t: gb.predict(t.select(NOVOL).to_numpy())),
]


def interval(y, p, seed):
    n = len(y)
    nb = int(np.ceil(n / BLOCK))
    rng = np.random.default_rng(seed)
    offsets = np.arange(BLOCK)
    out = np.empty((RESAMPLES, 2))
    for i in range(RESAMPLES):
        starts = rng.integers(0, n - BLOCK + 1, size=nb)
        idx = (starts[:, None] + offsets).ravel()[:n]
        out[i] = (r2(y[idx], p[idx], base), spearman(y[idx], p[idx]))
    return np.percentile(out[:, 0], [2.5, 97.5]), np.percentile(out[:, 1], [2.5, 97.5])


print()
results = {}
sets = [("all held-out", new)] + [(f"session {s}", new.filter(pl.col("session_id") == s)) for s in sessions]
for name, predict in models:
    for label, t in sets:
        if t.height < 2 * BLOCK:
            continue
        y, p = t["y"].to_numpy(), predict(t)
        a, b = r2(y, p, base), spearman(y, p)
        (alo, ahi), (blo, bhi) = interval(y, p, 0)
        results[(name, label)] = (a, b)
        print(f"{name:<28} {label:<28} bars {t.height:>6}  R^2 {a:+.4f} [{alo:+.4f}, {ahi:+.4f}]  Spearman {b:.3f} [{blo:.3f}, {bhi:.3f}]")
    print()

lin_r2, lin_rho = results[(models[0][0], "all held-out")]
gb_r2, _ = results[(models[1][0], "all held-out")]
print("pre-registered predictions" + ("" if ready else " (exploratory run, not valid)"))
print(f"  linear R^2 in [0.03, 0.09]:        {lin_r2:+.4f}  {'PASS' if 0.03 <= lin_r2 <= 0.09 else 'FAIL'}")
print(f"  linear Spearman in [0.30, 0.45]:   {lin_rho:.3f}  {'PASS' if 0.30 <= lin_rho <= 0.45 else 'FAIL'}")
print(f"  boosted R^2 - linear R^2 <= 0.01:  {gb_r2 - lin_r2:+.4f}  {'PASS' if gb_r2 - lin_r2 <= 0.01 else 'FAIL'}")