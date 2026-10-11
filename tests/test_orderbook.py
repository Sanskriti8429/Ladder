from ladder.orderbook import OrderBook
from hypothesis import given, strategies as st

orders = st.lists(
    st.tuples(st.sampled_from(["buy", "sell"]), st.integers(90, 100), st.integers(1, 10)),
    max_size=50,
)


@given(orders)
def test_book_is_never_crossed(order_list):
    book = OrderBook()
    for i, (side, price, qty) in enumerate(order_list):
        book.add_limit(order_id=i, side=side, price=price, qty=qty)
        bid = book.best_bid()
        ask = book.best_ask()
        if bid is not None and ask is not None:
            assert bid < ask

def test_same_price_fills_in_time_order():
    book= OrderBook()
    book.add_limit(order_id=1, side="sell", price= 100, qty=5)
    book.add_limit(order_id=2, side="sell", price= 100, qty=5)
    fills= book.market_order(side="buy", qty=7)
    assert fills == [(1,100,5), (2,100,2)]
    
def test_market_order_sweeps_levels():
    book= OrderBook()
    book.add_limit(order_id=1, side="sell", price=100, qty=3)
    book.add_limit(order_id=2, side="sell", price=101, qty=4)
    book.add_limit(order_id=3, side="sell", price=102, qty=5)
    fills= book.market_order(side="buy", qty=9)
    assert fills == [(1,100,3), (2,101,4), (3,102,2)]
    
def test_cancel_filled_order_fails_safely():
    book= OrderBook()
    book.add_limit(order_id=1, side="sell", price=100, qty=5)
    book.market_order(side="buy", qty=5)
    assert book.cancel(1) == False

def test_cancel_resting_order_removes_it():
    book= OrderBook()
    book.add_limit(order_id=1, side="sell", price=100, qty=5)
    book.add_limit(order_id=2, side="sell", price= 100, qty=5)
    assert book.cancel(1)== True
    fills= book.market_order(side="buy", qty=3)
    assert fills == [(2,100,3)]
    
def test_sell_market_order_hits_highest_bid_first():
    book= OrderBook()
    book.add_limit(order_id=1, side="buy", price=100, qty=5)
    book.add_limit(order_id=2, side="buy", price=101, qty=5)
    fills= book.market_order(side="sell", qty=7)
    assert fills== [(2,101,5), (1,100,2)]
    
def test_market_order_larger_than_book_takes_everything():
    book= OrderBook()
    book.add_limit(order_id=1, side= "sell", price=100, qty=3)
    book.add_limit(order_id=2, side="sell", price= 101, qty=2)
    fills= book.market_order(side="buy", qty=10)
    assert fills== [(1,100,3), (2,101,2)]
    assert book.books["sell"]== {}
    assert book.index== {}
    
def test_crossing_limit_order_trades_at_resting_price():
    book= OrderBook()
    book.add_limit(order_id=1, side="sell", price=100, qty=5)
    fills= book.add_limit(order_id=2, side="buy", price= 101, qty=3)
    assert fills== [(1,100,3)]
    assert book.books["buy"]== {}
    
def test_partially_filled_limit_order_rests_remainder():
    book= OrderBook()
    book.add_limit(order_id=1, side="sell", price=100, qty=3)
    fills= book.add_limit(order_id=2, side="buy", price=101, qty=5)
    assert fills== [(1,100,3)]
    assert list(book.books["buy"][101])==[[2,2]]
    assert book.books["sell"]== {}
    
def test_best_bid_ask_and_spread():
    book = OrderBook()
    assert book.best_bid() is None
    book.add_limit(order_id=1, side="buy", price=99, qty=5)
    book.add_limit(order_id=2, side="buy", price=98, qty=5)
    book.add_limit(order_id=3, side="sell", price=102, qty=5)
    book.add_limit(order_id=4, side="sell", price=103, qty=5)
    assert book.best_bid() == 99
    assert book.best_ask() == 102
    assert book.spread() == 3