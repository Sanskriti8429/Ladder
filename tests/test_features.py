from ladder.features import ofi, imbalance

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