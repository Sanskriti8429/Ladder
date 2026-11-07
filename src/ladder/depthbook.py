class ChainBreak(Exception):
    pass

class DepthBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}
        self.last_update_id = None

    @staticmethod
    def _ticks(price):
        return round(float(price) * 100)

    def apply_snapshot(self, last_update_id, bids, asks):
        self.bids = {self._ticks(p): float(q) for p, q in bids}
        self.asks = {self._ticks(p): float(q) for p, q in asks}
        self.last_update_id = last_update_id

    def _apply_levels(self, side, levels):
        for price, qty in levels:
            tick = self._ticks(price)
            q = float(qty)
            if q == 0:
                side.pop(tick, None)
            else:
                side[tick] = q

    def apply_event(self, event):
        if event["u"]<= self.last_update_id:
            return
        if event["U"]> self.last_update_id +1:
            raise ChainBreak(f"missed events: have {self.last_update_id}, got U={event['U']}")
        self._apply_levels(self.bids, event["b"])
        self._apply_levels(self.asks, event["a"])
        self.last_update_id = event["u"]
        
    def sync(self, snapshot, buffered_events):
        self.apply_snapshot(snapshot["lastUpdateId"], snapshot["bids"], snapshot["asks"])
        for event in buffered_events:
            self.apply_event(event)