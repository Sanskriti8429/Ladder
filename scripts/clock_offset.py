import polars as pl

df = pl.read_parquet("data/trades_*.parquet")
lag_ms = df["arrival_ns"] / 1e6 - df["t_ms"]
print(lag_ms.describe())
print("share of trades arriving before their exchange timestamp:", round((lag_ms < 0).mean(), 3))