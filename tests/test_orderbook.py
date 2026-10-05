from ladder.orderbook import OrderBook

def test_same_price_fills_in_time_order():
    book= OrderBook()
    book.add_limit(order_id=1, side="sell", price= 100, qty=5)
    book.add_limit(order_id=2, side="sell", price= 100, qty=5)
    fills= book.market_order(side="buy", qty=7)
    assert fills == [(1,100,5), (2,100,2)]