from collections import deque

class OrderBook:
    def __init__(self):
        self.books= {"buy":{}, "sell": {}}
        self.index= {}
        
    def _match(self, side, qty, limit_price=None):
        opposite= "sell" if side== "buy" else "buy"
        levels= self.books[opposite]
        fills= []
        for price in sorted(levels, reverse=(side=="sell")):
            if limit_price is not None:
                if side== "buy" and price> limit_price:
                    break
                if side== "sell" and price< limit_price:
                    break
            queue= levels[price]
            while queue and qty>0:
                order_id, resting_qty= queue[0]
                take= min(qty, resting_qty)
                fills.append((order_id, price, take))
                qty -= take
                if take== resting_qty:
                    queue.popleft()
                    del self.index[order_id]
                else:
                    queue[0][1] -= take
            if not queue:
                del levels[price]
            if qty==0:
                break
        return fills, qty
    
    def add_limit(self, order_id, side, price, qty):
        fills, remaining =self._match(side, qty, limit_price= price)
        if remaining>0:
            levels =self.books[side]
            if price not in levels:
                levels[price]= deque()
            levels[price].append([order_id, remaining])
            self.index[order_id]= (side, price)
        return fills
    
    def market_order(self, side, qty):
        fills, _= self._match(side, qty)
        return fills
    
    def cancel(self, order_id):
        entry= self.index.pop(order_id, None)
        if entry is None:
            return False
        side, price= entry
        queue= self.books[side][price]
        for resting in queue:
            if resting[0]== order_id:
                queue.remove(resting)
                break
        if not queue:
            del self.books[side][price]
        return True