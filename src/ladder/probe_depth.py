import asyncio
import json
import time
import websockets

URL= "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"
DURATION = 30

async def main():
    n=0
    breaks=0
    levels=0
    prev_u= None
    start = time.time()
    
    async with websockets.connect(URL) as ws:
        async for message in ws:
            d = json.loads(message)
            if prev_u is not None and d["U"] != prev_u + 1:
                breaks += 1
            prev_u = d["u"]
            n += 1
            levels += len(d["b"]) + len(d["a"])
            if time.time() - start > DURATION:
                elapsed = time.time() - start
                break

    print(f"events: {n} in {elapsed:.1f}s -> {n / elapsed:.1f} per second")
    print(f"chain breaks: {breaks}")
    print(f"average levels per event: {levels / n:.1f}")


asyncio.run(main())