import pytest
from ladder.backtest import trade_pnl


def test_buy_that_gains_after_crossing_the_spread():
    assert trade_pnl("buy", (100.00, 100.01), (100.04, 100.05)) == pytest.approx(0.03)


def test_sell_mirrors_buy():
    assert trade_pnl("sell", (100.04, 100.05), (100.00, 100.01)) == pytest.approx(0.03)


def test_unchanged_market_costs_the_spread():
    assert trade_pnl("buy", (100.00, 100.01), (100.00, 100.01)) == pytest.approx(-0.01)


def test_fee_is_charged_on_both_legs():
    assert trade_pnl("buy", (100.00, 100.01), (100.04, 100.05), fee_bps=1.0) == pytest.approx(0.009995)