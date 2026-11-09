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