import copy

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor

FRESH = 1_794_500_000_000_000_000
G = ["session_id", "segment_id"]
LAGS = 10
EMBARGO = 30
BASE = ["ofi_sum", "imb_last", "log_n"]

bars = (
    pl.read_parquet("data/bars_1s.parquet")
    .sort(G + ["sec"])
    .with_columns(pl.col("n").cast(pl.Float64).log1p().alias("log_n"))
)
cols = []
for k in range(LAGS):
    for f in BASE:
        name = f"{f}_l{k}"
        cols.append(name)
        bars = bars.with_columns(pl.col(f).shift(k).over(G).alias(name))
bars = bars.with_columns((pl.col("sec") - pl.col("sec").shift(LAGS - 1).over(G)).alias("span"))
bars = bars.filter(pl.col("span") == LAGS - 1).drop_nulls(cols)
lag0 = list(range(3))


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


def spearman(y, p):
    return pl.DataFrame({"p": p, "y": y}).select(pl.corr("p", "y", method="spearman")).item()


old = bars.filter(pl.col("session_id") < FRESH).sort("sec")
new = bars.filter(pl.col("session_id") >= FRESH).sort("sec")
cut = int(old.height * 0.85)
inner = old[:cut]
val = old[cut:].filter(pl.col("sec") > inner["sec"].max() + EMBARGO)
print("bars with a 10 second history: older", old.height, " fresh", new.height, " train", inner.height, " validation", val.height)

Xin, yin = inner.select(cols).to_numpy(), inner["y"].to_numpy()
mu, sd = Xin.mean(axis=0), Xin.std(axis=0)
sd[sd == 0] = 1.0


def prep(t):
    return (t.select(cols).to_numpy() - mu) / sd


Xin_s, Xva, yva = prep(inner), prep(val), val["y"].to_numpy()
base = old["y"].mean()
sessions = [None] + sorted(new["session_id"].unique().to_list())
Xnew = {sid: prep(new if sid is None else new.filter(pl.col("session_id") == sid)) for sid in sessions}
ynew = {sid: (new if sid is None else new.filter(pl.col("session_id") == sid))["y"].to_numpy() for sid in sessions}

lin0 = LinearRegression().fit(Xin_s[:, lag0], yin)
lin30 = LinearRegression().fit(Xin_s, yin)

gb = HistGradientBoostingRegressor(learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=200,
                                   l2_regularization=10.0, max_iter=600, early_stopping=False, random_state=0)
gb.fit(Xin_s[:, lag0], yin)
scores = [r2(yva, p, yin.mean()) for p in gb.staged_predict(Xva[:, lag0])]
trees = int(np.argmax(scores)) + 1
gb = HistGradientBoostingRegressor(learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=200,
                                   l2_regularization=10.0, max_iter=trees, early_stopping=False,
                                   random_state=0).fit(Xin_s[:, lag0], yin)

lo, hi = np.percentile(yin, [0.5, 99.5])
yclip = np.clip(yin, lo, hi)
mlp = MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1e-2, learning_rate_init=1e-3, batch_size=256, random_state=0)
best, best_epoch, best_model = -1e9, 0, None
curve = []
for epoch in range(1, 61):
    mlp.partial_fit(Xin_s, yclip)
    s = r2(yva, mlp.predict(Xva), yin.mean())
    curve.append(s)
    if s > best:
        best, best_epoch, best_model = s, epoch, copy.deepcopy(mlp)
print("MLP validation R^2 by epoch (every 10th):", " ".join(f"{curve[i]:+.4f}" for i in range(9, 60, 10)))

models = [
    ("linear, latest second", lambda X: lin0.predict(X[:, lag0]), ""),
    ("linear, 10 seconds", lambda X: lin30.predict(X), ""),
    ("boosted, latest second", lambda X: gb.predict(X[:, lag0]), f"trees {trees}, validation {max(scores):+.4f}"),
    ("MLP, 10 seconds", lambda X: best_model.predict(X), f"epoch {best_epoch}, validation {best:+.4f}"),
]
print("\nfresh sessions: R^2 / Spearman for all, then each session")
for name, predict, note in models:
    cells = []
    for sid in sessions:
        p, y = predict(Xnew[sid]), ynew[sid]
        cells.append(f"{r2(y, p, base):+.4f} / {spearman(y, p):.3f}")
    print(f"  {name:<24} {' | '.join(cells)}   {note}")