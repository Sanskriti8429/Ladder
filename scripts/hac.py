import numpy as np
import polars as pl
import statsmodels.api as sm

bars = pl.read_parquet("data/bars_1s.parquet").sort("sec")
x = bars["ofi_sum"].to_numpy()
y = bars["y"].to_numpy()
n = len(x)

d = x - x.mean()
b = (d * (y - y.mean())).sum() / (d ** 2).sum()
e = (y - y.mean()) - b * d
sxx = (d ** 2).sum()
u = e * d


def hac_se(u, sxx, L):
    s = (u ** 2).sum()
    for k in range(1, L + 1):
        w = 1 - k / (L + 1)
        s += 2 * w * (u[k:] * u[:-k]).sum()
    return np.sqrt(s) / sxx


naive = np.sqrt((e ** 2).sum() / (n - 2) / sxx)
print("slope:", round(b, 5), " naive se:", round(naive, 5), " White se (L=0):", round(hac_se(u, sxx, 0), 5))
for L in [1, 5, 10, 30, 60]:
    print(f"HAC L={L:>2}: se {hac_se(u, sxx, L):.5f}   t = {b / hac_se(u, sxx, L):.2f}")

X = sm.add_constant(x)
fit = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 10, "use_correction": False})
print("statsmodels HAC L=10:", round(fit.bse[1], 5))