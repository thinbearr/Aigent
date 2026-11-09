"""Statistics used in the benchmark. Pure Python, no SciPy needed."""
from __future__ import annotations

import math
import random


def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson score interval for k successes in n trials."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _ratio(k, n):
    return None if n == 0 else k / n


def metrics(rows):
    """rows: iterable of (truth_is_attack, predicted_incident). Positive class = attack."""
    rows = list(rows)
    tp = sum(1 for t, p in rows if t and p)
    fn = sum(1 for t, p in rows if t and not p)
    fp = sum(1 for t, p in rows if not t and p)
    tn = sum(1 for t, p in rows if not t and not p)
    n, att, ben = len(rows), tp + fn, fp + tn
    prec, rec = _ratio(tp, tp + fp), _ratio(tp, att)
    f1 = None if prec is None or rec is None or prec + rec == 0 else 2 * prec * rec / (prec + rec)
    return dict(n=n, tp=tp, fp=fp, tn=tn, fn=fn, accuracy=_ratio(tp + tn, n), accuracy_ci=wilson(tp + tn, n), precision=prec,
                precision_ci=wilson(tp, tp + fp), recall=rec, recall_ci=wilson(tp, att), fpr=_ratio(fp, ben), fpr_ci=wilson(fp, ben), f1=f1)


def mcnemar_exact(a_correct: list[bool], b_correct: list[bool]):
    """Exact two-sided McNemar test on paired correctness. Returns dict(b, c, p): b = A right & B wrong, c = A wrong & B right."""
    b = sum(1 for x, y in zip(a_correct, b_correct) if x and not y)
    c = sum(1 for x, y in zip(a_correct, b_correct) if y and not x)
    n = b + c
    if n == 0:
        return dict(a_only=b, b_only=c, p=1.0)
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return dict(a_only=b, b_only=c, p=min(1.0, p))


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values for a family of comparisons."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 0):
    """Percentile bootstrap 95% CI of the mean (used for per-seed accuracy)."""
    if not values:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n_boot))
    return (means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1])


def pct(x, digits=0):
    return "-" if x is None else f"{100 * x:.{digits}f}%"


def ci_text(x, ci, digits=0):
    return "-" if x is None else f"{pct(x, digits)} ({pct(ci[0], digits)}-{pct(ci[1], digits)})"
