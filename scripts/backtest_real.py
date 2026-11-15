import numpy as np
import polars as pl
from ladder.backtest import trade_pnl

G = ["session_id", "segment_id"]
H = 1_000_000_000
EMBARGO = 30
MAX_AGE = 2_000_000_000

bars = pl.read_parquet("data/bars_1s.parquet").sort("sec")
feats = ["ofi_sum", "imb_last"]
cut = int(len(bars) * 0.7)
train = bars[:cut]
test = bars.filter(pl.col("sec") > train["sec"].max() + EMBARGO)

Xtr, ytr = train.select(feats).to_numpy(), train["y"].to_numpy()
Xte = test.select(feats).to_numpy()
mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
A = np.column_stack([np.ones(len(Xtr)), (Xtr - mu) / sd])
w, *_ = np.linalg.lstsq(A, ytr, rcond=None)
pred_train = A @ w
pred = np.column_stack([np.ones(len(Xte)), (Xte - mu) / sd]) @ w
test_sig = test.select(G + ["sec"]).with_columns(pl.Series("pred", pred))

quotes = (pl.read_parquet("data/btcusdt_2*.parquet")
          .select(G + ["arrival_ns", "bid", "ask"])
          .sort("arrival_ns")
          .with_columns(pl.col("arrival_ns").alias("q_ns")))


def run(sig, lat_ns):
    t0 = (sig["sec"] + 1) * 1_000_000_000
    d = sig.with_columns((t0 + lat_ns).alias("t_in"), (t0 + H + lat_ns).alias("t_out")).sort("t_in")
    d = d.join_asof(quotes.rename({"bid": "eb", "ask": "ea", "q_ns": "q1"}),
                    left_on="t_in", right_on="arrival_ns", by=G, strategy="backward")
    d = d.select(pl.exclude("arrival_ns")).sort("t_out")
    d = d.join_asof(quotes.rename({"bid": "xb", "ask": "xa", "q_ns": "q2"}),
                    left_on="t_out", right_on="arrival_ns", by=G, strategy="backward")
    d = d.drop_nulls(["eb", "ea", "xb", "xa"])
    d = d.filter(((pl.col("t_in") - pl.col("q1")) < MAX_AGE) & ((pl.col("t_out") - pl.col("q2")) < MAX_AGE))
    side = np.sign(d["pred"].to_numpy())
    eb, ea, xb, xa = (d[c].to_numpy() for c in ["eb", "ea", "xb", "xa"])
    gross = np.where(side > 0, xb - ea, eb - xa)
    traded = np.where(side > 0, ea + xb, eb + xa)
    return side, gross, traded, (eb, ea, xb, xa), d["pred"].to_numpy()


side, gross, traded, q, _ = run(test_sig, 1_000_000)
rng = np.random.default_rng(0)
for i in rng.choice(len(side), 200, replace=False):
    s = "buy" if side[i] > 0 else "sell"
    expected = trade_pnl(s, (q[0][i], q[1][i]), (q[2][i], q[3][i]), fee_bps=1.0)
    assert abs((gross[i] - 1e-4 * traded[i]) - expected) < 1e-9
print("vectorised PnL matches trade_pnl on 200 random trades")
print("test bars:", len(test), " average traded value per round trip:", round(traded.mean()))

q90 = np.quantile(np.abs(pred_train), 0.9)
for label, thr in [("every second", 0.0), ("top 10% by |prediction|", q90)]:
    sig = test_sig.filter(pl.col("pred").abs() > thr)
    print(f"\n{label}:")
    for lat_ms in [1, 5, 50, 500]:
        side, gross, traded, q, p = run(sig, lat_ms * 1_000_000)
        mean_gross = gross.mean()
        print(f"  latency {lat_ms:>3} ms: trades {len(gross):>6}  mean |prediction| {np.abs(p).mean():.3f}  "
              f"mean PnL at zero fee {mean_gross:+.4f}  hit rate {(gross > 0).mean():.3f}  "
              f"break-even fee {mean_gross / traded.mean() * 1e4:+.4f} bps  "
              f"mean PnL at 1 bp {(gross - 1e-4 * traded).mean():+.3f}")