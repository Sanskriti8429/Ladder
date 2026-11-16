import time
import numpy as np
import polars as pl
from ladder.orderbook import OrderBook

df = pl.read_csv("data/events.csv")
op = df["op"].to_list()
oid = df["id"].to_list()
side = ["buy" if s == 0 else "sell" for s in df["side"].to_list()]
price = df["price"].to_list()
qty = df["qty"].to_list()
n = len(op)
MASK = (1 << 64) - 1
PRIME = 1099511628211
BASIS = 14695981039346656037


def throughput():
    book = OrderBook()
    add, market, cancel = book.add_limit, book.market_order, book.cancel
    t0 = time.perf_counter()
    for i in range(n):
        o = op[i]
        if o == 0:
            add(oid[i], side[i], price[i], qty[i])
        elif o == 1:
            market(side[i], qty[i])
        else:
            cancel(oid[i])
    return time.perf_counter() - t0


def checked():
    book = OrderBook()
    h = BASIS
    fills = 0
    lat = [[], [], []]
    clock = time.perf_counter_ns
    for i in range(n):
        o = op[i]
        t0 = clock()
        if o == 0:
            res = book.add_limit(oid[i], side[i], price[i], qty[i])
        elif o == 1:
            res = book.market_order(side[i], qty[i])
        else:
            res = book.cancel(oid[i])
        lat[o].append(clock() - t0)
        if o == 2:
            h = ((h ^ (1 if res else 0)) * PRIME) & MASK
        else:
            fills += len(res)
            for a, b, c in res:
                h = ((h ^ a) * PRIME) & MASK
                h = ((h ^ b) * PRIME) & MASK
                h = ((h ^ c) * PRIME) & MASK
    return book, h, fills, lat


secs = throughput()
print(f"events: {n}  time: {secs:.2f} s  throughput: {n / secs:,.0f} events per second  mean {secs / n * 1e6:.2f} us per event")

book, h, fills, lat = checked()
names = ["limit order", "market order", "cancel"]
for k in range(3):
    a = np.array(lat[k]) / 1000
    p50, p99, p999 = np.percentile(a, [50, 99, 99.9])
    print(f"{names[k]:<13} count {len(a):>8}  median {p50:7.2f} us  p99 {p99:8.2f}  p99.9 {p999:9.2f}  max {a.max():10.1f}")

print("resting orders:", len(book.index), " bid levels:", len(book.books["buy"]), " ask levels:", len(book.books["sell"]))
print("best bid:", book.best_bid(), " best ask:", book.best_ask(), " fills:", fills)
print("checksum:", format(h, "016x"))
with open("data/expected.txt", "w") as f:
    f.write(f"{len(book.index)} {book.best_bid()} {book.best_ask()} {fills} {h:016x}\n")