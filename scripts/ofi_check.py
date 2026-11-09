import polars as pl
from ladder.features import ofi

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