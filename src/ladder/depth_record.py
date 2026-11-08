import asyncio
import json
import os
import time
import urllib.request

import polars as pl
import websockets

from ladder.depthbook import DepthBook, ChainBreak

WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"
SNAP_URL = "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=1000"
FLUSH_SECONDS = 300 


def fetch_snapshot():
    with urllib.request.urlopen(SNAP_URL) as resp:
        return resp.read().decode()


def flush(rows, kind):
    if not rows:
        return
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    final = f"data/depth_{kind}_{stamp}.parquet"
    tmp = final + ".tmp"
    pl.DataFrame(rows).write_parquet(tmp)
    os.replace(tmp, final)
    print(f"flushed {len(rows)} {kind} -> {final}")


async def record():
    session_id = time.time_ns()
    segment_id = -1
    rows = []
    snaps = []
    last_flush = time.time()
    try:
        while True:
            try:
                book = DepthBook()
                buffered = []
                async with websockets.connect(WS_URL, open_timeout=3, close_timeout=1) as ws:
                    snap_task = asyncio.create_task(asyncio.to_thread(fetch_snapshot))
                    while not snap_task.done():
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        buffered.append((time.time_ns(), raw))
                    snap_raw = snap_task.result()
                    book.sync(json.loads(snap_raw), [json.loads(r) for _, r in buffered])

                    segment_id += 1
                    snaps.append({"session_id": session_id, "segment_id": segment_id,
                                  "arrival_ns": time.time_ns(), "raw": snap_raw})
                    flush(snaps, "snapshot")
                    snaps.clear()
                    for arrival_ns, raw in buffered:
                        rows.append({"session_id": session_id, "segment_id": segment_id,
                                     "arrival_ns": arrival_ns, "raw": raw})
                    print(f"{time.strftime('%H:%M:%S')} synced, segment {segment_id}")

                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        arrival_ns = time.time_ns()
                        event = json.loads(raw)
                        book.apply_event(event)
                        rows.append({"session_id": session_id, "segment_id": segment_id,
                                     "arrival_ns": arrival_ns, "raw": raw})
                        if time.time() - last_flush > FLUSH_SECONDS:
                            flush(rows, "events")
                            rows.clear()
                            last_flush = time.time()
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, OSError, ChainBreak) as e:
                print(f"{time.strftime('%H:%M:%S')} segment ended: {type(e).__name__}")
                flush(rows, "events")
                rows.clear()
                last_flush = time.time()
                await asyncio.sleep(1)
    finally:
        flush(rows, "events")


try:
    asyncio.run(record())
except KeyboardInterrupt:
    pass