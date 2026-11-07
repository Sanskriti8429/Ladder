import pytest
from ladder.depthbook import DepthBook, ChainBreak

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
    
def test_gap_in_chain_raises_and_leaves_book_unchanged():
    book = DepthBook()
    book.apply_snapshot(last_update_id=10, bids= [["100.00", "5.0"]], asks= [["100.01", "3.0"]])
    book.apply_event({"U":11, "u":12, "b": [], "a":[]})
    with pytest.raises(ChainBreak):
        book.apply_event({"U":14, "u":15, "b": [["100.00", "1.0"]], "a":[]})
    assert book.bids=={10000: 5.0}
    assert book.last_update_id==12
    
def test_stale_event_ignored_and_overlapping_event_applied():
    book = DepthBook()
    book.apply_snapshot(last_update_id=10, bids=[["100.00", "5.0"]], asks=[])
    book.apply_event({"U": 8, "u": 10, "b": [["100.00", "1.0"]], "a": []})
    assert book.bids == {10000: 5.0}
    book.apply_event({"U": 9, "u": 12, "b": [["100.00", "2.0"]], "a": []})
    assert book.bids == {10000: 2.0}
    assert book.last_update_id == 12
    
def test_sync_drops_stale_bridges_and_chains():
    book = DepthBook()
    snapshot = {"lastUpdateId": 10, "bids": [["100.00", "5.0"]], "asks": [["100.01", "3.0"]]}
    buffered = [
        {"U": 5, "u": 9, "b": [["100.00", "9.0"]], "a": []},
        {"U": 9, "u": 12, "b": [["100.00", "4.0"]], "a": []},
        {"U": 13, "u": 14, "b": [], "a": [["100.01", "0.0"]]},
    ]
    book.sync(snapshot, buffered)
    assert book.bids == {10000: 4.0}
    assert book.asks == {}
    assert book.last_update_id == 14


def test_sync_with_too_old_snapshot_raises():
    book = DepthBook()
    snapshot = {"lastUpdateId": 10, "bids": [], "asks": []}
    buffered = [{"U": 20, "u": 25, "b": [], "a": []}]
    with pytest.raises(ChainBreak):
        book.sync(snapshot, buffered)