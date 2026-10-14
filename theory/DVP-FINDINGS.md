# dpv findings (Timing-is-Everything, arXiv 2605.00143) -> engine wiring

828 professional stand-ups. The numbers that change our defaults:

| finding | stat | our old default | new default |
|---|---|---|---|
| avg pause -> votes | r=0.36 (strongest!) | 300-500ms | setup 600ms |
| pause before punch | 1.37s vs 1.01s (+35.6%) | 500ms hold | **1500ms hold** |
| pause variability | r=0.35 | uniform 350ms gaps | +-25% jitter |
| speech rate | r=-0.10 (slower wins) | 180wpm sweet spot | keep + slower option |
| peak > avg surprise | r=0.10 vs flat |均匀 incongruity | schedule ONE big surprise late |
| expertise marker | pros extend 41.2% pause before surprise vs amateurs 27.4% | n/a | coupling = the judge signal |

Strategic coupling formula: pause_before_surprise = baseline_pause x 1.41
(pro level). Our new pre-punch 1500ms from a 600ms baseline = +150%... we
overshoot slightly but direction is right for deadpan sets; jitter keeps
it from feeling metronomic.

Wired: compose_set.py pause ladder (setup .6 / pre-punch 1.5 / tag 1.0
+ jitter). Next: perf_set/swap_material adopt same ladder; generation
from theory schedules the biggest semantic surprise late with the long
pause (dpv coupling).
