import numpy as np
from ladder.orderbook import OrderBook

N = 1_000_000
TARGET = 5_000
DEPTH = 100

rng = np.random.default_rng(42)
book = OrderBook()
live = []
log = []
next_id = 0


def limit(side, price, qty):
    global next_id
    book.add_limit(next_id, side, price, qty)
    live.append(next_id)
    log.append((0, next_id, 0 if side == "buy" else 1, price, qty))
    next_id += 1


for p in range(9900, 10000):
    limit("buy", p, int(rng.integers(1, 6)))
for p in range(10001, 10101):
    limit("sell", p, int(rng.integers(1, 6)))

while len(log) < N:
    r = rng.random()
    qty = int(rng.integers(1, 6))
    bp, ap = book.best_bid(), book.best_ask()
    p_add = 0.30 if len(book.index) < TARGET else 0.20
    if r < p_add:
        limit("buy", ap - 1 - int(rng.integers(0, DEPTH)), qty)
    elif r < 2 * p_add:
        limit("sell", bp + 1 + int(rng.integers(0, DEPTH)), qty)
    elif r < 2 * p_add + 0.08:
        book.market_order("buy", qty)
        log.append((1, -1, 0, 0, qty))
    elif r < 2 * p_add + 0.16:
        book.market_order("sell", qty)
        log.append((1, -1, 1, 0, qty))
    elif r < 2 * p_add + 0.18:
        limit("buy", ap + int(rng.integers(0, 3)), qty)
    elif r < 2 * p_add + 0.20:
        limit("sell", bp - int(rng.integers(0, 3)), qty)
    else:
        for _ in range(20):
            if not live:
                break
            j = int(rng.integers(len(live)))
            live[j], live[-1] = live[-1], live[j]
            oid = live.pop()
            if book.cancel(oid):
                log.append((2, oid, 0, 0, 0))
                break

with open("data/events.csv", "w") as f:
    f.write("op,id,side,price,qty\n")
    f.writelines(f"{a},{b},{c},{d},{e}\n" for a, b, c, d, e in log)

counts = [sum(1 for e in log if e[0] == k) for k in range(3)]
print("events:", len(log), " limit:", counts[0], " market:", counts[1], " cancel:", counts[2])
print("resting orders at the end:", len(book.index), " bid levels:", len(book.books["buy"]), " ask levels:", len(book.books["sell"]))
print("best bid", book.best_bid(), " best ask", book.best_ask(), " spread", book.spread())