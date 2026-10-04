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