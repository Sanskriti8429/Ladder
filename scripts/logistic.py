import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression

bars = pl.read_parquet("data/bars_1s.parquet").sort("sec")
bars = bars.drop_nulls("vol").filter(pl.col("vol") > 0).filter(pl.col("y") != 0)   # drop flat seconds
feats = ["ofi_sum", "imb_last"]
embargo = 5
n = len(bars)

i0, i1 = int(n * 0.70), int(n * 0.85)
train = bars[:i0]
test = bars[i0:i1].filter(pl.col("sec") > train["sec"].max() + embargo)

Xtr, Xte = train.select(feats).to_numpy(), test.select(feats).to_numpy()
mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
ytr = (train["y"].to_numpy() > 0).astype(float)
yte = (test["y"].to_numpy() > 0).astype(float)


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


A = np.column_stack([np.ones(len(Xtr)), Xtr])
w = np.zeros(A.shape[1])
for step in range(5000):
    p = sigmoid(A @ w)
    w -= 0.5 * A.T @ (p - ytr) / len(ytr)

ptest = sigmoid(np.column_stack([np.ones(len(Xte)), Xte]) @ w)
acc = ((ptest > 0.5) == (yte == 1)).mean()
logloss = -np.mean(yte * np.log(ptest) + (1 - yte) * np.log(1 - ptest))
base = ytr.mean()
base_ll = -np.mean(yte * np.log(base) + (1 - yte) * np.log(1 - base))

sk = LogisticRegression(C=1e10, max_iter=1000).fit(Xtr, ytr)
print("rows kept (moving seconds):", n, " train:", len(ytr), " test:", len(yte))
print("share up in train:", round(ytr.mean(), 3), " in test:", round(yte.mean(), 3))
print("mine    : ", w)
print("sklearn :", np.r_[sk.intercept_, sk.coef_[0]])
print("test accuracy:", round(acc, 4), " always-up accuracy:", round(max(yte.mean(), 1 - yte.mean()), 4))
print("test log-loss:", round(logloss, 4), " constant-probability log-loss:", round(base_ll, 4))

lag = bars.sort("sec").with_columns(pl.col("y").shift(-1).over(["session_id", "segment_id"]).alias("y2")).drop_nulls("y2")
lag = lag.filter(pl.col("y2") != 0)
m = len(lag)
tr2, te2 = lag[: int(m * 0.70)], lag[int(m * 0.70): int(m * 0.85)]
te2 = te2.filter(pl.col("sec") > tr2["sec"].max() + embargo)
X2tr, X2te = tr2.select(feats).to_numpy(), te2.select(feats).to_numpy()
m2, s2 = X2tr.mean(axis=0), X2tr.std(axis=0)
X2tr, X2te = (X2tr - m2) / s2, (X2te - m2) / s2
sk2 = LogisticRegression(C=1e10, max_iter=1000).fit(X2tr, (tr2["y2"].to_numpy() > 0))
acc2 = (sk2.predict(X2te) == (te2["y2"].to_numpy() > 0)).mean()
print("two seconds ahead: rows", len(te2), " accuracy:", round(acc2, 4))