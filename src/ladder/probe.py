import asyncio
import json
import time
import websockets

URL= "wss://stream.binance.com:9443/ws/btcusdt@bookTicker"
DURATION= 30

async def main():
    n=0
    price_changes=0
    prev_bid=None
    prev_ask= None
    start= time.time()
    
    async with websockets.connect(URL) as ws:
        async for message in ws:
            d= json.loads(message)
            
            bid, bid_qty= float(d["b"]), float(d["B"])
            ask, ask_qty= float(d["a"]), float(d["A"])
            
            spread= ask-bid
            imbalance= (bid_qty-ask_qty)/(bid_qty+ask_qty)
            
            if prev_bid is not None and (bid!=prev_bid or ask!=prev_ask):
                price_changes += 1
            prev_bid, prev_ask= bid, ask
            
            n+=1
            if n<=5:
                print(f"bid: {bid}, ask: {ask}, spread: {spread:.2f}, imbalance: {imbalance:+.3f}")
                
            if time.time() - start> DURATION:
                elapsed= time.time()-start
                break
            
    print(f"\nmessages: {n} in {elapsed:.1f}s -> {n/elapsed:.1f} per second")
    print(f"messages where the price moved: {price_changes} ({100*price_changes/ n:.1f}%)")
    
asyncio.run(main())