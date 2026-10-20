"""Round 21: walk-forward ridge blend of price and volume signals, monthly and 3-session
(research/r21-walk-forward-blend-2026-10-20.md).

    PYTHONPATH=. python research/round21_tests.py --register
    PYTHONPATH=. python research/round21_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.intraday import sample_tickers
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from core.universe import load_member_panel, members_on
from research.round6_scan import load_inputs, load_module, lookup
from research.round8_short_horizon import dirty_index
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round19_tests import daily_eval, daily_fails

MEMO = "research/r21-walk-forward-blend-2026-10-20.md"
OUT_DIR = ROOT / "backtests" / "round21_tests"
FIRST_DECISION, RULE_ID = "2017-01-03", "rev5_h3_band40_s"
PENALTY = 0.05
HYP = {
    "blend_m_quintile": "A walk-forward ridge blend of 12 price and volume features, top 20% by score held monthly, passes the bar in both windows against the equal-weight members",
    "blend_d_band": "A walk-forward ridge blend of 12 short-horizon features, ranked every 3 sessions with the 40% band, passes the bar in both windows on both screens and beats the plain reversal parent's net active",
}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 21: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 21: thread-chosen method (walk-forward model), keep testing until one passes.",
                                        research_memo=MEMO, strategy="round21_tests.py")
    return {rid: ids[f"Round 21: {rid}"] for rid in HYP}


def member_mask(membership, index, columns):
    mask = pd.DataFrame(False, index, columns)
    pos = membership.index.searchsorted(index, side="right") - 1
    cols = {c: i for i, c in enumerate(columns)}
    cache = {}
    values = np.zeros((len(index), len(columns)), dtype=bool)
    for i, p in enumerate(pos):
        if p < 0:
            continue
        if p not in cache:
            row = np.zeros(len(columns), dtype=bool)
            for t in membership.iloc[p]:
                if t in cols:
                    row[cols[t]] = True
            cache[p] = row
        values[i] = cache[p]
    return pd.DataFrame(values, index, columns)


def ranked(frame, mask):
    return (frame.where(mask).rank(axis=1, pct=True) - 0.5)


def rolling_beta(ret, mret, window=63, min_periods=50):
    mm = mret.rolling(window, min_periods=min_periods).mean()
    cov = ret.mul(mret, axis=0).rolling(window, min_periods=min_periods).mean() - ret.rolling(window, min_periods=min_periods).mean().mul(mm, axis=0)
    return cov.div(mret.rolling(window, min_periods=min_periods).var(ddof=0), axis=0)


def monthly_features(c, o, h, l, v, vti):
    ret = c.pct_change(fill_method=None)
    mret = vti.pct_change(fill_method=None)
    ov = np.log1p((o / c.shift(1) - 1).where(lambda x: x.abs() <= 0.5))
    itd = np.log1p((c / o - 1).where(lambda x: x.abs() <= 0.5))
    beta = rolling_beta(ret, mret)
    return {
        "r5": c / c.shift(5) - 1, "r21": c / c.shift(21) - 1, "m31": c.shift(21) / c.shift(63) - 1, "m61": c.shift(21) / c.shift(126) - 1,
        "vol63": ret.rolling(63, min_periods=50).std(), "beta63": beta, "max21": ret.rolling(21, min_periods=19).max(),
        "skew63": ret.rolling(63, min_periods=50).skew(), "volratio": v.rolling(21, min_periods=19).mean() / v.rolling(126, min_periods=100).mean(),
        "overnight": ov.rolling(106, min_periods=90).sum().shift(21), "intraday": itd.rolling(106, min_periods=90).sum().shift(21),
        "dist126": c / c.rolling(126, min_periods=100).max() - 1,
    }


def daily_features(c, o, h, l, v, vti):
    ret = c.pct_change(fill_method=None)
    mret = vti.pct_change(fill_method=None)
    beta = rolling_beta(ret, mret)
    return {
        "r1": ret, "r2": c / c.shift(2) - 1, "r5": c / c.shift(5) - 1, "r10": c / c.shift(10) - 1, "r21": c / c.shift(21) - 1,
        "vol20": ret.rolling(20, min_periods=18).std(), "volratio": v.rolling(5, min_periods=5).mean() / v.rolling(60, min_periods=50).mean(),
        "clv": ((c - l) / (h - l)).where(h > l), "gap": o / c.shift(1) - 1, "intra": c / o - 1, "dist126": c / c.rolling(126, min_periods=100).max() - 1,
        "m61": c.shift(21) / c.shift(126) - 1,
    }


def stack(features, mask):
    names = list(features)
    cube = np.stack([ranked(features[k], mask).to_numpy() for k in names], axis=2)   # T x N x K
    return names, cube


def fit(X, y, mask_rows):
    """Ridge with fixed penalty on rows where the target exists; X features NaN -> 0."""
    ok = ~np.isnan(y) & mask_rows
    if ok.sum() < 500:
        return None
    Xs, ys = np.nan_to_num(X[ok]), y[ok]
    n = len(ys)
    return np.linalg.solve(Xs.T @ Xs / n + PENALTY * np.eye(Xs.shape[1]), Xs.T @ ys / n)


def walk_forward(cube, target, mask, decision_pos, horizon, refit_every, spacing):
    """Scores (T x N) at decision positions; model refit at the first decision of each refit group with samples whose
    target ended on or before that decision. Returns scores and the list of (date position, weights)."""
    scores = np.full(cube.shape[:2], np.nan)
    weights, w = [], None
    for k, p in enumerate(decision_pos):
        if k % refit_every == 0:
            last = p - horizon
            rows = np.arange(0, last + 1, spacing)
            X = cube[rows].reshape(-1, cube.shape[2])
            y = target[rows].reshape(-1)
            m = mask[rows].reshape(-1)
            w = fit(X, y, m)
            weights.append((p, w))
        if w is not None:
            s = np.nan_to_num(cube[p]) @ w
            scores[p] = np.where(mask[p] & ~np.isnan(cube[p]).all(axis=1), s, np.nan)
    return scores, weights


def forward_target(c, horizon, mask):
    fwd = c.shift(-horizon) / c - 1
    fwd = fwd.where(mask)
    return ranked(fwd - fwd.mean(axis=1).to_numpy()[:, None], mask).to_numpy()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    conn = connect()
    ids = register(conn)
    if args.register:
        print(f"registered {ids}")
        return
    fs, rm, sh = load_module("factor_scan_v1"), load_module("residual_momentum_v1"), load_module("short_horizon_v3")
    sh.FIRST_DECISION = FIRST_DECISION
    fs.FIRST_DECISION = FIRST_DECISION
    membership, stocks, etf = load_inputs(fs, rm)
    index, cols = etf.index, list(stocks.columns)
    panel = lambda f: load_member_panel(cols, f).reindex(index)[cols]
    o, h, l, v = panel("open"), panel("high"), panel("low"), panel("volume")
    mask = member_mask(membership, index, cols) & stocks.notna()
    vti = etf["VTI"]
    mask_np = mask.to_numpy()

    # ---- monthly model
    names, cube = stack(monthly_features(stocks, o, h, l, v, vti), mask)
    target = forward_target(stocks, 21, mask)
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    pos = [index.get_loc(d) for d in decisions]
    scores, weights = walk_forward(cube, target, mask_np, pos, 21, 1, 5)
    print("monthly model first fit", index[weights[0][0]].date(), "weights", dict(zip(names, np.round(weights[0][1], 3))), flush=True)
    wdf = pd.DataFrame([w for _, w in weights if w is not None], index=[index[p] for p, w in weights if w is not None], columns=names)
    by_era = {"IS": wdf[wdf.index <= "2022-12-31"].mean().round(3).to_dict(), "OOS": wdf[wdf.index > "2022-12-31"].mean().round(3).to_dict()}
    print("mean weights by era", json.dumps(by_era), flush=True)
    sc = pd.DataFrame(scores, index, cols)
    close_ff = stocks.ffill()
    returns = stocks.pct_change(fill_method=None)
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    rows = {"blend": [], "parent": []}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        s = sc.loc[date, priced].dropna()
        k = lambda n, frac: max(1, int(round(frac * n)))
        rows["blend"].append((date, equal(top(s, k(len(s), 0.2))) if len(s) >= 20 else {}, list(s.index), priced))
        res = rm.residual_scores(returns, factors, index.get_loc(date), priced, **fs.RESMOM6_1)
        rows["parent"].append((date, equal(top(res, k(len(res), 0.1))), list(res.index), priced))
    mout = {}
    for name, r in rows.items():
        mout[name] = run_rule(r, close_ff, index)
        print(f"{name:8s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} "
                                      f"10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}" for w, c in mout[name].items()), flush=True)

    # ---- 3-session model
    rule = next(r for r in sh.RULES if r["id"] == RULE_ID)
    ddec = sh.decision_dates(index, 3)
    dpos = [index.get_loc(d) for d in ddec]
    dnames, dcube = stack(daily_features(stocks, o, h, l, v, vti), mask)
    dtarget = forward_target(stocks, 3, mask)
    first_of_month = [i for i, p in enumerate(dpos) if i == 0 or ddec[i].month != ddec[i - 1].month]
    dscores = np.full(dcube.shape[:2], np.nan)
    dweights, w = [], None
    for i, p in enumerate(dpos):
        if i in first_of_month:
            rows_ = np.arange(0, p - 3 + 1, 3)
            w = fit(dcube[rows_].reshape(-1, dcube.shape[2]), dtarget[rows_].reshape(-1), mask_np[rows_].reshape(-1))
            dweights.append((p, w))
        if w is not None:
            dscores[p] = np.where(mask_np[p] & ~np.isnan(dcube[p]).all(axis=1), np.nan_to_num(dcube[p]) @ w, np.nan)
    dw = pd.DataFrame([w_ for _, w_ in dweights if w_ is not None], index=[index[p] for p, w_ in dweights if w_ is not None], columns=dnames)
    dby = {"IS": dw[dw.index <= "2022-12-31"].mean().round(3).to_dict(), "OOS": dw[dw.index > "2022-12-31"].mean().round(3).to_dict()}
    print("3-session mean weights by era", json.dumps(dby), flush=True)
    dsc = pd.DataFrame(dscores, index, cols)
    parent_score = -(stocks / stocks.shift(5) - 1)
    dirty = dirty_index(index)
    sample = set(sample_tickers())
    unseen = [c for c in cols if c not in sample]
    units = {"parent": parent_score, "blend_d_band": dsc}
    dout = {"screen_all": daily_eval("screen_all", stocks, units, sh, fs, membership, ddec, rule, dirty),
            "screen_unseen": daily_eval("screen_unseen", stocks[unseen], {k_: v_[unseen] for k_, v_ in units.items()}, sh, fs, membership, ddec, rule, dirty)}
    verdicts = {"blend_m_quintile": bar_fails(mout["blend"]),
                "blend_d_band": sum((daily_fails(dout[ev]["blend_d_band"], dout[ev]["parent"]) for ev in dout), [])}
    for rid, fails in verdicts.items():
        print(rid, "PASS the screen" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        if rid == "blend_m_quintile":
            c = mout["blend"]
            body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})" for w in JUDGED)
        else:
            body = "; ".join(f"{ev} " + ", ".join(f"{w} {dout[ev][rid][w]['net_active']:.2%}/yr (IR {dout[ev][rid][w]['information_ratio']:.2f}, placebo {dout[ev][rid][w]['placebo']:.3f})" for w in JUDGED) for ev in dout)
        add_evidence(conn, ids[rid], "backtest", f"round21_tests {rid}: {'passes the screen' if not fails else 'fails'}. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "rejected" if fails else ("supported" if rid == "blend_m_quintile" else "testing"))
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "monthly": mout, "daily": dout, "verdicts": verdicts,
                                "monthly_weights_by_era": by_era, "daily_weights_by_era": dby}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
