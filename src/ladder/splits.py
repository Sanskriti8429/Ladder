import numpy as np


def purged_walk_forward(t, horizon, embargo, blocks):
    """Yield (train_idx, test_idx) for each (start, end) fraction in blocks.

    t        : sorted array of bar start times in seconds
    horizon  : label length in seconds (the label of row i covers t[i] to t[i] + horizon)
    embargo  : extra seconds dropped before the test block, to cover feature autocorrelation
    """
    t = np.asarray(t)
    for a, b in blocks:
        i0, i1 = int(len(t) * a), int(len(t) * b)
        start = t[i0]
        train = np.where(t + horizon + embargo < start)[0]
        test = np.arange(i0, i1)
        yield train, test