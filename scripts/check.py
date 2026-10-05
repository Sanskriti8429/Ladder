import polars as pl

df = pl.read_parquet("data/btcusdt_2*.parquet")
print(df.shape)
print(df.head())
print("sorted:", df["arrival_ns"].is_sorted())
print(df.schema)

df= df.with_columns(
    (pl.col("arrival_ns").diff()/1e6).alias("gap_ms"),
    pl.col("update_id").diff().alias("id_jump"),
    (
        (pl.col("bid") != pl.col("bid").shift(1))
        | (pl.col("ask") != pl.col("ask").shift(1))
    )
    .fill_null(False)
    .alias("price_moved"),
)

print("\n--- gaps between messages ---")
print("median:",df["gap_ms"].median())
print("99th percentile:",df["gap_ms"].quantile(0.99))
print("max:",df["gap_ms"].max())

n_moved= df["price_moved"].sum()
print("--- price moved ---")
print(f"{n_moved} of {df.height-1} rows ({100* n_moved/(df.height-1):.2f}%)")

print("\n--- update_id jump ---")
print("median jump:",df["id_jump"].median())
print("max jump:",df["id_jump"].max())
clean= df.drop_nulls(["gap_ms", "id_jump"])
print(
    "rank correlation (gap_ms vs id_jump):",
    clean.select(pl.corr("gap_ms", "id_jump", method="spearman")).item(),
)