from ladder.depthbook import DepthBook

def test_event_sets_absolute_quantities_and_zero_removes():
    book= DepthBook()
    book.apply_snapshot(
        last_update_id= 10,
        bids= [["100.00", "5.0"], ["99.99", "2.0"]],
        asks= [["100.01", "3.0"]],
    )
    book.apply_event(
        {"U": 11, "u": 12, "b": [["100.00", "4.0"], ["99.99", "0.0"]], "a": [["100.02", "1.0"]]}
    )
    assert book.bids== {10000: 4.0}
    assert book.asks== {10001: 3.0, 10002: 1.0}