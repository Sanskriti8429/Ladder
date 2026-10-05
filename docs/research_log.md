# Research log

## Entry 1: Binance best bid/ask feed (04-10-2026)

### Goal
See what real exchange data looks like before building anything on it: which fields arrive, how fast, and how often the price actually moves.

### Setup
`src/ladder/probe.py` connects to the BTCUSDT `bookTicker` websocket stream. It reports the best bid, their sizes, the spread and the size imbalance. A first run printed 10 raw messages. Later runs listened for 30 secs and computed summary statistics.

### Expectation
I expected the price to move in a larger share of messages and I expected a wider spread than one tick.

### Observations

**Message format.** Each message contains an update id `u`, the symbol `s`, the best bid price and size `b`/`B`, and the best ask price and size `a`/`A`. Prices and sizes arrive as strings and need converting to numbers. There is no exchange timestamp, so I can only time messages by when they arrive on my machine. Any latency I measure later will include network delay.

**Message rate.** Two 30 s runs gave about 75 messages per second (2256 messages) and 41 per second (1230 messages). The rate changes a lot between runs, so a recorder cannot assume a fixed rate.

**Price moves versus size changes.** The best bid or ask changed price in 1.7 to 1.8% of messages (41 of 2256 in one run, 21 of 1230 in another). The other 98% only changed the quantity at the best price. So there are roughly 40 size updates for every price move, and the size changes are where any order flow information must be.

**Spread.** The spread was one tick (0.01) in every sample. With the spread already at its minimum, the price can only move by stepping one tick at a time.

**Imbalance.** Defined as (bid size - ask size) / (bid size + ask size), between -1 and +1. Values seen ranged from +0.40 to -0.97. In the second case about 98% of the size at the best level was on the ask.

### Hand calculation
First message from run 1: bid 84598.00 (size 1.33895), ask 84598.01 (size 3.00206).
- mid = (bid + ask) / 2 = 84598.005
- imbalance = (1.33895 - 3.00206) / (1.33895 + 3.00206) = -0.3831
- weighted mid ("microprice") = (bid x ask size + ask x bid size) / (bid size + ask size) = 84598.00308
- check: weighted mid = mid + (spread / 2) x imbalance = 84598.005 + 0.005 x (-0.3831) = 84598.00308

**Interpretation.** The weighted mid is below the mid, close to the bid, because the ask side is larger. Each price is weighted by the size on the opposite side. The bid queue is the smaller one, so it is more likely to be used up first. If that happens the best bid moves down. The weighted mid leans toward the side the price is more likely to move to. It can never differ from the mid by more than half the spread.

### Mistake found and fixed
The first 30 s run reported 2256 messages in 40.1 s (56 per second). The collection loop stopped at 30 s, but I measured elapsed time after the connection closed, and closing took about 10 s. After measuring at the point of stopping, the elapsed time was 30.1 s. This is a reminder to check a measurement against what I expect before trusting it.

### Surprises
- The best price moved in under 2% of messages. Almost all updates only changed the size at the best price.
- The spread was always one tick (0.01), much tighter than I expected.

### Open questions
1. Why does `u` skip numbers? Is the stream only publishing updates that change the best level?
2. When the book is lopsided (for example imbalance near -0.97), does the price move in the heavy side's direction more often than chance?
3. Does the message rate follow a pattern during the day, or is it driven by volatility?
4. If the connection drops, how do I record the gap so a later price-change calculation does not span it?
5. Is the one-tick spread specific to BTCUSDT? Compare with a less liquid pair.

### Next
Turn the probe into a recorder that saves best bid/ask updates with my own arrival timestamp to Parquet files, and logs reconnects and gaps.


## Entry 2: Recorder and reconnect test (05-10-2026)

### Goal
Turn the probe into a recorder that saves best bid/ask updates to Parquet and survives dropped connections, with gaps marked in the data.

### Setup
`src/ladder/record.py` stores one row per message: arrival time in nanoseconds, `segment_id`, update id, bid, bid size, ask, ask size. A 5 s silence watchdog (`asyncio.wait_for` on `recv`) and a reconnect loop wrap the connection. `segment_id` increases by 1 each time the connection fails. `scripts/check.py` and `scripts/segments.py` analyse the saved file.

### Observations

**Message rate.** A 60 s recording gave 2070 rows, about 34 messages per second. Across three runs the rate was about 75, 41 and 34 per second, so it varies by more than 2x between runs.

**Batching.** The median gap between consecutive messages was 0.01 ms (10 microseconds), while the 99th percentile gap was 463 ms. Messages arrive in clumps with quiet stretches between them. Hypothesis: several messages reach the machine together and the loop handles them back to back. Consequence: `arrival_ns` is the time my program handled a message, not the time the exchange sent it, and differences of microseconds inside a clump mean nothing. Use `update_id` to order messages.

**Longest silence.** The maximum gap in the normal 60 s recording was 1.17 s. I set the watchdog to 5 s, about 4x that. This comes from one short sample, so the setting needs rechecking on a longer recording.

**Price moves.** The price changed in 22 of 2069 rows (1.06%), compared with 1.7% in the probe runs. With only 22 events this difference is probably noise. It needs a longer sample.

**Update id jumps.** The median jump between consecutive messages was 3 and the maximum was 131. The rank correlation between time gap and id jump was 0.42. Hypothesis: the id counts book events that this stream does not publish (events that do not change the best bid or ask). The correlation is moderate, so this is supported but not proven. To check against the Binance documentation.

### Reconnect test
I turned the Wi-Fi off during a 90 s recording and back on. I did not time the outage, so I cannot say how much of the gap was the network and how much was the recorder.

Console output:
- `segment 0 ended: TimeoutError` (watchdog fired after silence)
- `segment 1 ended: TimeoutError`, 11 s later

Segment table from `scripts/segments.py`:

┌────────────┬──────┬─────────────────────┬─────────────────────┬───────────┬────────────┐
│ segment_id ┆ rows ┆ start_ns            ┆ end_ns              ┆ gap_s     ┆ duration_s │
│ ---        ┆ ---  ┆ ---                 ┆ ---                 ┆ ---       ┆ ---        │
│ i64        ┆ u32  ┆ i64                 ┆ i64                 ┆ f64       ┆ f64        │
╞════════════╪══════╪═════════════════════╪═════════════════════╪═══════════╪════════════╡
│ 0          ┆ 655  ┆ 1791145243982023472 ┆ 1791145261451815240 ┆ null      ┆ 17.469792  │
│ 2          ┆ 1379 ┆ 1791145289191885985 ┆ 1791145333118011344 ┆ 27.740071 ┆ 43.926125  │
└────────────┴──────┴─────────────────────┴─────────────────────┴───────────┴────────────┘

- Segment 1 has no rows. It was a failed connection attempt that never received data. Hypothesis: the connect call hung until its own timeout (about 10 s), which would explain the 11 s between the two log lines.
- The gap between segments 0 and 2 is 27.7 s. 17.5 + 27.7 + 43.9 = 89.1 s, matching the 90 s duration. So `DURATION` counts wall-clock time including outages, and about 61 s of it was actual data.
- The gap is marked in the data by the change of `segment_id`, so a later calculation can refuse to cross it.

### Why gaps must be marked
A 1-second return computed across a 27 s gap would look like a 1-second move. Order flow sums would miss the flow during the gap. A backtest would appear to trade on a stale book. Keeping segments separate prevents all three.

### Known rough edges
1. `segment_id` increases on failed connection attempts, so ids can skip. It only needs to differ across a gap, but contiguous ids would be cleaner: increment only after a successful connect.
2. The log message says "segment N ended" for a segment that never started. It should distinguish a failed attempt from a stream that ended.
3. All rows are held in memory until the end, so a crash loses everything.
4. Every run overwrites the same file. Filenames need a timestamp.
5. The connection timeout is the library default. A shorter one would retry sooner.

### Open questions
1. What does the Binance documentation say about gaps in `u` on this stream?
2. How much of the 27.7 s gap was network and how much was the recorder? Next test: print a timestamped line on every successful connect, and time the outage with a clock.
3. Is the price-move share really about 1 to 2% of messages, or does it depend on the time of day?

### Next
Flush to disk every few minutes into timestamped files, and make sure buffered rows are saved if the program is stopped with Ctrl+C.


## Entry 3: One-hour recorder run (05-10-2026)

### Goal
Check the recorder over an hour unattended: no lost rows, clean shutdown, and better estimates of message rate, gaps and price-move share than the 60 s samples gave.

### Setup
`src/ladder/record.py` with a 5 min timer flush, a flush on disconnect, atomic writes (temp file then rename), a 5 s silence watchdog, `open_timeout=3`, `close_timeout=1`, and a `session_id`. One run of 61 minutes, stopped with a single Ctrl+C.

### Expectation
I expected the price to move in a larger share of messages than it does, and I expected a wider spread than one tick (from Entry 1). I expected the recorder to survive an hour unattended, but I had not tested it for that long before.

### Results
- 13 Parquet files, 416,113 rows in total. The sum of the printed flush counts equals the rows read back, so nothing was lost.
- One segment, no reconnects, no watchdog timeouts.
- Average rate 113 messages per second. The 5-minute windows ranged from about 80 to 196 per second.
- Price changed in 6,629 of 416,112 messages (1.59%), about 1.8 changes per second.
- Gap between messages: median 13 microseconds, 99th percentile 164 ms, maximum 1.22 s.
- Update id jump: median 2, maximum 260. Rank correlation with the time gap 0.27 (0.42 on the earlier 2,000-row sample).
- Shutdown: one Ctrl+C triggered the final flush (5,873 rows). The traceback is asyncio re-raising `KeyboardInterrupt` after cleanup and does not affect the data.
- Disk: 3.8 MB for the hour (about 9 bytes per row after Parquet compression), so roughly 90 MB per day.

### Interpretation
- The message rate is not stable, so nothing downstream can assume a fixed number of messages per second or per bucket.
- The 1.06% price-move share from the 60 s sample had only 22 events and was noise. 1.6% is the better estimate for this hour.
- The 5 s watchdog is about 4x the longest silence seen in the hour. It is safe for this hour, but the sample is one hour at one time of day.
- Hypothesis (weakened): the update id counts book events that this stream does not publish. The correlation fell from 0.42 to 0.27, so the idea is not confirmed. To check against the Binance documentation.

### Limitations
One hour, one time of day. Top of book only, so no depth features. Arrival time is when my program handled a message, not when the exchange sent it.

### Surprises
- Ctrl+C did not stop the recorder with one press at first. The final flush still ran, and I learned that pressing twice can interrupt it.
- The message rate reached about 196 per second in one 5-minute window, much higher than the 34 to 75 per second in my short samples, so a short sample says little about the rate.
- The price moved in only 1.6% of messages, so almost all of the data is size changes at the best price.

### Open questions
1. Do the message rate and the price-move share change with the time of day?
2. What does the Binance documentation say about gaps in `u` on this stream?
3. How much disk does a day of data use, and when do I need to merge the 5-minute files into daily files?

### Next
Crude end-to-end loop on downloaded trade data (signed volume, hand-written OLS). Restart the recorder so data keeps accumulating.


## Entry 4: One day of Binance trades, signed volume vs next-second price change (2026-10-05)

### Goal
Test the simplest version of the order-flow idea on downloaded trade data: does net aggressive buying in one second predict the price change in the next second?

### Data
`BTCUSDT-trades-2026-10-04.zip` from data.binance.vision, 1,340,109 trades for the UTC day 2026-10-04. The file has no header row. Columns: trade id, price, quantity, quote quantity, time, is_buyer_maker, is_best_match. Time is in microseconds (16 digits), whereas my recorder's `arrival_ns` is in nanoseconds.

### Method
- Sort by (time, trade_id), since several trades share a timestamp.
- Sign each trade: +qty if `is_buyer_maker` is False (aggressive buyer), -qty if True (aggressive seller).
- Bucket into one-second bars: signed volume, last trade price (`close`), trade count.
- Join onto a full grid of all 86,400 seconds. Empty seconds get signed volume 0, and the last price is carried forward.
- Target: `next_change` = close(t+1) - close(t). The final row has no next second and is dropped.

### Expectation
I had no specific expectation going in.

### Results
- 15.5 trades per second on average. My recorder saw about 113 book updates per second on a different day, so book updates outnumber trades by roughly 7 to 1.
- 50.07% of trades have `is_buyer_maker = True` (aggressive seller). Net signed volume over the day was -45.49 BTC, so aggressive sellers outweighed buyers.
- 77,683 of 86,400 seconds had at least one trade, so 10.1% of seconds were empty.
- Check: the per-second trade counts sum to exactly 1,340,109.
- `next_change` (USDT): mean 0.021, std 2.34, min -68.93, max +116.36. 51.2% of seconds have exactly zero change, and the median and both quartiles are 0.
- Check: mean x count is about 1,776, matching the day's move in `close` from 84,753.57 to 86,530.00.

Correlation of signed volume with `next_change`:

shape: (5, 4)
┌────────────┬────────────┬──────────┬──────────┐
│ sec        ┆ signed_vol ┆ close    ┆ n_trades │
│ ---        ┆ ---        ┆ ---      ┆ ---      │
│ i64        ┆ f64        ┆ f64      ┆ u32      │
╞════════════╪════════════╪══════════╪══════════╡
│ 1791072000 ┆ 0.00586    ┆ 84753.57 ┆ 7        │
│ 1791072001 ┆ -0.00322   ┆ 84753.56 ┆ 6        │
│ 1791072002 ┆ 0.00068    ┆ 84753.56 ┆ 2        │
│ 1791072003 ┆ 0.00364    ┆ 84753.57 ┆ 5        │
│ 1791072004 ┆ 0.00591    ┆ 84753.57 ┆ 2        │
└────────────┴────────────┴──────────┴──────────┘
77683 seconds with at least one trade out of 86400
1340109
-45.48524999999998
86400
shape: (2, 5)
┌────────────┬────────────┬─────────┬──────────┬─────────────┐
│ sec        ┆ signed_vol ┆ close   ┆ n_trades ┆ next_change │
│ ---        ┆ ---        ┆ ---     ┆ ---      ┆ ---         │
│ i64        ┆ f64        ┆ f64     ┆ u32      ┆ f64         │
╞════════════╪════════════╪═════════╪══════════╪═════════════╡
│ 1791158398 ┆ -1.96097   ┆ 86530.0 ┆ 151      ┆ 0.0         │
│ 1791158399 ┆ 0.0        ┆ 86530.0 ┆ 0        ┆ null        │
└────────────┴────────────┴─────────┴──────────┴─────────────┘
shape: (9, 2)
┌────────────┬──────────┐
│ statistic  ┆ value    │
│ ---        ┆ ---      │
│ str        ┆ f64      │
╞════════════╪══════════╡
│ count      ┆ 86399.0  │
│ null_count ┆ 0.0      │
│ mean       ┆ 0.020561 │
│ std        ┆ 2.336959 │
│ min        ┆ -68.93   │
│ 25%        ┆ 0.0      │
│ 50%        ┆ 0.0      │
│ 75%        ┆ 0.0      │
│ max        ┆ 116.36   │
└────────────┴──────────┘
share of seconds with zero change: 0.511811479299529
shape: (1, 1)
┌────────────┐
│ signed_vol │
│ ---        │
│ f64        │
╞════════════╡
│ 0.052669   │
└────────────┘
shape: (1, 1)
┌────────────┐
│ signed_vol │
│ ---        │
│ f64        │
╞════════════╡
│ -0.185415  │
└────────────┘
4751
shape: (1, 1)
┌────────────┐
│ signed_vol │
│ ---        │
│ f64        │
╞════════════╡
│ 0.336471   │
└────────────┘
8641
shape: (1, 1)
┌────────────┐
│ signed_vol │
│ ---        │
│ f64        │
╞════════════╡
│ 0.145399   │
└────────────┘

### Interpretation
- The sign of the rank correlation depends on which seconds are included. Over all seconds it is negative, while in high-flow seconds it is positive.
- Hypothesis (not tested directly): `close` is the last trade price, so it bounces between bid and ask. If the last trade in a second was a buy, it executed at the ask, and the next change tends to be down by a tick. Net buying makes a last-trade buy more likely, so this produces a negative rank correlation without any real reversal. A one-tick bounce cannot survive the $1 filter, and the sign flip there is consistent with the explanation.
- The +0.336 conditions on the outcome (big moves), so it overstates what could be predicted in advance. The +0.145 filters on the predictor, which uses only information available before the next second, so it is the fairer number.
- Pearson (+0.053) and Spearman (-0.185) disagree because Pearson is dominated by a few huge moves and Spearman gives a one-tick move the same weight as a $100 move.

### Mistakes caught
- Divided time by 1e3 instead of 1e6, which gives millisecond buckets, not seconds.
- Gave `is_buyer_maker = True` a positive sign, but the buyer being the resting order means the seller was aggressive.
- Signed trade counts (+1/-1) instead of quantities.
- Used a full join instead of a left join when building the grid of seconds.
- Left out the `time` column when naming the columns, which would have shifted every name after it.

### Surprises
The relationship between flow and the next price change was different depending on which seconds I looked at. It was negative over the whole day, positive for the largest-flow seconds, and strongest when I conditioned on big moves.

### Limitations
- One day of data, so nothing here says whether the pattern repeats.
- No standard errors. The overlapping, heavy-tailed, tie-heavy data makes a naive 1/sqrt(n) badly overconfident.
- `close` is the last trade price and contains bid-ask bounce. A mid price from the recorded book would remove it.
- A correlation is not a trading result. There are no costs, latency or fills in any of this.

### Open questions
1. Is -45.49 BTC large relative to total volume traded that day?
2. Do trades with the same timestamp come from one aggressive order that matched several resting orders?
3. Does the result change if I use the mid price from my recorded book data?
4. How large is the uncertainty on +0.145 once autocorrelation is handled (HAC standard errors)?

### Next
Derive the OLS estimator by hand, fit the regression of `next_change` on `signed_vol`, and check it against scikit-learn. Then repeat the analysis using mid price from the recorded data.