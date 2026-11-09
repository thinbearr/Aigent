from cyberarena.bench import stats


def test_wilson_known_values():
    lo, hi = stats.wilson(8, 10)
    assert abs(lo - 0.4902) < 1e-3 and abs(hi - 0.9433) < 1e-3
    assert stats.wilson(0, 0) is None


def test_mcnemar_exact():
    a = [True] * 10 + [True] * 2
    b = [False] * 10 + [True] * 2          # A right / B wrong 10 times, never the reverse
    r = stats.mcnemar_exact(a, b)
    assert r["a_only"] == 10 and r["b_only"] == 0 and abs(r["p"] - 2 / 1024) < 1e-9
    assert stats.mcnemar_exact([True], [True])["p"] == 1.0


def test_holm_is_monotone_and_bounded():
    h = stats.holm({"a": 0.01, "b": 0.04, "c": 0.5})
    assert abs(h["a"] - 0.03) < 1e-12 and abs(h["b"] - 0.08) < 1e-12 and h["c"] == 0.5


def test_metrics_confusion():
    m = stats.metrics([(True, True), (True, False), (False, True), (False, False), (False, False)])
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (1, 1, 1, 2)
    assert abs(m["fpr"] - 1 / 3) < 1e-9
