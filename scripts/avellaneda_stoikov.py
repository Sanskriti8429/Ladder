import numpy as np

N, T, DT = 5000, 1.0, 0.005
S0, SIGMA, GAMMA, K, A = 100.0, 2.0, 0.1, 1.5, 140.0
steps = int(T / DT)


def spread(tau):
    return GAMMA * SIGMA ** 2 * tau + (2 / GAMMA) * np.log(1 + GAMMA / K)


avg_spread = np.mean([spread(T - i * DT) for i in range(steps)])


def run(strategy):
    rng = np.random.default_rng(3)
    s = np.full(N, S0)
    q = np.zeros(N)
    cash = np.zeros(N)
    for i in range(steps):
        tau = T - i * DT
        if strategy == "inventory":
            r = s - q * GAMMA * SIGMA ** 2 * tau
            half = spread(tau) / 2
        else:
            r = s
            half = avg_spread / 2
        bid, ask = r - half, r + half
        db, da = np.maximum(s - bid, 0), np.maximum(ask - s, 0)
        hit_ask = rng.random(N) < A * np.exp(-K * da) * DT
        hit_bid = rng.random(N) < A * np.exp(-K * db) * DT
        cash += np.where(hit_ask, ask, 0) - np.where(hit_bid, bid, 0)
        q += hit_bid.astype(float) - hit_ask.astype(float)
        s = s + SIGMA * np.sqrt(DT) * rng.standard_normal(N)
    return cash + q * s, q


print(f"time-averaged optimal spread: {avg_spread:.3f}   spread at the start {spread(T):.3f}   at the end {spread(DT):.3f}")
for name in ["inventory", "symmetric"]:
    pnl, q = run(name)
    print(f"{name:<10} profit mean {pnl.mean():7.2f}  std {pnl.std():6.2f}   "
          f"final inventory mean {q.mean():+.2f}  std {q.std():5.2f}  max abs {np.abs(q).max():.0f}")