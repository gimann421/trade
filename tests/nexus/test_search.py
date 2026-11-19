from nexus.candidates import CANDIDATES
from nexus.domain.models import Bar
from nexus.ideas import iid
from nexus.search import CRITERIA, digest, load_ledger, next_candidate, record_for, run_next, _save


def _hist(syms, n=400):
    out = {}
    for k, s in enumerate(syms):
        p, bars = 100.0, []
        for i in range(n):
            p *= 1 + 0.0004 + 0.001 * ((i * (k + 3)) % 7 - 3) / 3
            y, m, d = 2020 + i // 336, 1 + (i % 336) // 28, 1 + i % 28
            bars.append(Bar(iid(s), f"{y}-{m:02d}-{d:02d}", p, p, p, p, 1e6))
        out[iid(s)] = bars
    return out


def test_every_candidate_is_long_only_unleveraged_and_has_variants():
    ids = [c.cid for c in CANDIDATES]
    assert len(ids) == len(set(ids))
    for c in CANDIDATES:
        w = c.strategy(_hist(c.symbols))
        assert all(x >= 0 for x in w.values()) and sum(w.values()) <= 0.99 + 1e-9
        assert c.variants and record_for(c)["success_criteria"] == CRITERIA


def test_queue_skips_done_and_ledger_roundtrip(tmp_path):
    assert next_candidate(set()).cid == CANDIDATES[0].cid
    assert next_candidate({c.cid for c in CANDIDATES}) is None
    _save(str(tmp_path), [{"cid": CANDIDATES[0].cid, "segments": {"validation": {"sharpe": 1.5}}, "cleared": False}])
    assert load_ledger(str(tmp_path))[0]["cid"] == CANDIDATES[0].cid
    assert digest(str(tmp_path))["best_validation_sharpe"]["sharpe"] == 1.5


def test_empty_queue_reports_without_running(tmp_path):
    _save(str(tmp_path), [{"cid": c.cid, "segments": {}} for c in CANDIDATES])
    assert run_next(None, ledger_dir=str(tmp_path))["status"] == "queue_empty"
