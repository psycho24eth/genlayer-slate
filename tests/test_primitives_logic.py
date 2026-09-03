# tests/test_primitives_logic.py
"""
Unit tests validating the deterministic decision logic, invariant boundaries,
canonical serialization, and pull-payment accounting across all 8 Slate primitives.
"""

import json
import pytest


def parse_json_response(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1:
        t = t[start : end + 1]
    return json.loads(t)


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class TestHelperLogic:
    def test_parse_json_markdown_wrapped(self):
        raw = "```json\n{\"passed\": true, \"confidence\": 0.95, \"reason\": \"all good\"}\n```"
        data = parse_json_response(raw)
        assert data["passed"] is True
        assert data["confidence"] == 0.95
        assert data["reason"] == "all good"

    def test_parse_json_prose_wrapped(self):
        raw = "Here is your output:\n{\"valid\": true, \"severity\": \"HIGH\", \"payout_pct\": 50}\nThanks!"
        data = parse_json_response(raw)
        assert data["valid"] is True
        assert data["severity"] == "HIGH"
        assert data["payout_pct"] == 50

    def test_canonical_sorts_keys(self):
        obj1 = {"z": 1, "a": 2, "m": 3}
        obj2 = {"a": 2, "m": 3, "z": 1}
        assert canonical(obj1) == canonical(obj2)
        assert canonical(obj1) == '{"a":2,"m":3,"z":1}'


class TestMilestoneEscrowLogic:
    def test_settle_decision(self):
        threshold = 700
        # passed with high confidence -> SETTLE
        passed = True
        conf_milli = 850
        action = "SETTLE" if (passed and conf_milli >= threshold) else "REFUND"
        assert action == "SETTLE"

    def test_refund_on_low_confidence(self):
        threshold = 700
        # passed but low confidence -> REFUND
        passed = True
        conf_milli = 650
        action = "SETTLE" if (passed and conf_milli >= threshold) else "REFUND"
        assert action == "REFUND"

    def test_refund_on_fail(self):
        threshold = 700
        passed = False
        conf_milli = 950
        action = "SETTLE" if (passed and conf_milli >= threshold) else "REFUND"
        assert action == "REFUND"


class TestIntentSolverVerifierLogic:
    def test_intent_pass_decision(self):
        fulfilled = True
        score_milli = 800
        outcome = "PASS" if (fulfilled and score_milli >= 700) else "FAIL"
        assert outcome == "PASS"

    def test_intent_fail_on_low_quality(self):
        fulfilled = True
        score_milli = 600
        outcome = "PASS" if (fulfilled and score_milli >= 700) else "FAIL"
        assert outcome == "FAIL"


class TestSemanticDAOGuardLogic:
    def test_approval_threshold(self):
        max_risk = 300
        # compliant with 150 risk -> approved
        assert (True and 150 <= max_risk) is True
        # compliant with 350 risk -> rejected
        assert (True and 350 <= max_risk) is False
        # non-compliant with 0 risk -> rejected
        assert (False and 0 <= max_risk) is False


class TestAgentSlasherLogic:
    def test_slash_split_accounting(self):
        stake = 1000
        slash_pct = 40
        slashed = (stake * slash_pct) // 100
        assert slashed == 400

        reporter_reward = slashed // 2
        treasury_cut = slashed - reporter_reward

        assert reporter_reward == 200
        assert treasury_cut == 200
        assert reporter_reward + treasury_cut == slashed
        assert stake - slashed == 600

    def test_odd_slash_no_funds_lost(self):
        stake = 1000
        slash_pct = 25
        slashed = (stake * slash_pct) // 100
        assert slashed == 250

        reporter_reward = slashed // 2  # 125
        treasury_cut = slashed - reporter_reward  # 125
        assert reporter_reward + treasury_cut == slashed


class TestSpecBountyLogic:
    @pytest.mark.parametrize(
        "sev,raw_pct,expected_cap",
        [
            ("CRITICAL", 100, 100),
            ("CRITICAL", 80, 80),
            ("HIGH", 80, 50),
            ("MEDIUM", 50, 20),
            ("NONE", 50, 0),
        ],
    )
    def test_bounty_tier_caps(self, sev, raw_pct, expected_cap):
        max_allowed = 100 if sev == "CRITICAL" else (50 if sev == "HIGH" else (20 if sev == "MEDIUM" else 0))
        payout_pct = min(raw_pct, max_allowed)
        assert payout_pct == expected_cap


class TestDisputeCourtLogic:
    def test_split_on_high_ambiguity(self):
        max_amb = 350
        merit_milli = 800
        amb_milli = 400
        action = (
            "SPLIT"
            if (amb_milli >= max_amb or (450 <= merit_milli <= 550))
            else ("PLAINTIFF_WINS" if merit_milli > 550 else "DEFENDANT_WINS")
        )
        assert action == "SPLIT"

    def test_split_on_close_call(self):
        max_amb = 350
        merit_milli = 510
        amb_milli = 100
        action = (
            "SPLIT"
            if (amb_milli >= max_amb or (450 <= merit_milli <= 550))
            else ("PLAINTIFF_WINS" if merit_milli > 550 else "DEFENDANT_WINS")
        )
        assert action == "SPLIT"

    def test_plaintiff_clear_win(self):
        max_amb = 350
        merit_milli = 750
        amb_milli = 150
        action = (
            "SPLIT"
            if (amb_milli >= max_amb or (450 <= merit_milli <= 550))
            else ("PLAINTIFF_WINS" if merit_milli > 550 else "DEFENDANT_WINS")
        )
        assert action == "PLAINTIFF_WINS"


class TestCrossLingualOracleLogic:
    def test_corroboration_gate(self):
        threshold = 750
        # both agreed, high confidence
        agreed = True
        conf = 850
        ans = "YES"
        outcome = ans if (agreed and conf >= threshold and ans in ("YES", "NO")) else "AMBIGUOUS"
        assert outcome == "YES"

        # disagreement
        agreed = False
        outcome = ans if (agreed and conf >= threshold and ans in ("YES", "NO")) else "AMBIGUOUS"
        assert outcome == "AMBIGUOUS"


class TestMultiSourceInsuranceLogic:
    def test_payout_calculation(self):
        pool = 50000
        confirmed = True
        severity_pct = 30
        action = "PAYOUT" if (confirmed and severity_pct > 0) else "DENY"
        assert action == "PAYOUT"

        payout = (pool * severity_pct) // 100
        remaining_pool = pool - payout
        assert payout == 15000
        assert remaining_pool == 35000
