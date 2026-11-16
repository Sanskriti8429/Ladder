import time
import numpy as np
from ladder.orderbook import OrderBook

EVENTS = 10
TARGET = 60
MM_BASE = 10 ** 9
CAL_STEPS, STEPS, PATHS = 10_000, 1_500, 200


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


def calibrate(steps, seed):
    w = World(seed)
    mids = [w.mid()]
    hits = []
    for _ in range(steps):
        for _ in range(EVENTS):
            out = w.event()
            w.ensure()
            if out:
                side, m, fills = out
                for _, price, _ in fills:
                    hits.append(price - m if side == "buy" else m - price)
        mids.append(w.mid())
    sigma = float(np.std(np.diff(mids)))
    d = np.array(hits)
    grid = np.array([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5])
    counts = np.array([(d >= x).sum() for x in grid])
    rate = counts / (2 * steps)
    print(f"calibration run: {steps} steps, resting orders at the end {len(w.book.index)}, sigma {sigma:.3f} ticks per sqrt(step)")
    print("  delta (ticks)   count   rate per step per side")
    for x, c, r in zip(grid, counts, rate):
        print(f"  {x:8.1f} {c:12d} {r:12.4f}")
    use = counts >= 30
    slope, icpt = np.polyfit(grid[use], np.log(rate[use]), 1)
    y = np.log(rate[use])
    fit = icpt + slope * grid[use]
    r2 = 1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"  exponential fit on {int(use.sum())} points: A = {np.exp(icpt):.4f} per step, k = {-slope:.4f} per tick, R^2 {r2:.3f}")
    return sigma, float(-slope)


def spread(tau, gamma, sigma, k):
    return gamma * sigma ** 2 * tau + (2 / gamma) * np.log(1 + gamma / k)


def run_mm(kind, g, sigma, k, seed, avg_half):
    w = World(seed)
    gamma = g / (sigma ** 2 * STEPS)
    q, cash = 0, 0.0
    mids = np.empty(STEPS + 1)
    mids[0] = w.mid()
    qs = np.empty(STEPS)
    fills = []
    prev = None
    for t in range(STEPS):
        if prev:
            for oid in prev:
                w.book.cancel(oid)
        w.ensure()
        m = w.mid()
        tau = STEPS - t
        if kind == "inventory":
            r = m - q * gamma * sigma ** 2 * tau
            half = spread(tau, gamma, sigma, k) / 2
        else:
            r, half = m, avg_half
        bp, ap = w.book.best_bid(), w.book.best_ask()
        bid = min(int(np.floor(r - half)), ap - 1)
        ask = max(int(np.ceil(r + half)), bp + 1)
        if ask <= bid:
            ask = bid + 1
        ids = (MM_BASE + 2 * t, MM_BASE + 2 * t + 1)
        w.book.add_limit(ids[0], "buy", bid, 1)
        w.book.add_limit(ids[1], "sell", ask, 1)
        prev = ids
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
                            fills.append((t, -1))
                        else:
                            q += qty
                            cash -= price * qty
                            fills.append((t, 1))
        mids[t + 1] = w.mid()
        qs[t] = q
    pnl = cash + q * mids[-1]
    after = [s * (mids[t + 2] - mids[t + 1]) for t, s in fills if t + 2 <= STEPS]
    during = [s * (mids[t + 1] - mids[t]) for t, s in fills]
    return pnl, q, np.abs(qs).mean(), np.abs(qs).max(), len(fills), after, during


sigma, k = calibrate(CAL_STEPS, 1000)
assert k > 0
gamma_ref = 1 / (sigma ** 2 * STEPS)
avg_half = float(np.mean([spread(STEPS - t, gamma_ref, sigma, k) / 2 for t in range(STEPS)]))
print(f"\nsymmetric half-spread (time average of the optimal one at g = 1): {avg_half:.3f} ticks\n")

for name, kind, g in [("symmetric", "symmetric", 1.0), ("inventory g=0.5", "inventory", 0.5),
                      ("inventory g=1", "inventory", 1.0), ("inventory g=2", "inventory", 2.0)]:
    start = time.time()
    res = [run_mm(kind, g, sigma, k, s, avg_half) for s in range(PATHS)]
    pnl = np.array([r[0] for r in res])
    qf = np.array([r[1] for r in res])
    mabs = np.array([r[2] for r in res])
    mx = np.array([r[3] for r in res])
    nf = np.array([r[4] for r in res])
    after = np.array([x for r in res for x in r[5]])
    during = np.array([x for r in res for x in r[6]])
    print(f"{name:<16} profit {pnl.mean():8.1f} (se {pnl.std(ddof=1) / np.sqrt(PATHS):5.1f}) std {pnl.std(ddof=1):7.1f} | "
          f"final inventory mean {qf.mean():+6.1f} std {qf.std(ddof=1):6.1f} | mean |q| {mabs.mean():5.1f} max |q| {mx.max():4.0f} | "
          f"fills per path {nf.mean():6.1f}")
    print(f"{'':<16} mid move after a fill (+ = good for us): {after.mean():+.3f} (n {len(after)});  "
          f"within the fill step: {during.mean():+.3f}   [{time.time() - start:.0f} s]")