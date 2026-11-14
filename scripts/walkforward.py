import numpy as np
import polars as pl

bars = pl.read_parquet("data/bars_1s.parquet").sort("sec")
feats = ["ofi_sum", "imb_last"]
embargo = 30
bars = bars.drop_nulls("vol").filter(pl.col("vol") > 0)
n = len(bars)


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


rows = []
for a, b in [(0.40, 0.55), (0.55, 0.70), (0.70, 0.85), (0.85, 1.00)]:
    i0, i1 = int(n * a), int(n * b)
    train = bars[:i0]
    test = bars[i0:i1].filter(pl.col("sec") > train["sec"].max() + embargo)

    Xtr, ytr = train.select(feats).to_numpy(), train["y"].to_numpy()
    Xte, yte = test.select(feats).to_numpy(), test["y"].to_numpy()
    mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
    Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd

    w, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(Xtr)), Xtr]), ytr, rcond=None)
    pred = np.column_stack([np.ones(len(Xte)), Xte]) @ w

    score = r2(yte, pred, ytr.mean())
    rho = pl.DataFrame({"p": pred, "y": yte}).select(pl.corr("p", "y", method="spearman")).item()
    rows.append(score)
    print(f"test {a:.2f}-{b:.2f}: train {len(train)}, test {len(test)}, "
          f"price {test['mid_last'].min():.0f}-{test['mid_last'].max():.0f}, "
          f"R^2 {score:.4f}, Spearman {rho:.3f}")
    print("   y std: train", round(ytr.std(), 2), " test", round(yte.std(), 2),
          " | residual std:", round((yte - pred).std(), 2))
    d = pred - pred.mean()
    slope = (d * (yte - yte.mean())).sum() / (d ** 2).sum()
    corr2 = np.corrcoef(pred, yte)[0, 1] ** 2
    print("   calibration slope:", round(slope, 3), " R^2 if rescaled:", round(corr2, 4))
    vtr, vte = train["vol"].to_numpy(), test["vol"].to_numpy()
    w2, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(Xtr)), Xtr]), ytr / vtr, rcond=None)
    pred2 = (np.column_stack([np.ones(len(Xte)), Xte]) @ w2) * vte
    d2 = pred2 - pred2.mean()
    slope2 = (d2 * (yte - yte.mean())).sum() / (d2 ** 2).sum()
    print("   vol-scaled: R^2", round(r2(yte, pred2, ytr.mean()), 4), " calibration slope:", round(slope2, 3))

print("mean R^2:", np.mean(rows), " min:", min(rows), " max:", max(rows))
