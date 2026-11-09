import numpy as np
import polars as pl

bars = pl.read_parquet("data/bars_1s.parquet").sort("sec")
feats = ["ofi_sum", "imb_last", "spread_last"]

cut = int(len(bars) * 0.7)
embargo = 5
train = bars[:cut]
test = bars.filter(pl.col("sec") > train["sec"].max() + embargo)

Xtr, ytr = train.select(feats).to_numpy(), train["y"].to_numpy()
Xte, yte = test.select(feats).to_numpy(), test["y"].to_numpy()

mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
Xtr = (Xtr - mu) / sd
Xte = (Xte - mu) /sd

A = np.column_stack([np.ones(len(Xtr)), Xtr])
w, *_ = np.linalg.lstsq(A, ytr, rcond=None)
pred = np.column_stack([np.ones(len(Xte)), Xte]) @ w


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


print("train bars:", len(train), " test bars:", len(test))
print("weights (const, ofi_sum, imb_last, spread_last):", w)
print("test R^2 against the train-mean benchmark:", r2(yte, pred, ytr.mean()))
print("test Spearman:", pl.DataFrame({"p": pred, "y": yte}).select(pl.corr("p", "y", method="spearman")).item())

for cols in ([0], [1], [2], [0, 1], [0, 1, 2]):
    A_ = np.column_stack([np.ones(len(Xtr)), Xtr[:, cols]])
    w_, *_ = np.linalg.lstsq(A_, ytr, rcond=None)
    p_ = np.column_stack([np.ones(len(Xte)), Xte[:, cols]]) @ w_
    print([feats[c] for c in cols], "test R^2:", r2(yte, p_, ytr.mean()))