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