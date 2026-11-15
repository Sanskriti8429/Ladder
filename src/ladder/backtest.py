def trade_pnl(side, entry, exit_, fee_bps=0.0):
    """entry and exit_ are (bid, ask) quotes. Returns the PnL per unit of the asset, after fees."""
    (eb, ea), (xb, xa) = entry, exit_
    if side == "buy":
        gross = xb - ea
        traded = ea + xb
    else:
        gross = eb - xa
        traded = eb + xa
    return gross - fee_bps / 1e4 * traded