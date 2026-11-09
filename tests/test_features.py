import pytest
from ladder.features import ofi, imbalance, depth_imbalance

def test_ofi_cases():
    prev= (100.00, 5.0, 100.02, 3.0)
    assert ofi(prev, (100.00, 7.0, 100.02, 3.0))== 2.0
    assert ofi(prev, (100.01, 4.0, 100.02, 3.0))== 4.0
    assert ofi(prev, (100.00, 5.0, 100.03, 2.0))== 3.0
    
def test_imbalance_cases():
    assert imbalance(5.0, 3.0)== 0.25
    assert imbalance(2.0, 2.0)== 0.0
    assert imbalance(0.0, 4.0)== -1.0
    assert imbalance(0.0, 0.0) == 0.0
    
def test_depth_imbalance():
    bids= {10000:5.0, 9999: 3.0, 9998: 2.0}
    asks= {10001: 1.0, 10002: 4.0, 10003: 6.0}
    assert depth_imbalance(bids, asks, 1) == pytest.approx(2 / 3)
    assert depth_imbalance(bids, asks, 2) == pytest.approx(3 / 13)
    assert depth_imbalance(bids, asks, 5) == pytest.approx(-1 / 21)