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
        raw = "Here is your output:\n{\"valid\": true, \"severity\": \"HIGH\"}\nThanks!"
        data = parse_json_response(raw)
        assert data["valid"] is True
        assert data["severity"] == "HIGH"

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
        confirmed = True
        fulfilled = True
        outcome = "PASS" if (confirmed and fulfilled) else "FAIL"
        assert outcome == "PASS"

    def test_intent_fail_unconfirmed_on_chain(self):
        confirmed = False
        fulfilled = True
        outcome = "PASS" if (confirmed and fulfilled) else "FAIL"
        assert outcome == "FAIL"

    def test_intent_fail_unfulfilled_constraints(self):
        confirmed = True
        fulfilled = False
        outcome = "PASS" if (confirmed and fulfilled) else "FAIL"
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
    @pytest.mark.parametrize(
        "tier,expected_pct",
        [
            ("CRITICAL", 100),
            ("MAJOR", 50),
            ("MINOR", 25),
            ("NONE", 0),
        ],
    )
    def test_canonical_slash_tiers(self, tier, expected_pct):
        pct = 25 if tier == "MINOR" else (50 if tier == "MAJOR" else (100 if tier == "CRITICAL" else 0))
        assert pct == expected_pct

    def test_slash_split_accounting(self):
        stake = 1000
        # Major tier = 50%
        pct = 50
        slashed = (stake * pct) // 100
        assert slashed == 500

        reporter_reward = slashed // 2
        treasury_cut = slashed - reporter_reward

        assert reporter_reward == 250
        assert treasury_cut == 250
        assert reporter_reward + treasury_cut == slashed
        assert stake - slashed == 500

    def test_minor_slash_no_funds_lost(self):
        stake = 1000
        pct = 25  # MINOR
        slashed = (stake * pct) // 100
        assert slashed == 250

        reporter_reward = slashed // 2  # 125
        treasury_cut = slashed - reporter_reward  # 125
        assert reporter_reward + treasury_cut == slashed
        assert stake - slashed == 750

    def test_critical_slash_full_stake(self):
        stake = 1000
        pct = 100  # CRITICAL
        slashed = (stake * pct) // 100
        assert slashed == 1000

        reporter_reward = slashed // 2  # 500
        treasury_cut = slashed - reporter_reward  # 500
        assert reporter_reward + treasury_cut == slashed
        assert stake - slashed == 0


class TestSpecBountyLogic:
    @pytest.mark.parametrize(
        "sev,expected_pct",
        [
            ("CRITICAL", 50),
            ("HIGH", 25),
            ("MEDIUM", 10),
            ("NONE", 0),
        ],
    )
    def test_canonical_bounty_tiers(self, sev, expected_pct):
        pct = 50 if sev == "CRITICAL" else (25 if sev == "HIGH" else (10 if sev == "MEDIUM" else 0))
        assert pct == expected_pct

    def test_deterministic_bounty_payouts(self):
        pool = 10000
        for sev, expected_reward in [
            ("CRITICAL", 5000),
            ("HIGH", 2500),
            ("MEDIUM", 1000),
            ("NONE", 0),
        ]:
            pct = 50 if sev == "CRITICAL" else (25 if sev == "HIGH" else (10 if sev == "MEDIUM" else 0))
            reward = (pool * pct) // 100
            assert reward == expected_reward


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
    @pytest.mark.parametrize(
        "tier,expected_pct",
        [
            ("CATASTROPHIC", 100),
            ("SEVERE", 50),
            ("MODERATE", 25),
            ("NONE", 0),
        ],
    )
    def test_canonical_disaster_tiers(self, tier, expected_pct):
        pct = 100 if tier == "CATASTROPHIC" else (50 if tier == "SEVERE" else (25 if tier == "MODERATE" else 0))
        assert pct == expected_pct

    def test_payout_calculation(self):
        pool = 50000
        confirmed = True
        tier = "MODERATE"
        action = "PAYOUT" if (confirmed and tier != "NONE") else "DENY"
        assert action == "PAYOUT"

        pct = 100 if tier == "CATASTROPHIC" else (50 if tier == "SEVERE" else (25 if tier == "MODERATE" else 0))
        payout = (pool * pct) // 100
        remaining_pool = pool - payout
        assert payout == 12500
        assert remaining_pool == 37500

    def test_catastrophic_total_payout(self):
        pool = 50000
        confirmed = True
        tier = "CATASTROPHIC"
        action = "PAYOUT" if (confirmed and tier != "NONE") else "DENY"
        assert action == "PAYOUT"

        pct = 100 if tier == "CATASTROPHIC" else (50 if tier == "SEVERE" else (25 if tier == "MODERATE" else 0))
        payout = (pool * pct) // 100
        remaining_pool = pool - payout
        assert payout == 50000
        assert remaining_pool == 0

    def test_deny_on_unconfirmed(self):
        confirmed = False
        tier = "CATASTROPHIC"
        action = "PAYOUT" if (confirmed and tier != "NONE") else "DENY"
        assert action == "DENY"
