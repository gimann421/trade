from decimal import Decimal as D

from nexus.judgment import Call, gate


def _c(action, sym, dollars=0):
    return Call(action, sym, D(dollars), "medium", "3+ years", "2027-02-23", "because", "if wrong")


SNAP = {"cash": {"USD": "10000"}, "holdings": {"VTI": {"quantity": "100", "cost_basis": "1"}, "AAA": {"quantity": "50", "cost_basis": "1"},
                                              "BBB": {"quantity": "10", "cost_basis": "1"}}}
PX = {"VTI": D("300"), "AAA": D("400"), "BBB": D("100"), "NEW": D("50")}      # total 10000 + 30000 + 20000 + 1000 = 61000
TH = {"AAA": "ai", "BBB": "ai"}


def _why(call, themes=TH):
    return gate([call], SNAP, PX, themes, D("0.10"), frozenset({"VTI"}))[0][1]


def test_protected_fund_can_never_be_trimmed():
    assert any("protected" in w for w in _why(_c("TRIM", "VTI", 100)))
    assert _why(_c("HOLD", "VTI")) == []


def test_buy_is_limited_by_position_cap_cash_floor_and_theme_cap():
    assert _why(_c("BUY", "NEW", 1000)) == []
    assert any("position limit" in w for w in _why(_c("BUY", "NEW", 7000)))
    assert any("floor" in w for w in _why(_c("BUY", "NEW", 9000)))
    assert any("theme" in w for w in _why(_c("ADD", "BBB", 100)))


def test_buy_vs_add_vs_unowned_and_missing_price():
    assert any("already owned" in w for w in _why(_c("BUY", "AAA", 100)))
    assert any("not owned" in w for w in _why(_c("ADD", "NEW", 100)))
    assert any("no price" in w for w in _why(_c("BUY", "ZZZ", 100)))


def test_cumulative_spend_cannot_breach_the_cash_floor():
    res = gate([_c("BUY", "NEW", 3000), _c("BUY", "NEW2", 4000)], SNAP, {**PX, "NEW2": D("10")}, TH, D("0.10"), frozenset({"VTI"}))
    assert res[0][1] == [] and any("floor" in w for w in res[1][1])
