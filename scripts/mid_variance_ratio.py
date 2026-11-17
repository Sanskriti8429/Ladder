import numpy as np
from make_dashboard import World, EVENTS

HORIZONS = [1, 5, 20, 100, 400]
STEPS = 4000
PATHS = 20

changes = {h: [] for h in HORIZONS}
for seed in range(PATHS):
    w = World(seed)
    mid = [w.mid()]
    for _ in range(STEPS):
        for _ in range(EVENTS):
            w.event()
            w.ensure()
        mid.append(w.mid())
    mid = np.array(mid)
    for h in HORIZONS:
        changes[h].append(mid[h:] - mid[:-h])

v1 = np.concatenate(changes[1]).var()
print("one-step variance:", round(v1, 4), " std:", round(v1 ** 0.5, 4))
for h in HORIZONS:
    v = np.concatenate(changes[h]).var()
    print(f"h = {h:>3}: variance {v:8.3f}   variance ratio {v / (h * v1):.3f}")