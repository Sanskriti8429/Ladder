def ofi(prev, new):
    pb, qb, pa, qa= prev
    nb, nqb, na, nqa= new
    e= 0.0
    if nb>=pb:
        e+= nqb
    if nb<= pb:
        e-= qb
    if na<= pa:
        e-= nqa
    if na>= pa:
        e+= qa
    return e

def imbalance(bid_qty, ask_qty):
    total= bid_qty +ask_qty
    if total== 0.0:
        return 0.0
    return (bid_qty - ask_qty)/total

def depth_imbalance(bids, asks, n):
    bid_total= sum(bids[p] for p in sorted(bids, reverse= True)[:n])
    ask_total= sum(asks[p] for p in sorted(asks, reverse= False)[:n])
    return imbalance(bid_total, ask_total)

    
def microprice(bid, bid_qty, ask, ask_qty):
    total= bid_qty + ask_qty
    if total== 0:
        return (bid + ask)/2
    return (bid * ask_qty + ask * bid_qty)/total