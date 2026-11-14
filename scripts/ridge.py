import numpy as np
import polars as pl
from sklearn.linear_model import Ridge

bars = pl.read_parquet("data/bars_1s.parquet").sort("sec")
bars = bars.drop_nulls("vol").filter(pl.col("vol") > 0)
feats = ["ofi_sum", "imb_last"]
embargo = 5
n = len(bars)


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


def ridge_fit(X, y, lam):
    k = X.shape[1]
    return np.linalg.solve(X.T @ X + lam * np.eye(k), X.T @ y)


i0, i1 = int(n * 0.70), int(n * 0.85)
train = bars[:i0]
test = bars[i0:i1].filter(pl.col("sec") > train["sec"].max() + embargo)

Xtr, Xte = train.select(feats).to_numpy(), test.select(feats).to_numpy()
mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
ytr, yte = train["y"].to_numpy(), test["y"].to_numpy()
vtr, vte = train["vol"].to_numpy(), test["vol"].to_numpy()
target = ytr / vtr
c = target.mean()

print("rows in train:", len(Xtr))
print("lambda          w_ofi     w_imb    test R^2")
for lam in [0, 1, 100, 10_000, 1_000_000, 100_000_000]:
    w = ridge_fit(Xtr, target - c, lam)
    pred = (c + Xte @ w) * vte
    print(f"{lam:>11}  {w[0]:9.5f}  {w[1]:9.5f}  {r2(yte, pred, ytr.mean()):.4f}")

lam = 10_000
w_mine = ridge_fit(Xtr, target - c, lam)
sk = Ridge(alpha=lam).fit(Xtr, target)
print("mine    :", w_mine, " intercept", c)
print("sklearn :", sk.coef_, " intercept", sk.intercept_)