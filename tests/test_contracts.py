# tests/test_contracts.py
from lib.ledger import Ledger
from lib.helpers import parse_json, calculate_variance

def test_ledger_flow():
    l = Ledger()
    l.credit("user1", 100)
    l.credit("user2", 250)
    assert l.total_locked == 350

    withdrawn = l.debit("user1")
    assert withdrawn == 100
    assert l.get_balance("user1") == 0
    assert l.total_locked == 250

def test_json_cleaner():
    raw = "```json\n{\"passed\": true, \"reason\": \"ok\"}\n```"
    data = parse_json(raw)
    assert data["passed"] is True
    assert data["reason"] == "ok"

def test_variance():
    scores = [50.0, 50.0, 50.0]
    assert calculate_variance(scores) == 0.0

    divergent = [0.0, 100.0]
    assert calculate_variance(divergent) == 2500.0
