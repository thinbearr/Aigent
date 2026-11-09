# HAI experiment (process anomaly detection only)

**This does not test the Critic or alert triage.** HAI has sensor time series only: no logs, accounts or tickets. No ticket overlay was used.

File: `test1.csv.gz` (HAI 21.03, github.com/icsdataset/hai), sha256 `532de41bed372206...`, 43201 rows x 79 sensors at 1 Hz. Baseline fitted on the first 2000 rows (before any attack; labels not used for fitting). Evaluated on the remaining 41201 rows: 5 attack segments, 629 attack rows.

Detector: per-sensor z-score of the level and of the one-step change against the baseline, maximum over sensors, 10-second rolling median; alarm when above (multiplier) x the largest score seen in the baseline. The multiplier grid was fixed after a first run with quantile thresholds saturated (all identical); both runs are described in docs/BENCHMARK.md.

| threshold = multiplier x max baseline score | point precision | point recall | point F1 | attack segments detected | false-alarm episodes | false alarms / hour |
|---|---|---|---|---|---|---|
| 1 | 0.02 | 1.00 | 0.03 | 5/5 | 6 | 0.54 |
| 2 | 0.02 | 1.00 | 0.03 | 5/5 | 5 | 0.45 |
| 5 | 0.01 | 0.89 | 0.03 | 5/5 | 5 | 0.45 |
| 10 | 0.01 | 0.83 | 0.03 | 5/5 | 5 | 0.45 |
| 20 | 0.01 | 0.77 | 0.02 | 5/5 | 5 | 0.45 |

Reading: the detector finds every attack segment, but almost every alarm it raises is a false one at the point level (precision 1-2 %). A 2,000-second baseline is too short for this process: long benign periods after operating-point changes are flagged. Caveats: one file only, no separate training file, a simple statistical detector (not the HAI-benchmark models), and results depend on the threshold.