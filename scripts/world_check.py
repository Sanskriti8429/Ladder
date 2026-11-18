import numpy as np
from ladder.orderbook import OrderBook

EVENTS = 10
TARGET = 60
HORIZONS = [1, 5, 20, 100, 400]
STEPS = 6000
PATHS = 8


class FWorld:
    def __init__(self, seed, sigma_f, phi):
        self.rng = np.random.default_rng(seed)
        self.sigma_f = sigma_f
        self.phi = phi
        self.f = 10000.5
        self.inc = 0.0
        self.book = OrderBook()
        self.live = []
        self.next_id = 0
        self.last_mid = 10000.5
        for p in range(9990, 10001):
            self.add("buy", p, int(self.rng.integers(1, 6)))
        for p in range(10001, 10012):
            self.add("sell", p, int(self.rng.integers(1, 6)))

    def add(self, side, price, qty):
        self.book.add_limit(self.next_id, side, price, qty)
        self.live.append(self.next_id)
        self.next_id += 1

    def mid(self):
        return (self.book.best_bid() + self.book.best_ask()) / 2

    def move(self):
        shock = np.sqrt(1 - self.phi ** 2) * self.sigma_f * self.rng.standard_normal()
        self.inc = self.phi * self.inc + shock
        self.f += self.inc

    def ensure(self):
        buys, sells = self.book.books["buy"], self.book.books["sell"]
        if not buys and not sells:
            c = int(np.floor(self.f))
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
        base = int(np.floor(self.f))
        p_add = 0.30 if len(self.book.index) < TARGET else 0.20
        if r < p_add:
            self.add("buy", base - int(self.rng.integers(0, 5)), qty)
        elif r < 2 * p_add:
            self.add("sell", base + 1 + int(self.rng.integers(0, 5)), qty)
        elif r < 2 * p_add + 0.10:
            self.book.market_order("buy", qty)
        elif r < 2 * p_add + 0.20:
            self.book.market_order("sell", qty)
        else:
            self.cancel_random()


def simulate(seed, sigma_f, phi):
    w = FWorld(seed, sigma_f, phi)
    mid = [w.mid()]
    fund = [w.f]
    spreads = []
    for _ in range(STEPS):
        w.move()
        for _ in range(EVENTS):
            w.event()
            w.ensure()
        mid.append(w.mid())
        fund.append(w.f)
        spreads.append(w.book.best_ask() - w.book.best_bid())
    return np.array(mid), np.array(fund), float(np.mean(spreads)), len(w.book.index)


def ratios(series):
    v1 = np.concatenate([s[1:] - s[:-1] for s in series]).var()
    if v1 == 0:
        return 0.0, [float("nan")] * len(HORIZONS)
    out = []
    for h in HORIZONS:
        v = np.concatenate([s[h:] - s[:-h] for s in series]).var()
        out.append(v / (h * v1))
    return float(np.sqrt(v1)), out


print("variance ratio of the mid and of the latent fundamental at h =", HORIZONS)
for sigma_f, phi in [(0.0, 0.0), (0.5, 0.0), (1.0, 0.0), (2.0, 0.0), (4.0, 0.0), (2.0, 0.25)]:
    runs = [simulate(s, sigma_f, phi) for s in range(PATHS)]
    sd_m, rm = ratios([r[0] for r in runs])
    sd_f, rf = ratios([r[1] for r in runs])
    spread = np.mean([r[2] for r in runs])
    resting = np.mean([r[3] for r in runs])
    print(f"\nsigma_f {sigma_f:.1f}  phi {phi:.2f}  mid step std {sd_m:.3f}  mean spread {spread:.2f} ticks  resting orders at the end {resting:.0f}")
    print("  mid         " + "  ".join(f"{x:6.3f}" for x in rm))
    print("  fundamental " + "  ".join(f"{x:6.3f}" for x in rf))