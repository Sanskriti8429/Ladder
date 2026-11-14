"""Leakage 2: real features, 10-second labels, linear vs nearest-neighbour model,
random split vs naive time split vs purged time split."""
import numpy as np
import polars as pl
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from ladder.splits import purged_walk_forward

g = ["session_id", "segment_id"]
bars = pl.read_parquet("data/bars_1s.parquet").sort(g + ["sec"])
H, EMBARGO = 10, 30
b = bars.with_columns(
    (pl.col("mid_last").shift(-H).over(g) - pl.col("mid_last")).alias("yH"),
    (pl.col("sec").shift(-H).over(g) - pl.col("sec")).alias("span"),
).filter(pl.col("span") == H).sort("sec")

t = b["sec"].to_numpy().astype(float)
X = b.select(["ofi_sum", "imb_last"]).to_numpy()
y = b["yH"].to_numpy()
n = len(y)


def score(make_model, tr, te):
    mu, sd = X[tr].mean(axis=0), X[tr].std(axis=0)
    model = make_model().fit((X[tr] - mu) / sd, y[tr])
    p = model.predict((X[te] - mu) / sd)
    return 1 - ((y[te] - p) ** 2).sum() / ((y[te] - y[tr].mean()) ** 2).sum()


cut = int(n * 0.7)
random_idx = np.random.default_rng(0).permutation(n)
(train_p, test_p), = list(purged_walk_forward(t, H, EMBARGO, [(0.7, 1.0)]))

splits = {
    "random 70/30": (random_idx[:cut], random_idx[cut:]),
    "naive time split": (np.arange(cut), np.arange(cut, n)),
    "purged time split": (train_p, test_p),
}
models = {
    "linear": LinearRegression,
    "nearest-neighbour k=5": lambda: KNeighborsRegressor(n_neighbors=5),
}

print("bars with a clean 10-second label:", n)
print("training rows: random", cut, " naive", cut, " purged", len(train_p), " (test rows", len(test_p), ")")
print()
for mname, make in models.items():
    for sname, (tr, te) in splits.items():
        print(f"{mname:<22} {sname:<18} R^2 = {score(make, tr, te):.4f}")
    print()