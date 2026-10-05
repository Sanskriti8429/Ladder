import asyncio
import json
import time
import websockets
import polars as pl
import os

URL= "wss://stream.binance.com:9443/ws/btcusdt@bookTicker"
FLUSH_SECONDS= 300

def flush(rows):
    if not rows:
        return
    df= pl.DataFrame(rows)
    stamp= time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
    final= f"data/btcusdt_{stamp}.parquet"
    tmp= final + ".tmp"
    df.write_parquet(tmp)
    os.replace(tmp, final)
    print(f"flushed {len(rows)} rows-> {final}")

async def record():
    rows=[]
    segment_id= -1
    last_flush= time.time()
    session_id = time.time_ns()
    
    try:
        while True:
            try:
                async with websockets.connect(URL, open_timeout=3, close_timeout=1) as ws:
                    segment_id +=1
                    print(f"{time.strftime('%H:%M:%S')} connected, segment {segment_id}")
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
                            "ask_qty": float(d["A"]),
                            "session_id": session_id,
                        })
                    
                        if time.time()- last_flush> FLUSH_SECONDS:
                            flush(rows)
                            rows.clear()
                            last_flush= time.time()
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, OSError) as e:
                print(f"{time.strftime('%H:%M:%S')} segment {segment_id} ended: {type(e).__name__}")
                flush(rows)
                rows.clear()
                last_flush = time.time()
                await asyncio.sleep(1)
    
    finally:
        flush(rows)

asyncio.run(record())