import asyncio
import json
import time
import websockets
import polars as pl

URL= "wss://stream.binance.com:9443/ws/btcusdt@bookTicker"
DURATION = 90

async def record():
    rows=[]
    segment_id=0
    start= time.time()
    
    while time.time()-start< DURATION:
        try:
            async with websockets.connect(URL) as ws:
                while True:
                    message= await asyncio.wait_for(ws.recv(), timeout=5)
            
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
                    
                    if time.time()-start> DURATION:
                        break
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, OSError) as e:
            print(f"{time.strftime('%H:%M:%S')} segment {segment_id} ended: {type(e).__name__}")
            await asyncio.sleep(1)
            segment_id+=1
    df = pl.DataFrame(rows)
    df.write_parquet("data/btcusdt_book.parquet")
    print(f"saved {df.height} rows")

asyncio.run(record())