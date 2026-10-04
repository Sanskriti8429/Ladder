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