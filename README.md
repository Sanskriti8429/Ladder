# Ladder

**Short-horizon order flow signals on limit order book data, tested with realistic execution.**

`ladder` is a from-scratch research project on market microstructure. It reconstructs a limit order book from raw exchange data, builds order flow and book imbalance signals, and tests how much of the edge survives fees, latency and queue position.

> **Status:** early development. Checked boxes in the roadmap are the only things that exist.

## Approach

- Build from scratch first (OLS, ridge, walk-forward splits), then compare against libraries.
- Break things on purpose to see what a fake edge looks like.
- Test the pipeline on a synthetic market with a known, planted effect.
- Report negative results.

## Roadmap

- [ ] Repo, tooling and research log
- [ ] Crude end-to-end loop: trades, signed volume, hand-written OLS
- [ ] Live book recorder (Binance websocket to Parquet)
- [ ] Order book and matching engine with tests
- [ ] Book reconstruction (gaps, ordering, timestamps)
- [ ] Features: OFI, multi-depth imbalance, microprice
- [ ] Baselines: ridge and logistic regression, HAC standard errors
- [ ] Leakage experiments and purged walk-forward validation
- [ ] Synthetic market with planted impact
- [ ] Backtester: fees, latency sweep, queue assumptions
- [ ] Avellaneda-Stoikov market maker
- [ ] C++ port of the book with benchmarks
- [ ] Gradient boosting, then a small neural net
- [ ] Replay dashboard

```bash
git clone git@github.com:Sanskriti8429/Ladder.git
cd Ladder
python -m venv .venv 
.venv\Scripts\activate
pip install -r requirements.txt
pytest
```