import polars as pl
df = pl.read_parquet("data/btcusdt_2*.parquet")
print(df.height, df["segment_id"].unique().to_list())