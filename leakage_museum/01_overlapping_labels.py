"""Leakage 1: overlapping labels.
A model that only knows the clock time scores R^2 = 0.845 on a random split and -0.131
on a time-ordered split, because the label of each bar covers the next 10 seconds and
neighbouring bars share 9 of them. Fix: split by time, and leave an embargo at least as
long as the label horizon plus the decay of the features' autocorrelation."""