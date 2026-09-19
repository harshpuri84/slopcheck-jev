The scheduler now solves a 400-job week in 1.8 seconds, down from 47 seconds.

We replaced the greedy pass with a CP-SAT model and removed the hand-tuned priority table.

Two jobs still fail to place when a machine has more than six calendar exceptions. The
solver reports them rather than dropping them, so a planner sees the conflict.

Next: raise the exception ceiling to sixteen and re-measure.
