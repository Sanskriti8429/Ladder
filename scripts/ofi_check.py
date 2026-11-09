import polars as pl
from ladder.features import ofi
import numpy as np

grp = ["session_id", "segment_id"]
df = pl.read_parquet("data/btcusdt_2*.parquet").sort(grp + ["update_id"])

df = df.with_columns(
    pl.col("bid").shift(1).over(grp).alias("pb"),
    pl.col("bid_qty").shift(1).over(grp).alias("pqb"),
    pl.col("ask").shift(1).over(grp).alias("pa"),
    pl.col("ask_qty").shift(1).over(grp).alias("pqa"),
)

f = pl.Float64
df = df.with_columns(
    (
        (pl.col("bid") >= pl.col("pb")).cast(f) * pl.col("bid_qty")
        - (pl.col("bid") <= pl.col("pb")).cast(f) * pl.col("pqb")
        - (pl.col("ask") <= pl.col("pa")).cast(f) * pl.col("ask_qty")
        + (pl.col("ask") >= pl.col("pa")).cast(f) * pl.col("pqa")
    ).alias("ofi")
).drop_nulls("ofi")

for r in df.sample(n=2000, seed=0).iter_rows(named=True):
    expected = ofi((r["pb"], r["pqb"], r["pa"], r["pqa"]),
                   (r["bid"], r["bid_qty"], r["ask"], r["ask_qty"]))
    assert abs(r["ofi"] - expected) < 1e-9
print("vectorised OFI matches the scalar function on 2000 random rows")
print(df["ofi"].describe())

bars = (
    df.with_columns(
        (pl.col("arrival_ns") // 1_000_000_000).alias("sec"),
        ((pl.col("bid") + pl.col("ask")) / 2).alias("mid"),
    )
    .group_by(grp + ["sec"], maintain_order=True)
    .agg(
        pl.col("ofi").sum().alias("ofi_sum"),
        pl.col("mid").last().alias("mid_last"),
        pl.len().alias("n"),
    )
    .sort(grp + ["sec"])
    .with_columns(
        (pl.col("mid_last") - pl.col("mid_last").shift(1).over(grp)).alias("dmid"),
        (pl.col("sec") - pl.col("sec").shift(1).over(grp)).alias("gap"),
    )
    .with_columns(
        pl.col("dmid").shift(-1).over(grp).alias("dmid_next"),
        pl.col("gap").shift(-1).over(grp).alias("gap_next"),
    )
    .filter(pl.col("gap_next") == 1)
)

x = bars["ofi_sum"].to_numpy()
y = bars["dmid_next"].to_numpy()
b = ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()
r = np.corrcoef(x, y)[0, 1]
print("seconds used:", len(x), " slope:", b, " R^2:", r ** 2)

print("Spearman:", bars.select(pl.corr("ofi_sum", "dmid_next", method="spearman")).item())

q = bars["ofi_sum"].abs().quantile(0.99)
trim = bars.filter(pl.col("ofi_sum").abs() <= q)
xt, yt = trim["ofi_sum"].to_numpy(), trim["dmid_next"].to_numpy()
print("R^2 without the top 1% of |OFI|:", np.corrcoef(xt, yt)[0, 1] ** 2)