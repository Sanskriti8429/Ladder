import numpy as np
from scipy.stats import spearmanr
from ladder.orderbook import OrderBook
from ladder.features import ofi, imbalance

rng = np.random.default_rng(7)
STEPS, EVENTS = 20_000, 10

book = OrderBook()
live = []
next_id = 0


def add(side, price, qty):
    global next_id
    book.add_limit(next_id, side, price, qty)
    live.append(next_id)
    next_id += 1


for p in range(9990, 10000):
    add("buy", p, int(rng.integers(1, 6)))
for p in range(10001, 10011):
    add("sell", p, int(rng.integers(1, 6)))


def top():
    bp, ap = book.best_bid(), book.best_ask()
    bq = sum(q for _, q in book.books["buy"][bp])
    aq = sum(q for _, q in book.books["sell"][ap])
    return (bp, bq, ap, aq)


def ensure():
    if not book.books["buy"]:
        add("buy", book.best_ask() - 2, 3)
    elif not book.books["sell"]:
        add("sell", book.best_bid() + 2, 3)


def one_event():
    r = rng.random()
    qty = int(rng.integers(1, 6))
    bp, ap = book.best_bid(), book.best_ask()
    if r < 0.25:
        add("buy", ap - 1 - int(rng.integers(0, 5)), qty)
    elif r < 0.50:
        add("sell", bp + 1 + int(rng.integers(0, 5)), qty)
    elif r < 0.60:
        book.market_order("buy", qty)
    elif r < 0.70:
        book.market_order("sell", qty)
    elif live:
        i = int(rng.integers(len(live)))
        live[i], live[-1] = live[-1], live[i]
        book.cancel(live.pop())


def ols(x, y):
    d = x - x.mean()
    sxx = (d ** 2).sum()
    b = (d * (y - y.mean())).sum() / sxx
    e = (y - y.mean()) - b * d
    se = np.sqrt(((d * e) ** 2).sum()) / sxx
    return b, b / se, np.corrcoef(x, y)[0, 1] ** 2


rows = []
prev = top()
for _ in range(STEPS):
    ofi_sum = 0.0
    for _ in range(EVENTS):
        one_event()
        ensure()
        new = top()
        ofi_sum += ofi(prev, new)
        prev = new
    bp, bq, ap, aq = prev
    assert bp < ap, "the simulated book is crossed"
    rows.append((ofi_sum, (bp + ap) / 2, imbalance(bq, aq), ap - bp))

a = np.array(rows)
ofi_s, mid, imb, spread = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
dmid = np.diff(mid)

print("steps:", STEPS, " events:", STEPS * EVENTS, " resting orders at the end:", len(book.index))
print("mean spread (ticks):", round(spread.mean(), 2), " share of steps with no mid change:", round((dmid == 0).mean(), 3))

b, t, r2 = ols(ofi_s[1:], dmid)
print(f"same step, OFI -> mid change:      slope {b:.4f}  t {t:.1f}  R^2 {r2:.4f}")
b, t, r2 = ols(ofi_s[:-1], dmid)
rho = spearmanr(ofi_s[:-1], dmid)[0]
print(f"next step, OFI -> mid change:      slope {b:.4f}  t {t:.1f}  R^2 {r2:.4f}  Spearman {rho:.3f}")
b, t, r2 = ols(imb[:-1], dmid)
rho = spearmanr(imb[:-1], dmid)[0]
print(f"next step, imbalance -> mid change: slope {b:.4f}  t {t:.1f}  R^2 {r2:.4f}  Spearman {rho:.3f}")