import numpy as np
import polars as pl

HORIZONS = [1, 5, 20, 100, 400]
G = ["session_id", "segment_id"]

df = (
    pl.read_parquet("data/btcusdt_2*.parquet")
    .with_columns(
        (pl.col("arrival_ns") // 1_000_000_000).alias("sec"),
        ((pl.col("bid") + pl.col("ask")) / 2).alias("mid"),
    )
    .sort(G + ["arrival_ns"])
    .group_by(G + ["sec"], maintain_order=True)
    .agg(pl.col("mid").last())
    .sort(G + ["sec"])
)

changes = {h: [] for h in HORIZONS}
for (sid, seg), g in df.group_by(G, maintain_order=True):
    sec = g["sec"].to_numpy()
    mid = g["mid"].to_numpy()
    full = np.arange(sec[0], sec[-1] + 1)
    mid = np.interp(full, sec, mid)
    for h in HORIZONS:
        if len(mid) > h + 1:
            changes[h].append(mid[h:] - mid[:-h])

v1 = np.concatenate(changes[1]).var()
print("segments used:", len(changes[1]), " one-second variance:", round(v1, 3), " std:", round(v1 ** 0.5, 3))
for h in HORIZONS:
    x = np.concatenate(changes[h])
    print(f"h = {h:>3} s: {len(x):>7} increments  variance {x.var():9.2f}  variance ratio {x.var() / (h * v1):.3f}")