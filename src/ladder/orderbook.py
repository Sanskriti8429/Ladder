from collections import deque

class OrderBook:
    def __init__(self):
        self.asks= {}
        
    def add_limit(self, order_id, side, price, qty):
        if price not in self.asks:
            self.asks[price]= deque()
        self.asks[price].append([order_id, qty])
        
    def market_order(self, side, qty):
        fills= []
        for price in sorted(self.asks):
            queue= self.asks[price]
            while queue and qty>0:
                order_id, resting_qty= queue[0]
                take= min(qty, resting_qty)
                fills.append((order_id, price, take))
                qty -= take
                if take== resting_qty:
                    queue.popleft()
                else:
                    queue[0][1] -= take
            if not queue:
                del self.asks[price]
            if qty==0:
                break
        return fills