import numpy as np
from scipy.signal import lfilter

BETA, S0, PHI = 0.05, 0.2, 0.18
N, REPS = 70_000, 300
rng = np.random.default_rng(1)


def simulate(n):
    innov = rng.laplace(scale=1 / np.sqrt(2), size=n)
    ofi = lfilter([np.sqrt(1 - PHI ** 2)], [1, -PHI], innov)
    x = ofi[:-1]
    noise = S0 * (1 + 0.5 * np.abs(x)) * rng.standard_normal(n - 1)
    y = BETA * x + noise
    return x, y


def fit(x, y, L=10):
    n = len(x)
    d = x - x.mean()
    sxx = (d ** 2).sum()
    b = (d * (y - y.mean())).sum() / sxx
    e = (y - y.mean()) - b * d
    u = e * d
    naive = np.sqrt((e ** 2).sum() / (n - 2) / sxx)
    s = (u ** 2).sum()
    white = np.sqrt(s) / sxx
    for k in range(1, L + 1):
        s += 2 * (1 - k / (L + 1)) * (u[k:] * u[:-k]).sum()
    hac = np.sqrt(s) / sxx
    return b, naive, white, hac


res = np.array([fit(*simulate(N)) for _ in range(REPS)])
b, se = res[:, 0], res[:, 1:]
names = ["naive", "White", "HAC(10)"]

print(f"true beta {BETA}   mean estimate {b.mean():.5f}   bias {b.mean() - BETA:+.5f}")
print(f"spread of the estimate across {REPS} simulations (the true standard error): {b.std():.5f}")
for i, name in enumerate(names):
    cover = (np.abs(b - BETA) <= 1.96 * se[:, i]).mean()
    print(f"{name:<8} average se {se[:, i].mean():.5f}   95% interval contains the truth {100 * cover:.1f}% of the time")

x, y = simulate(N)
print("R^2 of one simulated dataset:", round(np.corrcoef(x, y)[0, 1] ** 2, 4))