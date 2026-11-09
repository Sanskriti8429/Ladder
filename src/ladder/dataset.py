import polars as pl

GRP = ["session_id", "segment_id"]


def build_bars(raw, bucket_ns=1_000_000_000):
    df = raw.sort(GRP + ["update_id"])
    df = df.with_columns(
        pl.col("bid").shift(1).over(GRP).alias("pb"),
        pl.col("bid_qty").shift(1).over(GRP).alias("pqb"),
        pl.col("ask").shift(1).over(GRP).alias("pa"),
        pl.col("ask_qty").shift(1).over(GRP).alias("pqa"),
    )
    f = pl.Float64
    total = pl.col("bid_qty") + pl.col("ask_qty")
    df = df.with_columns(
        (
            (pl.col("bid") >= pl.col("pb")).cast(f) * pl.col("bid_qty")
            - (pl.col("bid") <= pl.col("pb")).cast(f) * pl.col("pqb")
            - (pl.col("ask") <= pl.col("pa")).cast(f) * pl.col("ask_qty")
            + (pl.col("ask") >= pl.col("pa")).cast(f) * pl.col("pqa")
        ).alias("ofi"),
        pl.when(total > 0).then((pl.col("bid_qty") - pl.col("ask_qty")) / total)
          .otherwise(0.0).alias("imb"),
        ((pl.col("bid") + pl.col("ask")) / 2).alias("mid"),
        ((pl.col("ask") - pl.col("bid")) * 100).round(0).alias("spread"),
        (pl.col("arrival_ns") // bucket_ns).alias("sec"),
    ).drop_nulls("ofi")

    bars = (
        df.group_by(GRP + ["sec"], maintain_order=True)
        .agg(
            pl.col("ofi").sum().alias("ofi_sum"),
            pl.col("imb").last().alias("imb_last"),
            pl.col("spread").last().alias("spread_last"),
            pl.col("mid").last().alias("mid_last"),
            pl.len().alias("n"),
        )
        .sort(GRP + ["sec"])
        .with_columns(
            (pl.col("mid_last") - pl.col("mid_last").shift(1).over(GRP)).alias("dmid"),
            (pl.col("sec") - pl.col("sec").shift(1).over(GRP)).alias("gap"),
        )
        .with_columns(
            pl.col("dmid").shift(-1).over(GRP).alias("y"),
            pl.col("gap").shift(-1).over(GRP).alias("gap_next"),
        )
        .filter((pl.col("gap") == 1) & (pl.col("gap_next") == 1))
        .drop("gap", "gap_next")
    )
    return bars


if __name__ == "__main__":
    raw = pl.read_parquet("data/btcusdt_2*.parquet")
    bars = build_bars(raw)
    bars.write_parquet("data/bars_1s.parquet")
    print(bars.height, "bars,", bars["session_id"].n_unique(), "sessions")
    print(bars.describe())