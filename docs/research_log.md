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
```
┌────────────┬──────┬─────────────────────┬─────────────────────┬───────────┬────────────┐
│ segment_id ┆ rows ┆ start_ns            ┆ end_ns              ┆ gap_s     ┆ duration_s │
│ ---        ┆ ---  ┆ ---                 ┆ ---                 ┆ ---       ┆ ---        │
│ i64        ┆ u32  ┆ i64                 ┆ i64                 ┆ f64       ┆ f64        │
╞════════════╪══════╪═════════════════════╪═════════════════════╪═══════════╪════════════╡
│ 0          ┆ 655  ┆ 1791145243982023472 ┆ 1791145261451815240 ┆ null      ┆ 17.469792  │
│ 2          ┆ 1379 ┆ 1791145289191885985 ┆ 1791145333118011344 ┆ 27.740071 ┆ 43.926125  │
└────────────┴──────┴─────────────────────┴─────────────────────┴───────────┴────────────┘
```
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


## Entry 4: One day of Binance trades, signed volume vs next-second price change (05-10-2026)

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
- OLS of next_change on signed_vol (hand-written from the derivation): slope 0.1728, intercept 0.0207. Matches scikit-learn to 15 significant digits. r^2 is about 0.3%, so the line explains very little of the variance.
- Naive standard error of the slope: 0.0111, t = 15.5. This equals the t-stat implied by the correlation (r * sqrt(n-2) / sqrt(1-r^2)), which is how I caught an operator-precedence bug (`/n-2` instead of `/(n-2)`) that had given 19.5.
- Lag-1 autocorrelation: signed volume +0.037, residuals +0.073. By a rough variance-inflation rule these alone raise the standard error by under 1%, so autocorrelation at lag 1 is not the main problem. Heteroskedasticity is the next suspect.
- Heteroskedasticity-robust (White) standard error of the slope: 0.0481, t = 3.59, against the naive 0.0111 and t = 15.5. The naive standard error was understated by about 4.3x. Hypothesis (untested): residual variance is larger in high-flow seconds.
- Hand-written robust (White/HC0) standard error 0.048113 matches statsmodels `cov_type="HC0"` to about 15 digits.

Correlation of signed volume with `next_change`:

| Sample                            | Seconds | Spearman | Pearson      |
|-----------------------------------|---------|----------|--------------|
| All seconds                       | 86,399  | -0.185   | +0.053       |
| Next move at least $1             | 4,751   | +0.336   | not computed |
| Top 10% of absolute signed volume | 8,641   | +0.145   | not computed |

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
- Standard errors are naive (t = 15.5) and heteroskedasticity-robust (t = 3.6). HAC (Newey-West) errors are not computed yet, and the correlations in the table have no error bars.
- `close` is the last trade price and contains bid-ask bounce. A mid price from the recorded book would remove it.
- A correlation is not a trading result. There are no costs, latency or fills in any of this.

### Open questions
1. Is -45.49 BTC large relative to total volume traded that day?
2. Do trades with the same timestamp come from one aggressive order that matched several resting orders?
3. Does the result change if I use the mid price from my recorded book data?
4. How large is the uncertainty on +0.145 once autocorrelation is handled (HAC standard errors)?

### Next
Repeat the analysis with the mid price from the recorded book data (no bid-ask bounce), compute HAC standard errors, and test whether residual variance rises with flow.

## Entry 5: Order book and matching engine (06-10-2026)

### Goal
Build a limit order book with price-time priority, tested enough to trust as the base for the backtester.

### What exists
`src/ladder/orderbook.py`: two sides (bids and asks), each a dictionary of price level to a FIFO queue of resting orders. Features: limit orders that match on arrival (via a shared `_match` routine), market orders, cancel by order id, best bid, best ask and spread. Trades execute at the resting order's price. Any unfilled part of a limit order rests at its own limit price. The unfilled part of a market order is discarded.

### Tests
12 tests, all passing. Ten are hand-written examples (time priority, multi-level sweeps, cancel of filled and resting orders, both sides, a market order bigger than the book, crossing and partly filled limit orders, best bid/ask/spread, a limit order at exactly the resting price). Two are property tests with hypothesis: the book is never crossed, and quantity is conserved (submitted = resting + 2 x filled).

### Test of the tests
I planted a bug on purpose (`>` changed to `>=` in the limit-price check). Only the never-crossed property failed, and hypothesis shrank the failure to two orders: sell 1 at 90, then buy 1 at 90. None of my hand-written tests covered equal prices, and the conservation property stayed green because the bug moves quantity into the book rather than losing it. The shrunk case is now a permanent unit test.

### Mistakes caught along the way
- `side` was ignored in the first version, so bids were stored as asks. The bid-side test returned the wrong fills without any error.
- Operator precedence and function-vs-call slips (`return max` instead of `max(levels)`, `self.best_ask` without brackets).
- `assert ask - bid` passes for any nonzero value, so it would have hidden a crossed book. The check has to be `bid < ask`.

### Known limitations
- Prices are plain integers in the tests, but nothing enforces integer ticks.
- No validation: duplicate order ids, zero or negative quantities are not rejected, and the property tests never generate them.
- `best_bid` and `best_ask` scan all price levels, which is fine here but will show up in the C++ benchmarks.
- No order modify, no self-trade handling, no order types beyond limit and market.

### Next
Book reconstruction from snapshots and deltas, which needs a depth feed, not the best bid/ask stream I recorded so far.

## Entry 6: Recorded top-of-book data, and the depth stream (02-11-2026)

### Goal
Summarise what the recorder has collected so far, and learn the format and rules of Binance's depth feed before building a full order book from it.

### Part 1: What the recorder has collected

**Data.** 7,470,790 rows in 22 segments across 4 program runs (4 session ids), about 19.5 hours of recording in total. Segments last from 29 s to 2.4 h. The one-hour test run holds 416,113 rows, and the three later runs hold the rest.

**Gaps.**
- Between runs: 547 s (about 9 min), 311,167 s (3.6 days) and 103,806 s (28.8 h). These are separate program runs and not reconnects.
- Inside runs: 18 gaps. Four are under 10 s, which fits a short network drop plus the reconnect delay. The other 14 range from about a minute to about an hour (longest 3,679 s).

**Hypothesis (not verified):** the longer gaps inside runs come from the laptop sleeping and suspending the recorder, not from the network. The only evidence so far is one stretch of console output (10:06:53 to 10:20:03) where two expected 5-minute flush lines never printed, which is what a suspended program would look like. To test it, turn sleep off while plugged in and see whether the long gaps stop.

**Consequence for analysis.** Every calculation must be done within (session_id, segment_id). A `.diff()` over the combined data would treat the 3.6-day gap as one message interval. `scripts/segments.py` now groups by both columns. `scripts/check.py` still needs the same change.

### Part 2: The depth stream

**Recipe (from the Binance documentation).** Open the diff depth stream and buffer its events, fetch a REST snapshot, drop events older than the snapshot, then apply events in order. Each event's first update id `U` must equal the previous event's last id `u` plus 1, and if the chain breaks the book must be rebuilt from a new snapshot. Each event carries absolute quantities per price level, and a quantity of 0 removes the level. An event that removes a level the local book never had is normal. I could not confirm the exact spot rule for the first event after the snapshot (the futures docs say `u >= lastUpdateId`; I believe spot uses `lastUpdateId + 1`), so this needs checking against the current spot documentation.

**Event format (three real messages).** Fields: `e` (event type), `E` (exchange event time, milliseconds), `s` (symbol), `U` and `u` (first and last update id), `b` and `a` (lists of `[price, quantity]` string pairs). Prices and quantities are strings with 8 decimals. The `E` values were 100 ms apart. Each event holds only the levels that changed, including levels far from the market (one bid update was about 10% below the best bid).

**Chain check, 30 s of live data.** 294 events in 30.1 s (9.8 per second, consistent with the 100 ms stream), 0 chain breaks, average 21.3 levels per event.

**Snapshot (limit 1000).** `lastUpdateId` 102,226,903,765, the same scale as the event ids. 1,000 bids and 1,000 asks, best price first in both lists. Best bid 76,632.00, best ask 76,632.01. The 1,000th bid is $215.44 (0.28%) below the best bid and the 1,000th ask is $284.56 (0.37%) above the best ask, so the snapshot only covers a thin band around the price.

**Three timestamp units in this project.** Trades files use microseconds, the depth event time `E` uses milliseconds, and the recorder's `arrival_ns` uses nanoseconds. Convert before comparing any two of them.


### Interpretation
- A depth book is level-aggregated, meaning price to total quantity, so my order-by-order matching engine cannot consume it. The two books do different jobs: the depth book reproduces what the exchange showed, and the matching engine simulates my own orders in the backtester.
- Because the snapshot covers only about 0.3% around the price, a local book is complete near the market and sparse far from it. Features that use the top few levels are safe, but a long session needs fresh snapshots as the price drifts.
- `E` is an exchange timestamp, so `arrival_ns` minus `E` gives a rough latency estimate. My clock and Binance's are not synchronised, so this is approximate until I measure the offset.
- Hypothesis (not tested): `bookTicker` ids skipped numbers while depth ids chain without gaps because `bookTicker` only publishes changes that touch the top of the book.
- This feed cannot show anything faster than 100 ms, which limits the shortest horizon in the project.

### Limitations
- The depth probes are 30 s samples, so the 0 chain breaks says little about long sessions or busy periods.
- The recorded top-of-book data covers about 19.5 hours across 4 runs, with gaps. It has no depth.
- The first-event rule after the snapshot is unconfirmed for spot.

### Open questions
1. What exactly is the spot rule for the first event after the snapshot?
2. Do the long gaps inside runs come from the laptop sleeping?
3. How large is the offset between my clock and the exchange's `E` time?
4. How much disk does a day of raw depth events need, and should the recorder save raw JSON or parsed rows?

### Next
Write a `DepthBook` class (price to quantity per side, integer ticks) test-first, then a depth recorder that saves raw events and snapshots with session and segment ids, then replay the raw events and compare the rebuilt best bid and ask with the `bookTicker` feed recorded over the same time.

## Entry 7: Depth book reconstruction and replay check (08-11-2026)

### Goal
Rebuild Binance's order book from the diff depth stream plus a REST snapshot, and verify it against an independent feed.

### What exists
- `src/ladder/depthbook.py`: price (integer ticks) to quantity per side. A snapshot sets the book. An event sets absolute quantities, and a quantity of 0 removes the level. A stale event (last id at or below the book's) is ignored, an overlapping event is applied, and an event that starts after the book's id plus 1 raises `ChainBreak` before touching the book. `sync(snapshot, buffered_events)` combines a snapshot with events buffered during the REST call.
- `src/ladder/depth_record.py`: saves raw event JSON and raw snapshots with session and segment ids, flushing every 5 minutes, with a new segment and a fresh snapshot after any disconnect or `ChainBreak`.
- `src/ladder/live_sync.py`: 30 s live check of the sync procedure.
- `scripts/replay_check.py`: rebuilds the book from the saved raw events and compares the top of book with `bookTicker`.
- 17 passing tests, including a gap test, a stale-and-overlap test and two sync tests.

### Spot rule (confirmed from the current docs)
Events whose last id is at or below the snapshot's `lastUpdateId` are discarded. After that, an event is applied unless its first id is greater than the book's id plus 1, which means events were missed and the book must be rebuilt. Overlap is allowed because quantities are absolute. This corrected my first version, which used a strict equality check that would have rejected valid events.

### Results
- Live sync: 3 to 5 events buffered during the snapshot download, no chain break in 30 s, quantities and prices changing as expected.
- Replay check over about 26 minutes recorded at the same time as `bookTicker`: 15,629 events rebuilt, 15,576 compared. Best bid and ask matched on 100% of events and sizes on 100%, with 0 mismatches.
- A first run showed 51 size mismatches. They were all in the last 5 seconds, because I stopped the `bookTicker` recorder about 5 s before the depth recorder. The ticker values were frozen at its last row. Comparing only up to the last ticker id removed them.
- Disk: about 75 bytes per event after Parquet compression, so roughly 65 MB per day at 10 events per second (rough, from a 2-minute test).

### Mistakes caught
- `asyncio.block` does not exist (the function is `asyncio.to_thread`).
- A leftover `save = False` line meant events were saved but never applied, so the chain check would never have run.
- The recorder's exception list needed `ChainBreak`.
- My first hypothesis for the mismatches (one-update lag between feeds) was wrong. The ticker rows ended before the mismatches began.

### Interpretation
- The shared update id counter between `bookTicker` and the depth stream is confirmed, since the join only works if both use one counter. It also explains the skipped ids in `bookTicker`: it only emits a row when the top of the book changes.
- Raw JSON storage is cheap enough to keep, so the book logic can be fixed and replayed.

### Expectation
I expected the rebuilt best bid and ask to match `bookTicker` on nearly every event, with a few disagreements from timing differences between the two feeds. I expected the live sync to need only a handful of buffered events, and I expected the spot rule for the first event after the snapshot to be the strict one I had already coded.

### Surprises
- The spot rule is looser than the one I coded: overlapping events are allowed, and a break only means the first id is greater than the book's id plus 1. My strict equality check would have rejected valid events.
- The 51 size mismatches turned out to come from my own recording, not from the book. I stopped the `bookTicker` recorder about 5 seconds before the depth recorder, so the ticker values were frozen at its last row.
- My timing-lag explanation for the mismatches was wrong. The ticker rows ended before the first mismatch.
- The `bookTicker` and depth streams share one update id counter, and that is what makes the replay check possible at all.

### Limitations
- 26 minutes, one segment, no live resync exercised.
- The replay compares the top of the book only.
- Both feeds come from the same exchange, so this checks my code, not the exchange.

### Open questions
1. What happens to the check across a deliberate Wi-Fi drop during depth recording?
2. How far does the 1000-level snapshot window drift out of date over several hours?
3. How large is the offset between my clock and the exchange's `E` time?

### Next
Features computed from the book: order flow imbalance, multi-depth imbalance and microprice.

## Entry 8: OFI replication on recorded top-of-book data (09-11-2026)

### Goal
Replicate the central result of Cont, Kukanov and Stoikov (2014): over a fixed interval, the change in mid price is roughly linear in order flow imbalance (OFI). Then test whether OFI predicts the next interval.

### Method
- OFI per update from the best bid and ask: +new bid size if the bid price rose or stayed, -old bid size if it fell or stayed, -new ask size if the ask fell or stayed, +old ask size if it rose or stayed. The vectorised version matches the scalar function on 2,000 random rows.
- Computed within (session_id, segment_id) and ordered by update id, so no pair crosses a gap.
- One-second bars: summed OFI, last mid price, mid change from the previous second. Only seconds that directly follow another second are used, so 69,192 seconds from 7.5 million updates.

### Results
- OFI per update: median -0.00006 BTC, middle half within +/-0.0005, standard deviation 0.31 (min -31.3, max +49.3). Most of the variance comes from rare large values.
- Same-second regression of mid change on OFI: slope 0.180 dollars per BTC, R^2 = 0.628.
- Next-second regression: slope 0.041, R^2 = 0.033, Spearman +0.268.
- Without the top 1% of |OFI|, next-second R^2 = 0.031, so the result is not driven by extreme seconds.
- For comparison, signed trade volume (Entry 4) explained 0.3% of the next second's change, with last-trade prices that contain bid-ask bounce.

### Interpretation
- The mechanism holds: order flow at the top of the book accounts for most of the same-second mid price movement. This is partly mechanical, because OFI includes the full queue size when the best price moves, so a large OFI and a mid move are partly the same event.
- OFI has some predictive content one second ahead. I cannot tell real persistence from a timing artifact yet: my seconds are based on my own arrival time, and arrival times inside a clump are not meaningful.
- Hypothesis: the rank correlation is now positive, unlike Entry 4, because the mid price from the book has no bid-ask bounce.

### Expectation
I expected the same-second regression of mid change on OFI to explain far more variance than the 0.3% I got from signed trade volume in Entry 4, since OFI and the mid price come from the same book. I expected the next-second regression to explain much less than the same-second one. I expected that removing the extreme OFI seconds might change the fit noticeably, because the OFI distribution has very heavy tails.

### Surprises
- The same-second R^2 was 0.63, and the slope (0.18) happened to be close to the 0.17 from the trades regression, even though the two use different data and features.
- The next-second R^2 of 3.3% was small but not zero, and about ten times the trade-volume result.
- Removing the top 1% of |OFI| changed the next-second R^2 only from 0.033 to 0.031, so the heavy tails were not driving it.
- The Spearman correlation (+0.27) is larger than the Pearson (+0.18) and positive, the reverse of Entry 4, where the last-trade price with bid-ask bounce gave a negative rank correlation.
- Mistake caught: I first pointed the regression's y at the wrong column, and regressing OFI on itself would have given an R^2 of exactly 1. A perfect fit is a sign of this kind of bug.

### Limitations
- In-sample, no standard errors (HAC needed), about 19 hours over several days with gaps, one asset.
- Seconds bucketed by arrival time, not exchange time.
- No costs, latency or fills. A correlation is not a trading result.

### Open questions
1. How much of the next-second effect remains when buckets use the exchange timestamp `E`?
2. What are the HAC standard errors of the slope, and does the effect hold on separate days?
3. How does the effect change with horizon (100 ms up to 10 s)?

### Next
Multi-level imbalance, microprice, and a proper walk-forward evaluation with ridge and logistic baselines.

## Entry 9: First out-of-sample baseline (10-11-2026)

### Goal
Get a first honest out-of-sample number for predicting the next second's mid price change from simple book features, and find out which feature does the work.

### Data and method
- `src/ladder/dataset.py`: one-second bars from the recorded top-of-book data (7.5 million updates, 5 sessions). Features at the end of second t: summed OFI (`ofi_sum`), last queue imbalance (`imb_last`), last spread in ticks (`spread_last`). Target `y`: mid price change over second t+1. Only seconds with both a previous and a next second are kept, so no change crosses a gap. 68,991 bars.
- `scripts/baseline.py`: linear regression by least squares (`numpy.linalg.lstsq`), trained on the first 70% of bars in time (48,293) and tested on the rest (20,693), with a 5 second embargo between them. Features are scaled with training-set means and standard deviations only. The benchmark is the training-set mean of `y`.
- The microprice is left out on purpose: it equals mid + (spread/2) x imbalance, so with a one-tick spread it would almost copy `imb_last`.

### Expectation
I expected the out-of-sample R^2 to be below the in-sample 3.3% from Entry 8, and possibly negative.

### Results
- Full model (three features): test R^2 = 0.0725, test Spearman = 0.381. Standardised weights: `ofi_sum` 0.42, `imb_last` 0.88, `spread_last` 0.08.
- Single features: `imb_last` 0.0648, `ofi_sum` 0.0336, `spread_last` -0.0012.
- Pairs and full set: `ofi_sum` + `imb_last` 0.0735, all three 0.0725.

### Interpretation
- Queue imbalance does most of the work and OFI adds about one percentage point. This matches the plan to show that a simple model does most of the work.
- `spread_last` has no signal (the spread is almost always one tick) and adding it slightly lowers the test R^2.
- Hypothesis (not tested): OFI over the second is already mostly reflected in the price by the end of the second, while the imbalance at that moment describes the book that decides the next move.
- The Spearman (0.38) is much higher than the R^2 suggests because squared error is dominated by a few very large moves (y ranges from -169 to +101, with the middle half exactly 0).

### Mistakes caught
- Used `1e9` (a float) as the bucket size, which loses precision at nanosecond timestamps near 1.8e18. The integer 1_000_000_000 fixes it.
- Used the maximum imbalance in a second instead of the last, which is a different feature.
- A feature-selection blank pointed at the test targets instead of the feature columns, which would have been a leak if it had run.

### Surprises
- The out-of-sample R^2 came out higher than the in-sample 3.3% in Entry 8, but the models differ (three features here, OFI alone there), so they are not comparable.
- Queue imbalance beat order flow imbalance, the feature the project is built around.

### Limitations
- One time split, so the number has no uncertainty attached. The test period is the latest 30% by time and covers a different price range from the training period.
- No standard errors. The test seconds are autocorrelated, so the effective sample is smaller than 20,693.
- Linear model only, level-1 features only, one asset. The depth recording covers about 26 minutes, too little for deeper-level features.
- A prediction, not a trading result: no costs, latency or fills.

### Open questions
1. How stable are these numbers across several walk-forward splits?
2. Does OFI alone on this same split give 0.034, and is the OFI gain over imbalance alone more than noise?
3. Does the picture change with a shorter horizon (100 ms) or a longer one (10 s)?
4. How much of the apparent signal remains after costs?

### Next
Walk-forward validation with several splits and an embargo, then ridge and logistic baselines, and HAC standard errors.

## Entry 10: Walk-forward validation and a volatility-scaled target (14-11-2026)

### Goal
Check how stable the 7.2% single-split R^2 from Entry 9 is, and explain the blocks where it fails.

### Method
- `scripts/walkforward.py`: four expanding-window splits with test blocks at 40-55%, 55-70%, 70-85% and 85-100% of the bars in time order, a 5 second embargo, train-only scaling, and the training mean of `y` as the benchmark. Features: `ofi_sum` and `imb_last` (`spread_last` dropped after the ablation).
- Diagnostics per block: standard deviation of `y` in train and test, and the calibration slope (regression of actual `y` on the prediction in the test block).
- Fix: `src/ladder/dataset.py` now adds `vol`, the standard deviation of the previous 300 seconds of mid changes (at least 60 samples). The model is trained on `y / vol` and its prediction is multiplied back by the test row's `vol`. `vol` only uses data up to the end of second t.

### Expectation
I expected the four R^2 values to cluster around the single-split 7.2%, with a possible dip in the block with the largest price move.

### Results
- Plain model, R^2 by block: 0.048, 0.078, 0.087, -0.009 (mean 0.051). Spearman 0.30 to 0.43 in every block.
- The last block has a test `y` standard deviation of 1.91 against 4.19 in training. The test period was calmer than the training data. My first explanation (a more volatile test block) was the opposite of what the data showed.
- Calibration slope tracks the ratio of test to train volatility: slopes 0.63, 0.78, 1.05, 0.48 against ratios 0.54, 0.67, 1.08, 0.46. The model's predictions are too large when the test period is calmer than training.
- If each block were rescaled with its own data (an upper bound, not a usable score), R^2 would be 0.074, 0.087, 0.087, 0.056.
- Volatility-scaled model, R^2 by block: 0.087, 0.099, 0.087, 0.062 (mean 0.084). Calibration slopes 0.99, 1.06, 0.80, 0.93.
- Dropping the 1,300 bars without a volatility estimate moved the block boundaries by about 500 rows each and changed block 2's R^2 from 0.063 to 0.078. The per-block scores are sensitive to where the cut falls.

### Interpretation
- The signal is present in every block, so the negative R^2 in the last block was a scale problem and not a missing signal. The dollar effect of a given imbalance depends on the volatility regime, and scaling by trailing volatility mostly corrects it.
- The single-split 7.2% in Entry 9 was at the top of the walk-forward range for the plain model. The plain walk-forward mean is 5.1%.

### Mistakes caught
- Wrong volatility hypothesis, corrected by printing the train and test standard deviations before building anything on it.
- An indentation error and an unbalanced bracket when editing code by hand.

### Surprises
- A model with a positive rank correlation in all four blocks (0.30 to 0.43) had a negative R^2 in one of them.
- The block scores moved noticeably when about 500 rows near each boundary were dropped.

### Limitations
- The volatility scaling was chosen after seeing these four blocks fail, so its improvement is partly tuned to this data. It needs fresh data to test it.
- Four blocks from five sessions at different price levels. No standard errors.
- The 300 row window counts rows, not seconds, and rows were dropped for missing neighbours, so it can span a short hole.
- Block 3's slope of 0.80 after scaling is unexplained.
- A prediction, not a trading result: no costs, latency or fills.

### Open questions
1. Does the volatility-scaled model hold on data recorded after this analysis?
2. How much of the signal does ridge or a different feature set change?
3. What are the HAC standard errors of the R^2 or of the weights across blocks?
4. How long does the autocorrelation of the features last, and is 5 seconds of embargo enough?

### Next
Ridge regression from scratch (derivation, check against scikit-learn), logistic regression on the sign of the move, HAC standard errors, then leakage experiments.

## Entry 11: Ridge from scratch and logistic regression on the sign of the move (14-11-2026)

### Goal
Add the next baselines to the plan: ridge regression derived and checked against scikit-learn, and a classifier for the direction of the next mid price move.

### Ridge regression
- Closed form w = (X^T X + lambda I)^-1 X^T y on standardised features with a centred target (the intercept is the training mean of `y/vol` and is not penalised). Matches scikit-learn `Ridge` to every printed digit (weights 0.08631 and 0.21912 at lambda = 10,000).
- On the 70-85% block with the volatility-scaled target, test R^2: 0.0869 for lambda 0 to 100, 0.0883 at 10,000, 0.0135 at 1,000,000, -0.0001 at 100,000,000. The lambda = 0 row equals the OLS result from the walk-forward script.
- Ridge does almost nothing here: two features and 47,378 training rows leave no variance to reduce. The +0.0014 at lambda = 10,000 is within the noise from moving the cut points.

### Logistic regression
- Task: up or down, with flat seconds dropped (`y == 0`). Only 12,107 of about 68,000 seconds have a nonzero mid change, so 82% of seconds are flat. My earlier assumption that about half were flat came from the trade-price series in Entry 4 and was wrong for the mid price.
- Fit by gradient descent (5,000 steps, learning rate 0.5) on the 70-85% block, 8,474 training and 1,815 test seconds, 5 second embargo. Weights [intercept, ofi_sum, imb_last] = [0.118, -0.118, 2.351], against scikit-learn [0.118, -0.117, 2.350].
- Test accuracy 0.841 against 0.536 for always predicting the majority side. Test log-loss 0.386 against 0.698 for a constant probability.
- Almost all the weight is on imbalance. The OFI weight is slightly negative, which is unreliable when imbalance is in the model.

### Leakage test: one extra second
- Targeting the move two seconds ahead (1,810 test rows): accuracy 0.662, against a majority baseline of about 0.536.
- About 60% of the edge above baseline (30.5 points to 12.6 points) disappears with one extra second of lag. Hypothesis (not separated): part of it is a timing effect at the one-second boundary, and part is ordinary signal decay. Two horizons cannot tell these apart.

### Interpretation
- When the mid price moves by one tick, the thinner queue has been used up, and the imbalance at the end of the previous second describes which side is thinner. That link is close to mechanical, so a high accuracy at a one-tick move is not absurd.
- The 84.1% is an upper bound that may include a boundary effect. The 66.2% is the more honest figure, for one block.
- The signal decays quickly with horizon, which is the first point of the decay curve in the plan.

### Expectation
I expected the up-or-down accuracy to be above 50% but well below the 84% I got, since the regression R^2 was only about 5 to 9%.

### Surprises
- 82% of seconds have exactly zero mid change, far more than the 51% of zero trade-price changes in Entry 4.
- The accuracy was 84%, much higher than the regression R^2 suggested. The two answer different questions: the classifier only has to rank the direction of moves that happen, while the regression is judged on squared dollar error, which a few huge moves dominate.
- One extra second of lag removed about 60% of the edge above the baseline.

### Limitations
- One time block with a small test set (1,815 and 1,810 rows), no standard errors, and one asset.
- The classifier conditions on the mid moving, which is only 18% of seconds, so it says nothing about when a move will happen.
- Features and target are one second apart, and the boundary effect is not separated from natural decay.
- A prediction, not a trading result: no costs, latency or fills.

### Open questions
1. How does accuracy decay with horizon at finer resolution (100 ms to 10 s)? That needs the depth data with the exchange timestamp.
2. How would a classifier for "will the mid move at all" do?
3. How stable is the 84% across walk-forward blocks?
4. How much of the edge survives costs and latency?

### Next
HAC standard errors, then leakage experiments (shuffled splits, the embargo length measurement).

## Entry 12: HAC (Newey-West) standard errors (14-11-2026)

### Goal
Put honest standard errors on the OFI slope, and find out whether heteroskedasticity or autocorrelation was the reason the naive standard error was too small in Entry 4.

### Method
`scripts/hac.py`: regression of the next-second mid change `y` on `ofi_sum` over all 68,991 bars. Naive, White (heteroskedasticity-robust) and Newey-West HAC standard errors with Bartlett weights w_k = 1 - k/(L+1), written from the formula and checked against statsmodels (`cov_type="HAC"`, `use_correction=False`).

### Expectation
I expected the HAC standard error to rise with the number of lags, because order flow and price changes are autocorrelated, and to end up well above the White value.

### Results
- Slope 0.04116 dollars per BTC of OFI (Entry 8: 0.0411).
- Naive se 0.00085 (t = 48.4). White se 0.00180 (t = 22.9).
- HAC se: 0.00179 (L=1), 0.00168 (L=5), 0.00166 (L=10), 0.00167 (L=30), 0.00170 (L=60). t between 22.96 and 24.73.
- statsmodels HAC at L=10: 0.00166, matching my value.

### Interpretation
- Heteroskedasticity roughly doubled the standard error (naive to White, 2.1x). The autocorrelation correction was small and in the opposite direction: HAC at L=10 is about 8% below White, and the value is flat for L from 5 to 60.
- Hypothesis (not tested directly): the residual variance rises with the size of the flow, which is what the White correction picks up. This is the same hypothesis left open in Entry 4.
- The slope is far from zero statistically (t about 24) but explains only 3.3% of the variance.

### Surprises
- The HAC standard error came out below the White one, not above it, so autocorrelation did not make the estimate less certain.
- The naive-to-White ratio here (2.1x) is much smaller than in Entry 4 (4.3x), for a different regression.

### Limitations
- Rows are not evenly spaced in time (gaps were removed), so lag k means k rows and only approximately k seconds.
- All five sessions are pooled and in-sample, with different price levels and volatility regimes.
- Heavy-tailed variables make the asymptotic standard errors an approximation.
- No correction for the number of things I have tried. A correlation is not a trading result.

### Open questions
1. Does the residual variance really rise with |flow|? (Bucket by |OFI| and compare residual standard deviations.)
2. How long do features, targets and labels stay correlated, and how does that set the embargo?

### Next
Leakage experiments: a random split against a time-ordered split with a multi-second label, and the feature autocorrelation at several lags.

## Entry 13: Leakage experiment and embargo length (14-11-2026)

### Goal
Show what leakage from overlapping labels looks like, and measure how long features and targets stay correlated, so the embargo is based on data and not on a guess.

### Method
`leakage_museum/01_overlapping_labels.py`: the label is the mid change over the next 10 seconds, so neighbouring bars share 9 of 10 seconds. The model sees no market data, only each bar's clock time, and predicts with the 5 nearest training bars in time. It is scored on a random 70/30 split and on a time-ordered 70/30 split. 67,225 bars have a clean 10-second label. Autocorrelation of `ofi_sum`, `imb_last` and the one-second target is measured at lags of 1, 2, 3, 5, 10 and 30 rows.

### Expectation
I expected the random split to give a large R^2 for a model with no information, and the time-ordered one to give about zero.

### Results
- Random split: R^2 = 0.845. Time-ordered split: R^2 = -0.131. The model has no market information.
- Autocorrelation at lags 1, 2, 3, 5, 10, 30: `ofi_sum` 0.181, 0.087, 0.051, 0.028, 0.006, 0.004. `y` 0.118, 0.076, 0.038, 0.034, 0.014, 0.000. `imb_last` 0.827, 0.713, 0.625, 0.497, 0.301, 0.095.
- Walk-forward rerun with a 30 second embargo instead of 5: every block's R^2 changed by 0.0005 or less (plain mean 0.0510, volatility-scaled blocks 0.0875, 0.0988, 0.0868, 0.0621). With a one-second label and a 2-parameter linear model the embargo length makes no practical difference. A more flexible model or a longer label would be more exposed.

### Interpretation
- The 0.845 is entirely leakage. Overlapping labels let a nearest-neighbour rule copy an answer from the training bar next to each test bar. Any result this strong from a simple model is a reason to check the split first.
- The -0.131 is what a model with no information looks like out of sample: it extrapolates stale labels and does worse than predicting the training mean.
- `ofi_sum` and `y` decorrelate within about 3 to 5 rows, so my 5 second embargo covers them. `imb_last` is still 0.50 correlated at 5 rows and 0.30 at 10, so 5 seconds was too short for that feature. About 30 seconds brings it to 0.095.

### Surprises
- A model that only knows what time it is can score 0.845.
- The one feature that carries most of the signal (`imb_last`) is also the most persistent, so it is the one most exposed to leakage between train and test.

### Limitations
- Lags count rows and not seconds, so a lag can span a removed gap.
- I have not rerun the walk-forward with a 30 second embargo, so I do not know how much the Entry 10 scores change.
- One asset, one set of sessions.

### Open questions
1. How much do the walk-forward R^2 values change with a 30 second embargo?
2. How should the label horizon and the embargo interact when the target covers more than one second (purged cross-validation)?

### Next
Rerun the walk-forward with a 30 second embargo, then build the purged and embargoed walk-forward splitter from scratch.