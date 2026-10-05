from ladder.orderbook import OrderBook

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