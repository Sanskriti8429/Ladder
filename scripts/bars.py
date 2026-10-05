import polars as pl
import numpy as np
from sklearn.linear_model import LinearRegression

COLS= ["trade_id", "price", "qty", "quote_qty","time", "is_buyer_maker", "is_best_match"]
df= pl.read_csv(
    "data/trades/BTCUSDT-trades-2026-10-04.csv",
    has_header= False,
    new_columns= COLS,
)

df= df.sort(["time", "trade_id"])

df = df.with_columns(
    (pl.col("time")// 1_000_000).alias("sec"),
    pl.when(pl.col("is_buyer_maker")).then(-pl.col("qty")).otherwise(pl.col("qty")).alias("signed_qty"),
)

bars=(
    df.group_by("sec")
    .agg(
        pl.col("signed_qty").sum().alias("signed_vol"),
        pl.col("price").last().alias("close"),
        pl.len().alias("n_trades"),
    )
    .sort("sec")
)

print(bars.head())
print(bars.height, "seconds with at least one trade out of 86400")

print(bars["n_trades"].sum())
print(bars["signed_vol"].sum())

first= bars["sec"].min()
grid= pl.DataFrame({"sec": pl.int_range(first, first +86400, eager= True)})

full=(
    grid.join(bars, on="sec", how="left")
    .sort("sec")
    .with_columns(
        pl.col("signed_vol").fill_null(0),
        pl.col("n_trades").fill_null(0),
        pl.col("close").fill_null(strategy="forward"),
    )
    .with_columns((pl.col("close").shift(-1)-pl.col("close")).alias("next_change"))
)

print(full.height)
print(full.tail(2))

full= full.drop_nulls("next_change")
print(full["next_change"].describe())
print("share of seconds with zero change:", (full["next_change"]==0).mean())

print(full.select(pl.corr("signed_vol", "next_change")))
print(full.select(pl.corr("signed_vol", "next_change", method="spearman")))

big = full.filter(pl.col("next_change").abs() >= 1)
print(big.height)
print(big.select(pl.corr("signed_vol", "next_change", method="spearman")))

thr = full["signed_vol"].abs().quantile(0.9)
strong = full.filter(pl.col("signed_vol").abs() >= thr)
print(strong.height)
print(strong.select(pl.corr("signed_vol", "next_change", method="spearman")))

x= full["signed_vol"].to_numpy()
y= full["next_change"].to_numpy()

x_bar= x.mean()
y_bar= y.mean()

b= ((x-x_bar)*(y-y_bar)).sum()/ ((x-x_bar)**2).sum()
a= y_bar- b*x_bar

print("slope b:", b)
print("intercept a:", a)

print("check:", 0.052669*y.std()/x.std())

model= LinearRegression().fit(x.reshape(-1,1),y)
print("sklearn slope:", model.coef_[0])
print("sklearn intercept:", model.intercept_)

n= len(x)
resid= y-(a+b*x)
s2= (resid**2).sum()/(n-2)
se_b= np.sqrt(s2/ ((x-x_bar)**2).sum())
t= b/ se_b

print("naive se(b):", se_b)
print("naive t-stat:", t)