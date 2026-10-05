from collections import deque

class OrderBook:
    def __init__(self):
        self.books= {"buy": {}, "sell": {}}
        self.index= {}
        
    def add_limit(self, order_id, side, price, qty):
        levels= self.books[side]
        if price not in levels:
            levels[price]= deque()
        levels[price].append([order_id, qty])
        self.index[order_id]= (side, price)
        
    def market_order(self, side, qty):
        opposite= "sell" if side== "buy" else "buy"
        levels= self.books[opposite]
        fills= []
        for price in sorted(levels, reverse=(side=="sell")):
            queue= levels[price]
            while queue and qty>0:
                order_id, resting_qty= queue[0]
                take= min(qty, resting_qty)
                fills.append((order_id, price, take))
                qty -= take
                if take==resting_qty:
                    queue.popleft()
                    del self.index[order_id]
                else:
                    queue[0][1] -= take
            if not queue:
                del levels[price]
            if qty==0:
                break
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