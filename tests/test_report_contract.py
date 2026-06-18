from sprintsight.report.contract import Claim, Report


def test_report_defaults():
    rep = Report(team="Echo", audience="exec")
    assert rep.sections == {}
    assert rep.claims == []
    assert rep.insufficient_evidence is False


def test_claim_holds_citations():
    c = Claim(text="Velocity 38.", citations=["burndown-boreas-s15"])
    assert c.citations == ["burndown-boreas-s15"]
