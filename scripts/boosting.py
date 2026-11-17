import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from ladder.splits import purged_walk_forward

FRESH = 1_794_500_000_000_000_000
G = ["session_id", "segment_id"]
ALL = ["ofi_sum", "imb_last", "spread_last", "log_n", "vol"]
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


def boosted(**kw):
    return HistGradientBoostingRegressor(learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=200,
                                         l2_regularization=10.0, early_stopping=False, random_state=0, **kw)


old = bars.filter(pl.col("session_id") < FRESH).sort("sec")
new = bars.filter(pl.col("session_id") >= FRESH).sort("sec")
ytr, yte = old["y"].to_numpy(), new["y"].to_numpy()
base = ytr.mean()
print("older bars:", old.height, " fresh bars:", new.height)

cut = int(old.height * 0.85)
inner = old[:cut]
val = old[cut:].filter(pl.col("sec") > inner["sec"].max() + EMBARGO)
yin, yva = inner["y"].to_numpy(), val["y"].to_numpy()

print("\nfresh sessions (trained on the older sessions)")
for name, feats in (("linear, 2 features", TWO), ("linear, 5 features", ALL)):
    m = LinearRegression().fit(old.select(feats).to_numpy(), ytr)
    p = m.predict(new.select(feats).to_numpy())
    print(f"  {name:<22} R^2 {r2(yte, p, base):+.4f}  Spearman {spearman(yte, p):.3f}")

for name, feats in (("boosted, 2 features", TWO), ("boosted, 5 features", ALL)):
    m = boosted(max_iter=600).fit(inner.select(feats).to_numpy(), yin)
    scores = [r2(yva, p, yin.mean()) for p in m.staged_predict(val.select(feats).to_numpy())]
    best = int(np.argmax(scores)) + 1
    for i, p in enumerate(m.staged_predict(new.select(feats).to_numpy()), 1):
        if i == best:
            break
    print(f"  {name:<22} R^2 {r2(yte, p, base):+.4f}  Spearman {spearman(yte, p):.3f}  trees {best}  (validation R^2 {max(scores):+.4f})")

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
X = b.select(ALL).to_numpy()
y = b["yH"].to_numpy()
n = len(y)
cut = int(n * 0.7)
random_idx = np.random.default_rng(0).permutation(n)
(train_p, test_p), = list(purged_walk_forward(t, H, EMBARGO, [(0.7, 1.0)]))
splits = {
    "random 70/30": (random_idx[:cut], random_idx[cut:]),
    "naive time split": (np.arange(cut), np.arange(cut, n)),
    "purged time split": (train_p, test_p),
}
models = {"linear": LinearRegression, "boosted (300 trees)": lambda: boosted(max_iter=300)}
print("\n10-second label on the older sessions:", n, "bars")
for mname, make in models.items():
    for sname, (tr, te) in splits.items():
        p = make().fit(X[tr], y[tr]).predict(X[te])
        print(f"  {mname:<20} {sname:<18} R^2 {r2(y[te], p, y[tr].mean()):+.4f}")