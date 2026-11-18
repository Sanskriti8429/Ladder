import json
import sys

import numpy as np

from ladder.orderbook import OrderBook

EVENTS = 10
TARGET = 60
MM_BASE = 10 ** 9
STEPS = 400
SIGMA, K, G = 0.633, 1.92, 1.0
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 5

from dashboard_page import PAGE


class World:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.book = OrderBook()
        self.live = []
        self.next_id = 0
        self.last_mid = 10000.5
        for p in range(9990, 10000):
            self.add("buy", p, int(self.rng.integers(1, 6)))
        for p in range(10001, 10011):
            self.add("sell", p, int(self.rng.integers(1, 6)))

    def add(self, side, price, qty):
        self.book.add_limit(self.next_id, side, price, qty)
        self.live.append(self.next_id)
        self.next_id += 1

    def mid(self):
        return (self.book.best_bid() + self.book.best_ask()) / 2

    def ensure(self):
        buys, sells = self.book.books["buy"], self.book.books["sell"]
        if not buys and not sells:
            c = int(self.last_mid)
            self.add("buy", c, 3)
            self.add("sell", c + 1, 3)
        elif not buys:
            self.add("buy", self.book.best_ask() - 2, 3)
        elif not sells:
            self.add("sell", self.book.best_bid() + 2, 3)
        self.last_mid = self.mid()

    def cancel_random(self):
        for _ in range(20):
            if not self.live:
                return
            j = int(self.rng.integers(len(self.live)))
            self.live[j], self.live[-1] = self.live[-1], self.live[j]
            if self.book.cancel(self.live.pop()):
                return

    def event(self):
        r = self.rng.random()
        qty = int(self.rng.integers(1, 6))
        bp, ap = self.book.best_bid(), self.book.best_ask()
        p_add = 0.30 if len(self.book.index) < TARGET else 0.20
        if r < p_add:
            self.add("buy", ap - 1 - int(self.rng.integers(0, 5)), qty)
        elif r < 2 * p_add:
            self.add("sell", bp + 1 + int(self.rng.integers(0, 5)), qty)
        elif r < 2 * p_add + 0.10:
            return "buy", (bp + ap) / 2, self.book.market_order("buy", qty)
        elif r < 2 * p_add + 0.20:
            return "sell", (bp + ap) / 2, self.book.market_order("sell", qty)
        else:
            self.cancel_random()
        return None


def spread(tau, gamma):
    return gamma * SIGMA ** 2 * tau + (2 / gamma) * np.log(1 + gamma / K)


def top(levels, reverse, n=8):
    return [[p, sum(q for _, q in levels[p])] for p in sorted(levels, reverse=reverse)[:n]]


def main():
    w = World(SEED)
    gamma = G / (SIGMA ** 2 * STEPS)
    q, cash, prev = 0, 0.0, None
    frames = []
    for t in range(STEPS):
        if prev:
            for oid in prev:
                w.book.cancel(oid)
        w.ensure()
        m = w.mid()
        tau = STEPS - t
        r = m - q * gamma * SIGMA ** 2 * tau
        half = spread(tau, gamma) / 2
        bp, ap = w.book.best_bid(), w.book.best_ask()
        bid = min(int(np.floor(r - half)), ap - 1)
        ask = max(int(np.ceil(r + half)), bp + 1)
        if ask <= bid:
            ask = bid + 1
        ids = (MM_BASE + 2 * t, MM_BASE + 2 * t + 1)
        w.book.add_limit(ids[0], "buy", bid, 1)
        w.book.add_limit(ids[1], "sell", ask, 1)
        prev = ids
        fills = []
        for _ in range(EVENTS):
            out = w.event()
            w.ensure()
            if out:
                side, _, hit = out
                for oid, price, qty in hit:
                    if oid >= MM_BASE:
                        if side == "buy":
                            q -= qty
                            cash += price * qty
                            fills.append(["sell", price])
                        else:
                            q += qty
                            cash -= price * qty
                            fills.append(["buy", price])
        mid = w.mid()
        frames.append({
            "mid": mid,
            "bid_quote": bid,
            "ask_quote": ask,
            "q": q,
            "pnl": cash + q * mid,
            "bids": top(w.book.books["buy"], True),
            "asks": top(w.book.books["sell"], False),
            "fills": fills,
        })
    note = f"Avellaneda-Stoikov inventory quotes, g = {G}, sigma {SIGMA}, k {K}, one unit per side, reposted every step, seed {SEED}. Synthetic book from Entry 26."
    page = PAGE.replace("__DATA__", json.dumps({"note": note, "frames": frames}, separators=(",", ":")))
    with open("docs/replay.html", "w") as f:
        f.write(page)
    total = sum(len(f["fills"]) for f in frames)
    print("frames:", len(frames), " fills:", total, " final inventory:", q,
          " max |q|:", max(abs(f["q"]) for f in frames),
          " final PnL:", round(frames[-1]["pnl"], 1), " file bytes:", len(page))


if __name__ == "__main__":
    main()