import json
import polars as pl
from ladder.depthbook import DepthBook

ev = pl.read_parquet("data/depth_events_*.parquet")
sn = pl.read_parquet("data/depth_snapshot_*.parquet")

session = ev["session_id"].max()
ev = ev.filter(pl.col("session_id") == session).sort("arrival_ns")
sn = sn.filter(pl.col("session_id") == session)

records = []
for seg in sorted(ev["segment_id"].unique().to_list()):
    snap = json.loads(sn.filter(pl.col("segment_id") == seg)["raw"][0])
    book = DepthBook()
    book.apply_snapshot(snap["lastUpdateId"], snap["bids"], snap["asks"])
    for raw in ev.filter(pl.col("segment_id") == seg)["raw"]:
        event = json.loads(raw)
        if event["u"] <= snap["lastUpdateId"]:
            continue
        book.apply_event(event)
        bid, ask = max(book.bids), min(book.asks)
        records.append({"u": event["u"], "bid": bid / 100, "bid_qty": book.bids[bid],
                        "ask": ask / 100, "ask_qty": book.asks[ask]})

lo, hi = ev["arrival_ns"].min(), ev["arrival_ns"].max()
tk = (pl.read_parquet("data/btcusdt_2*.parquet")
      .filter(pl.col("arrival_ns").is_between(lo, hi))
      .sort("update_id"))
print("rebuilt events:", len(records), " bookTicker rows in the window:", tk.height)

m = (pl.DataFrame(records).sort("u")
     .join_asof(tk.select("update_id", "bid", "bid_qty", "ask", "ask_qty"),
                left_on="u", right_on="update_id", strategy="backward", suffix="_tk")
     .drop_nulls())

last_ticker_id = tk["update_id"].max()
m = m.filter(pl.col("u") <= last_ticker_id)

m = m.with_columns(
    ((pl.col("bid") == pl.col("bid_tk")) & (pl.col("ask") == pl.col("ask_tk"))).alias("price_ok"),
    (((pl.col("bid_qty") - pl.col("bid_qty_tk")).abs() < 1e-9)
     & ((pl.col("ask_qty") - pl.col("ask_qty_tk")).abs() < 1e-9)).alias("qty_ok"),
)
print("events compared:", m.height)
print("best prices match:", m["price_ok"].mean())
print("prices and sizes match:", (m["price_ok"] & m["qty_ok"]).mean())
bad = m.filter(~pl.col("qty_ok"))
print(bad.select("u", "bid_qty", "bid_qty_tk", "ask_qty", "ask_qty_tk").head(10))
print("mismatches:", bad.height)

if bad.height:
    first, last = bad["u"].min(), bad["u"].max()
    print("first compared event:", m["u"].min(), " first mismatch:", first, " last mismatch:", last)
    print(tk.filter(pl.col("update_id").is_between(first - 300, last + 300))
            .select("update_id", "arrival_ns", "bid_qty", "ask_qty"))