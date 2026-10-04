import polars as pl

df = pl.read_parquet("data/btcusdt_book.parquet")

segs = (
    df.group_by("segment_id")
    .agg(
        pl.len().alias("rows"),
        pl.col("arrival_ns").min().alias("start_ns"),
        pl.col("arrival_ns").max().alias("end_ns"),
    )
    .sort("start_ns")
    .with_columns(
        ((pl.col("start_ns") - pl.col("end_ns").shift(1)) / 1e9).alias("gap_s"),
        ((pl.col("end_ns") - pl.col("start_ns")) / 1e9).alias("duration_s"),
    )
)
print(segs)