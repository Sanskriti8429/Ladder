import numpy as np
import polars as pl

book = pl.read_parquet("data/btcusdt_2*.parquet")
book = book.filter(pl.col("session_id") == book["session_id"].max()).sort("arrival_ns")
lo, hi = book["arrival_ns"].min(), book["arrival_ns"].max()
trades = (pl.read_parquet("data/trades_*.parquet")
          .filter(pl.col("arrival_ns").is_between(lo, hi))
          .sort("trade_id")
          .with_columns(
              ((pl.col("t_ms") != pl.col("t_ms").shift(1)) | (pl.col("buyer_maker") != pl.col("buyer_maker").shift(1)))
              .fill_null(True)
              .alias("first")
          ))

bt = book["arrival_ns"].to_numpy()
mid = ((book["bid"] + book["ask"]) / 2).to_numpy()
tt = trades["arrival_ns"].to_numpy()
tp = trades["price"].to_numpy()
buy = ~trades["buyer_maker"].to_numpy().astype(bool)
first = trades["first"].to_numpy()

i = np.searchsorted(bt, tt, side="right") - 1
ok = i >= 0
tp, buy, first, i = tp[ok], buy[ok], first[ok], i[ok]
delta = np.maximum(np.where(buy, tp - mid[i], mid[i] - tp), 0.0)

print("trades:", len(delta), " first trade of an order:", int(first.sum()), f"({first.mean():.3f})")
deltas = [0.5, 1.0, 2.0, 5.0, 10.0]
for name, mask in (("buyers hitting asks", buy), ("sellers hitting bids", ~buy)):
    for label, m in (("all trades", mask), ("first trade of each order", mask & first)):
        d = delta[m]
        shares = "  ".join(f">= {x:g}: {(d >= x).mean():.4f}" for x in deltas)
        print(f"{name:<22} {label:<26} n {len(d):>7}  share reaching {shares}")