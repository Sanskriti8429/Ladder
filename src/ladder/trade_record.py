import asyncio
import json
import os
import time

import polars as pl
import websockets

URL = "wss://stream.binance.com:9443/ws/btcusdt@trade"
FLUSH_SECONDS = 300


def flush(rows):
    if not rows:
        return
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    final = f"data/trades_{stamp}.parquet"
    tmp = final + ".tmp"
    pl.DataFrame(rows).write_parquet(tmp)
    os.replace(tmp, final)
    print(f"flushed {len(rows)} trades -> {final}")


async def record():
    session_id = time.time_ns()
    segment_id = -1
    rows = []
    last_flush = time.time()
    try:
        while True:
            try:
                async with websockets.connect(URL, open_timeout=3, close_timeout=1) as ws:
                    segment_id += 1
                    print(f"{time.strftime('%H:%M:%S')} connected, segment {segment_id}")
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        arrival_ns = time.time_ns()
                        d = json.loads(raw)
                        if d.get("e") != "trade":
                            continue
                        rows.append({
                            "session_id": session_id,
                            "segment_id": segment_id,
                            "arrival_ns": arrival_ns,
                            "trade_id": d.get("t"),
                            "t_ms": d.get("T"),
                            "price": float(d.get("p", "nan")),
                            "qty": float(d.get("q", "nan")),
                            "buyer_maker": d.get("m"),
                            "raw": raw,
                        })
                        if time.time() - last_flush > FLUSH_SECONDS:
                            flush(rows)
                            rows.clear()
                            last_flush = time.time()
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, OSError, json.JSONDecodeError) as e:
                print(f"{time.strftime('%H:%M:%S')} segment ended: {type(e).__name__}")
                flush(rows)
                rows.clear()
                last_flush = time.time()
                await asyncio.sleep(1)
    finally:
        flush(rows)


try:
    asyncio.run(record())
except KeyboardInterrupt:
    pass