import asyncio
import json
import time
import websockets
import polars as pl

URL= "wss://stream.binance.com:9443/ws/btcusdt@bookTicker"
DURATION = 60

async def main():
    rows=[]
    segment_id=0
    start= time.time()
    
    async with websockets.connect(URL) as ws:
        async for message in ws:
            arrival_ns= time.time_ns()
            d= json.loads(message)
            
            rows.append({
                "arrival_ns": arrival_ns,
                "segment_id": segment_id,
                "update_id": d["u"],
                "bid": float(d["b"]),
                "bid_qty": float(d["B"]),
                "ask": float(d["a"]),
                "ask_qty": float(d["A"])
            })
            
            if time.time() - start > DURATION:
                break
            
    df = pl.DataFrame(rows)
    df.write_parquet("data/btcusdt_book.parquet")
    print(f"saved {df.height} rows")

asyncio.run(main())