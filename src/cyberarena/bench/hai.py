"""Limited HAI experiment: unsupervised process-anomaly detection on ONE HAI file.

What this is:   a check that the process-anomaly part of the idea works on a public ICS dataset.
What this is NOT: a test of the Critic or of triage. HAI has sensor time series only: no logs, accounts or tickets.
                 Nothing here can validate the Critic, and nothing in this file claims it does.

Data: HAI 21.03 `test1.csv.gz` (https://github.com/icsdataset/hai), 43,201 rows at 1 Hz, 5 labelled attack segments.
Only one file was approved for download, so there is no separate training file. Protocol: fit the baseline on the first
`train_rows` rows (before the first attack, label never used for fitting), evaluate on everything after them.
The file is only ever read as data (gzip + csv). Nothing from it is executed.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
from pathlib import Path

import numpy as np


def load(path: Path):
    with gzip.open(path, "rt", encoding="utf8") as f:
        r = csv.reader(f)
        head = next(r)
        rows = list(r)
    attack_i = head.index("attack")
    feat = [i for i, c in enumerate(head) if c != "time" and not c.startswith("attack")]
    X = np.array([[float(row[i]) for i in feat] for row in rows], dtype=float)
    y = np.array([row[attack_i] == "1" for row in rows])
    return [head[i] for i in feat], X, y, [row[0] for row in rows]


def scores(X, train_rows, smooth=10):
    tr = X[:train_rows]
    d_tr = np.diff(tr, axis=0)
    mu, sd = tr.mean(0), tr.std(0)
    rng = np.percentile(tr, 99, axis=0) - np.percentile(tr, 1, axis=0)
    sd = np.maximum(sd, 0.01 * rng + 1e-6)
    dmu, dsd = d_tr.mean(0), np.maximum(d_tr.std(0), 0.01 * np.abs(rng) + 1e-6)
    level = np.abs((X - mu) / sd)
    diff = np.vstack([np.zeros((1, X.shape[1])), np.abs((np.diff(X, axis=0) - dmu) / dsd)])
    s = np.maximum(level, diff).max(1)
    if smooth > 1:                                    # rolling median over `smooth` seconds, causal
        pad = np.concatenate([np.full(smooth - 1, s[0]), s])
        s = np.array([np.median(pad[i:i + smooth]) for i in range(len(s))])
    return s


def segments(y):
    out, s = [], None
    for i, a in enumerate(y):
        if a and s is None:
            s = i
        if not a and s is not None:
            out.append((s, i - 1))
            s = None
    if s is not None:
        out.append((s, len(y) - 1))
    return out


def evaluate(path: Path, train_rows=2000, multipliers=(1, 2, 5, 10, 20), grace=60):
    names, X, y, times = load(path)
    s = scores(X, train_rows)
    test = np.arange(train_rows, len(y))
    segs = [g for g in segments(y) if g[0] >= train_rows]
    res = []
    for q in multipliers:
        thr = float(s[:train_rows].max() * q)
        pred = s > thr
        tp = int((pred[test] & y[test]).sum())
        fp = int((pred[test] & ~y[test]).sum())
        fn = int((~pred[test] & y[test]).sum())
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
        hit = [bool(pred[a:min(len(y), b + 1 + grace)].any()) for a, b in segs]
        # false alarm episodes = runs of alarms that touch no attack segment (+grace)
        near = np.zeros(len(y), bool)
        for a, b in segs:
            near[max(0, a - grace):min(len(y), b + 1 + grace)] = True
        eps, run = 0, False
        for i in test:
            if pred[i] and not near[i]:
                if not run:
                    eps += 1
                run = True
            else:
                run = False
        normal_hours = float((~near[test]).sum()) / 3600
        res.append(dict(quantile=q, threshold=thr, point_precision=prec, point_recall=rec, point_f1=f1, segments=len(segs),
                        segments_detected=sum(hit), false_alarm_episodes=eps, false_alarms_per_hour=eps / normal_hours if normal_hours else None))
    return dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), rows=len(y), sensors=len(names), train_rows=train_rows,
                test_rows=len(y) - train_rows, attack_segments_in_test=len(segs), attack_rows_in_test=int(y[train_rows:].sum()), results=res)


def to_markdown(r) -> str:
    L = [f"# HAI experiment (process anomaly detection only)", "",
         "**This does not test the Critic or alert triage.** HAI has sensor time series only: no logs, accounts or tickets. "
         "No ticket overlay was used.", "",
         f"File: `{r['file']}` (HAI 21.03, github.com/icsdataset/hai), sha256 `{r['sha256'][:16]}...`, {r['rows']} rows x {r['sensors']} sensors at 1 Hz. "
         f"Baseline fitted on the first {r['train_rows']} rows (before any attack; labels not used for fitting). "
         f"Evaluated on the remaining {r['test_rows']} rows: {r['attack_segments_in_test']} attack segments, {r['attack_rows_in_test']} attack rows.", "",
         "Detector: per-sensor z-score of the level and of the one-step change against the baseline, maximum over sensors, 10-second rolling median; "
         "alarm when above (multiplier) x the largest score seen in the baseline. The multiplier grid was fixed after a first run with quantile thresholds saturated (all identical); both runs are described in docs/BENCHMARK.md.", "",
         "| threshold = multiplier x max baseline score | point precision | point recall | point F1 | attack segments detected | false-alarm episodes | false alarms / hour |", "|---|---|---|---|---|---|---|"]
    f = lambda v: "-" if v is None else f"{v:.2f}"
    for x in r["results"]:
        L.append(f"| {x['quantile']} | {f(x['point_precision'])} | {f(x['point_recall'])} | {f(x['point_f1'])} | {x['segments_detected']}/{x['segments']} | "
                 f"{x['false_alarm_episodes']} | {f(x['false_alarms_per_hour'])} |")
    L += ["", "Reading: the detector finds every attack segment, but almost every alarm it raises is a false one at the point level (precision 1-2 %). "
              "A 2,000-second baseline is too short for this process: long benign periods after operating-point changes are flagged. "
              "Caveats: one file only, no separate training file, a simple statistical detector (not the HAI-benchmark models), and results depend on the threshold."]
    return "\n".join(L)
