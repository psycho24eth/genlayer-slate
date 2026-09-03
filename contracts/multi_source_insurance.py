# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 08: MultiSourceInsurance

PURPOSE
  Parametric disaster and event insurance pool. Requires independent corroboration
  across multiple web feeds (e.g. government weather agencies, seismic sensors, news feeds)
  before releasing insurance claim disbursements. Protects pools against single-oracle
  faults and spoofed data.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  fetches the configured web sources and determines whether the parametric condition
  was met, estimating severity from 0 to 100%. Consensus requires agreement on the
  confirmation boolean and that severity assessments align within tolerance.
  Claim payouts are credited only upon successful multi-validator corroboration.

STATE DESIGN
  - Single parametric claim lifecycle: POOL_FUNDED -> CLAIM_EVALUATED -> SETTLED.
  - Strict pull-payment accounting (`claimable: TreeMap[Address, u256]`).
  - Integer percentage scaling ensures deterministic pool balance deductions.
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
    severity_pct: u256
    tolerance_pct: u256
    claimable: TreeMap[Address, u256]

    def __init__(
        self,
        claimant: Address,
        incident_condition: str,
        source_url_1: str,
        source_url_2: str,
        tolerance_pct: int = 25,
    ):
        require(len(incident_condition.strip()) > 0, "empty incident condition")
        require(len(source_url_1.strip()) > 0, "empty source url 1")
        require(len(source_url_2.strip()) > 0, "empty source url 2")
        require(0 < tolerance_pct <= 50, "invalid tolerance percentage")

        self.claimant = claimant
        self.incident_condition = incident_condition.strip()
        self.source_url_1 = source_url_1.strip()
        self.source_url_2 = source_url_2.strip()
        self.pool_balance = u256(0)
        self.claim_settled = False
        self.severity_pct = u256(0)
        self.tolerance_pct = u256(tolerance_pct)

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
        tol = int(self.tolerance_pct)

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
If confirmed, estimate the severity percentage (1 to 100). If unconfirmed or contradictory, confirmed must be false.

Return strict JSON only with no markdown wrapping:
{{
  "confirmed": true or false,
  "severity_pct": <integer between 0 and 100>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            confirmed = bool(data.get("confirmed", False))
            sev = int(data.get("severity_pct", 0))
            sev = max(0, min(100, sev))
            severity_pct = sev if confirmed else 0
            reason = str(data.get("reason", "")).strip()[:120]

            action = "PAYOUT" if (confirmed and severity_pct > 0) else "DENY"
            return canonical(
                {
                    "confirmed": confirmed,
                    "severity_pct": severity_pct,
                    "reason": reason,
                    "action": action,
                }
            )

        principle = (
            "The two validators corroborate the disaster claim across independent feeds. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'confirmed' boolean, "
            f"(2) their severity_pct values differ by at most {tol} percentage points, and "
            "(3) their 'action' values match ('PAYOUT' or 'DENY'). If confirmation diverges, "
            "they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(corroborate_incident, principle)
        parsed = json.loads(agreed)

        confirmed = bool(parsed["confirmed"])
        severity_pct = int(parsed["severity_pct"])
        action = str(parsed["action"])

        expected_action = "PAYOUT" if (confirmed and severity_pct > 0) else "DENY"
        require(action == expected_action, "claim action violates corroboration logic")

        self.claim_settled = True
        self.severity_pct = u256(severity_pct)

        if action == "PAYOUT":
            payout = (current_pool * severity_pct) // 100
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
                "severity_pct": int(self.severity_pct),
                "source_url_1": self.source_url_1,
                "source_url_2": self.source_url_2,
            }
        )

    @gl.public.view
    def get_claimable(self, account: Address) -> int:
        return int(self.claimable.get(account, u256(0)))
