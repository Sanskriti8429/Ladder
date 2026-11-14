import numpy as np
from ladder.splits import purged_walk_forward


def test_purged_split_leaves_no_overlap():
    t = np.arange(100)
    (train, test), = list(purged_walk_forward(t, horizon=10, embargo=5, blocks=[(0.5, 0.8)]))
    assert test[0] == 50
    assert train.max() == 34          # t=34: 34 + 10 + 5 = 49 < 50, but t=35 gives 50, which is not < 50
    assert len(train) == 35
    assert all(t[i] + 10 + 5 < t[test[0]] for i in train)


def test_zero_horizon_and_embargo_keeps_everything_before_the_block():
    t = np.arange(100)
    (train, test), = list(purged_walk_forward(t, horizon=0, embargo=0, blocks=[(0.5, 0.8)]))
    assert train.max() == 49
    assert len(train) == 50