# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 08: MultiSourceInsurance

PURPOSE
  Parametric disaster and event insurance pool. Requires independent corroboration
  across multiple web feeds (e.g. government weather agencies, seismic sensors, news feeds)
  before releasing insurance claim disbursements based on exact canonical disaster tiers.
  Protects pools against single-oracle faults and spoofed data.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  fetches the configured web sources and determines whether the parametric condition
  was met, assigning an exact canonical disaster severity tier:
  CATASTROPHIC (100% of pool), SEVERE (50% of pool), MODERATE (25% of pool), or NONE (0%).
  Consensus requires exact categorical agreement on both the confirmation boolean
  and the canonical severity tier string. Claim payouts are credited strictly from
  the agreed canonical bucket, guaranteeing 100% deterministic pool deductions.

STATE DESIGN
  - Single parametric claim lifecycle: POOL_FUNDED -> CLAIM_EVALUATED -> SETTLED.
  - Strict pull-payment accounting (claimable: TreeMap[Address, u256]).
  - Evaluated severity tier stored as canonical string (severity_tier: str).
  - Integer percentage scaling from canonical buckets ensures deterministic pool balance deductions.
  - Non-deterministic web fetches are fully isolated in error-guarded closures.

REUSE
  Applicable to flight delay insurance, parametric hurricane/flood coverage,
  crop yield disaster pools, and satellite-verified maritime loss contracts.
"""

from genlayer import *
import json

try:
    _SlateError = gl.vm.UserError
except Exception:
    _SlateError = Exception


def require(condition: bool, message: str) -> None:
    if not condition:
        raise _SlateError(message)


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


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


@gl.evm.contract_interface
class _NativeRecipient:
    class View:
        pass

    class Write:
        pass


def send_native(recipient: Address, amount: int) -> None:
    _NativeRecipient(recipient).emit_transfer(value=u256(amount))


class MultiSourceInsurance(gl.Contract):
    claimant: Address
    incident_condition: str
    source_url_1: str
    source_url_2: str
    pool_balance: u256
    claim_settled: bool
    severity_tier: str
    claimable: TreeMap[Address, u256]

    def __init__(
        self,
        claimant: Address,
        incident_condition: str,
        source_url_1: str,
        source_url_2: str,
    ):
        require(len(incident_condition.strip()) > 0, "empty incident condition")
        require(len(source_url_1.strip()) > 0, "empty source url 1")
        require(len(source_url_2.strip()) > 0, "empty source url 2")

        self.claimant = claimant
        self.incident_condition = incident_condition.strip()
        self.source_url_1 = source_url_1.strip()
        self.source_url_2 = source_url_2.strip()
        self.pool_balance = u256(0)
        self.claim_settled = False
        self.severity_tier = "NONE"

    @gl.public.write.payable
    def fund_pool(self) -> None:
        require(int(gl.message.value) > 0, "deposit must be positive")
        self.pool_balance = u256(int(self.pool_balance) + int(gl.message.value))

    @gl.public.write
    def evaluate_claim(self) -> str:
        require(not self.claim_settled, "claim already settled")
        current_pool = int(self.pool_balance)
        require(current_pool > 0, "insurance pool has no funds")

        cond = self.incident_condition
        url1 = self.source_url_1
        url2 = self.source_url_2

        def corroborate_incident() -> str:
            try:
                feed_1 = gl.nondet.web.render(url1, mode="text")
                body_1 = feed_1[:2500] if feed_1 else "[EMPTY FEED 1]"
            except Exception as exc:
                body_1 = f"[FETCH 1 FAILED: {exc}]"[:200]

            try:
                feed_2 = gl.nondet.web.render(url2, mode="text")
                body_2 = feed_2[:2500] if feed_2 else "[EMPTY FEED 2]"
            except Exception as exc:
                body_2 = f"[FETCH 2 FAILED: {exc}]"[:200]

            prompt = f"""You are a parametric insurance adjustor verifying an incident condition.

PARAMETRIC INCIDENT CONDITION:
{cond}

DATA FEED 1 ({url1}):
{body_1}

DATA FEED 2 ({url2}):
{body_2}

Verify whether BOTH independent data feeds corroborate that the incident occurred.
If confirmed, assign an exact canonical disaster severity tier:
- CATASTROPHIC: Total devastation or extreme catastrophe meeting top threshold (100% of pool).
- SEVERE: Major widespread damage or intense incident (50% of pool).
- MODERATE: Significant localized damage meeting minimum threshold (25% of pool).
- NONE: Incident not confirmed, contradictory feeds, or below thresholds (0% payout).

Return strict JSON only with no markdown wrapping:
{{
  "confirmed": true or false,
  "tier": "CATASTROPHIC" | "SEVERE" | "MODERATE" | "NONE",
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            confirmed = bool(data.get("confirmed", False))
            tier = str(data.get("tier", "NONE")).strip().upper()
            if tier not in ("CATASTROPHIC", "SEVERE", "MODERATE", "NONE"):
                tier = "NONE"

            if not confirmed or tier == "NONE":
                confirmed = False
                tier = "NONE"

            reason = str(data.get("reason", "")).strip()[:120]
            action = "PAYOUT" if (confirmed and tier != "NONE") else "DENY"
            return canonical(
                {
                    "confirmed": confirmed,
                    "tier": tier,
                    "reason": reason,
                    "action": action,
                }
            )

        principle = (
            "The two validators corroborate the disaster claim across independent feeds. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'confirmed' boolean, "
            "(2) their 'tier' values match exactly ('CATASTROPHIC', 'SEVERE', 'MODERATE', or 'NONE'), and "
            "(3) their 'action' values match ('PAYOUT' or 'DENY'). If confirmation or tier determination diverges, "
            "they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(corroborate_incident, principle)
        parsed = json.loads(agreed)

        confirmed = bool(parsed["confirmed"])
        tier = str(parsed["tier"])
        action = str(parsed["action"])

        expected_action = "PAYOUT" if (confirmed and tier != "NONE") else "DENY"
        require(action == expected_action, "claim action violates corroboration logic")
        require(tier in ("CATASTROPHIC", "SEVERE", "MODERATE", "NONE"), "invalid disaster tier")

        self.claim_settled = True
        self.severity_tier = tier

        if action == "PAYOUT":
            pct = 100 if tier == "CATASTROPHIC" else (50 if tier == "SEVERE" else (25 if tier == "MODERATE" else 0))
            require(pct > 0, "positive payout percentage required")

            payout = (current_pool * pct) // 100
            self.pool_balance = u256(current_pool - payout)
            prev_claimant = int(self.claimable.get(self.claimant, u256(0)))
            self.claimable[self.claimant] = u256(prev_claimant + payout)
            return "PAID"

        return "DENIED"

    @gl.public.write
    def withdraw(self) -> None:
        bal = int(self.claimable.get(gl.message.sender_address, u256(0)))
        require(bal > 0, "no claimable balance")
        self.claimable[gl.message.sender_address] = u256(0)
        _NativeRecipient(gl.message.sender_address).emit_transfer(value=u256(bal))

    @gl.public.view
    def get_details(self) -> str:
        return canonical(
            {
                "claimant": str(self.claimant),
                "incident_condition": self.incident_condition,
                "pool_balance": int(self.pool_balance),
                "claim_settled": self.claim_settled,
                "severity_tier": self.severity_tier,
                "source_url_1": self.source_url_1,
                "source_url_2": self.source_url_2,
            }
        )

    @gl.public.view
    def get_claimable(self, account: Address) -> int:
        return int(self.claimable.get(account, u256(0)))
