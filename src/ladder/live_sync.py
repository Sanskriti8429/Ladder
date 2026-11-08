import asyncio
import json
import time
import urllib.request
import websockets
from ladder.depthbook import DepthBook, ChainBreak

WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"
SNAP_URL = "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=1000"
DURATION = 30


def fetch_snapshot():
    with urllib.request.urlopen(SNAP_URL) as resp:
        return json.loads(resp.read())


async def main():
    book = DepthBook()
    buffered = []
    async with websockets.connect(WS_URL) as ws:
        snap_task = asyncio.create_task(asyncio.to_thread(fetch_snapshot))
        while not snap_task.done():
            buffered.append(json.loads(await ws.recv()))
        book.sync(snap_task.result(), buffered)
        print("synced at", book.last_update_id, "after buffering", len(buffered), "events")

        start = time.time()
        last_print = 0
        async for message in ws:
            event = json.loads(message)
            try:
                book.apply_event(event)
            except ChainBreak:
                print("chain break, would restart from a new snapshot")
                break
            if time.time() - last_print > 1:
                bid_tick= max(book.bids)
                ask_tick= min(book.asks)
                print(f"best bid {bid_tick / 100:.2f} x {book.bids[bid_tick]}   best ask {ask_tick / 100:.2f} x {book.asks[ask_tick]}")
                last_print = time.time()
            if time.time() - start > DURATION:
                break


asyncio.run(main())