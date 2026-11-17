import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from ladder.splits import purged_walk_forward

FRESH = 1_794_500_000_000_000_000
G = ["session_id", "segment_id"]
ALL = ["ofi_sum", "imb_last", "spread_last", "log_n", "vol"]
NOVOL = ["ofi_sum", "imb_last", "spread_last", "log_n"]
TWO = ["ofi_sum", "imb_last"]
EMBARGO = 30

bars = (
    pl.read_parquet("data/bars_1s.parquet")
    .sort(G + ["sec"])
    .drop_nulls("vol")
    .filter(pl.col("vol") > 0)
    .with_columns(pl.col("n").cast(pl.Float64).log1p().alias("log_n"))
)


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


def spearman(y, p):
    return pl.DataFrame({"p": p, "y": y}).select(pl.corr("p", "y", method="spearman")).item()


def boosted(iters):
    return HistGradientBoostingRegressor(learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=200,
                                         l2_regularization=10.0, max_iter=iters, early_stopping=False,
                                         random_state=0)


old = bars.filter(pl.col("session_id") < FRESH).sort("sec")
new = bars.filter(pl.col("session_id") >= FRESH).sort("sec")
ytr = old["y"].to_numpy()
base = ytr.mean()
cut = int(old.height * 0.85)
inner = old[:cut]
val = old[cut:].filter(pl.col("sec") > inner["sec"].max() + EMBARGO)
yin, yva = inner["y"].to_numpy(), val["y"].to_numpy()
sessions = [None] + sorted(new["session_id"].unique().to_list())


def subset(sid):
    return new if sid is None else new.filter(pl.col("session_id") == sid)


def pick(feats):
    m = boosted(600).fit(inner.select(feats).to_numpy(), yin)
    scores = [r2(yva, p, yin.mean()) for p in m.staged_predict(val.select(feats).to_numpy())]
    return int(np.argmax(scores)) + 1, max(scores)


fitted = {"linear, 2 features": (TWO, LinearRegression().fit(old.select(TWO).to_numpy(), ytr), "")}
for name, feats in (("boosted, 2 features", TWO), ("boosted, no vol", NOVOL), ("boosted, 5 features", ALL)):
    k, v = pick(feats)
    fitted[name] = (feats, boosted(k).fit(inner.select(feats).to_numpy(), yin), f"trees {k}, validation R^2 {v:+.4f}")

print("older bars:", old.height, " fresh bars:", new.height, " fresh sessions:", len(sessions) - 1)
print("\nfresh sessions: all, then each session on its own")
for name, (feats, m, note) in fitted.items():
    cells = []
    for sid in sessions:
        t = subset(sid)
        p = m.predict(t.select(feats).to_numpy())
        y = t["y"].to_numpy()
        cells.append(f"{r2(y, p, base):+.4f} / {spearman(y, p):.3f}")
    print(f"  {name:<20} R^2 / Spearman: {' | '.join(cells)}   {note}")

H = 10
b = (
    old.sort(G + ["sec"])
    .with_columns(
        (pl.col("mid_last").shift(-H).over(G) - pl.col("mid_last")).alias("yH"),
        (pl.col("sec").shift(-H).over(G) - pl.col("sec")).alias("span"),
    )
    .filter(pl.col("span") == H)
    .sort("sec")
)
t = b["sec"].to_numpy().astype(float)
y = b["yH"].to_numpy()
n = len(y)
cut = int(n * 0.7)
random_idx = np.random.default_rng(0).permutation(n)
(train_p, test_p), = list(purged_walk_forward(t, H, EMBARGO, [(0.7, 1.0)]))


def both(make, feats):
    X = b.select(feats).to_numpy()
    out = []
    for tr, te in ((random_idx[:cut], random_idx[cut:]), (train_p, test_p)):
        p = make().fit(X[tr], y[tr]).predict(X[te])
        out.append(r2(y[te], p, y[tr].mean()))
    return out


rows = [("linear, 5 features", LinearRegression, ALL)]
for iters in (30, 90, 300):
    rows.append((f"boosted {iters} trees, 5 features", lambda it=iters: boosted(it), ALL))
    rows.append((f"boosted {iters} trees, no vol", lambda it=iters: boosted(it), NOVOL))

print("\n10-second label on the older sessions:", n, "bars")
print(f"  {'model':<30}{'random':>9}{'purged':>9}{'gap':>9}")
for name, make, feats in rows:
    a, c = both(make, feats)
    print(f"  {name:<30}{a:+9.4f}{c:+9.4f}{a - c:+9.4f}")