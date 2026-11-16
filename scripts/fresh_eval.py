import numpy as np
import polars as pl

FRESH = 1_794_500_000_000_000_000
feats = ["ofi_sum", "imb_last"]

bars = pl.read_parquet("data/bars_1s.parquet").sort("sec")
bars = bars.drop_nulls("vol").filter(pl.col("vol") > 0)
train = bars.filter(pl.col("session_id") < FRESH)
test = bars.filter(pl.col("session_id") >= FRESH)

Xtr, ytr, vtr = train.select(feats).to_numpy(), train["y"].to_numpy(), train["vol"].to_numpy()
mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
A = np.column_stack([np.ones(len(Xtr)), (Xtr - mu) / sd])
w, *_ = np.linalg.lstsq(A, ytr, rcond=None)
w2, *_ = np.linalg.lstsq(A, ytr / vtr, rcond=None)


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


def slope(y, p):
    d = p - p.mean()
    return (d * (y - y.mean())).sum() / (d ** 2).sum()


print("train bars:", len(train), " test bars:", len(test), " test sessions:", test["session_id"].n_unique())
print("mean price: train", round(train["mid_last"].mean()), " test", round(test["mid_last"].mean()))
print("y std: train", round(ytr.std(), 2), " test", round(test["y"].std(), 2))

for sid in [None] + sorted(test["session_id"].unique().to_list()):
    t = test if sid is None else test.filter(pl.col("session_id") == sid)
    Xte, yte, vte = t.select(feats).to_numpy(), t["y"].to_numpy(), t["vol"].to_numpy()
    B = np.column_stack([np.ones(len(Xte)), (Xte - mu) / sd])
    p1, p2 = B @ w, (B @ w2) * vte
    rho = pl.DataFrame({"p": p1, "y": yte}).select(pl.corr("p", "y", method="spearman")).item()
    name = "all test sessions" if sid is None else f"session {sid}"
    print(f"\n{name}: bars {len(t)}, y std {yte.std():.2f}, mean price {t['mid_last'].mean():.0f}")
    print(f"  plain:      R^2 {r2(yte, p1, ytr.mean()):+.4f}  calibration slope {slope(yte, p1):.3f}  Spearman {rho:.3f}")
    print(f"  vol-scaled: R^2 {r2(yte, p2, ytr.mean()):+.4f}  calibration slope {slope(yte, p2):.3f}")