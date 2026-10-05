import polars as pl

COLS= ["trade_id", "price", "qty", "quote_qty","time", "is_buyer_maker", "is_best_match"]

df= pl.read_csv(
    "data/trades/BTCUSDT-trades-2026-10-04.csv",
    has_header= False,
    new_columns= COLS,
)

print(df.shape)
print(df.head())
print(df.schema)

print(df["is_buyer_maker"].mean())
print(df["time"].min(), df["time"].max())
print(df.height/86400)