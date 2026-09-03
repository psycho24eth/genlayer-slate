# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 05: SpecBounty

PURPOSE
  Autonomous bug bounty pool that evaluates security vulnerability submissions
  against a plain-text program scope policy. Automates triage, categorizes severity,
  and distributes rewards according to severity tier.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  analyzes the submission details and proof-of-concept against the program scope.
  Validators must agree on validity, severity tier (CRITICAL, HIGH, MEDIUM, NONE),
  and recommended reward percentage within a configured tolerance.
  Rewards are calculated and credited only after consensus is finalized.

STATE DESIGN
  - Pool balance held in contract custody (`pool_balance: u256`).
  - Immutable program scope document.
  - Append-only registry of evaluated claims (`claims: DynArray[BountyClaim]`).
  - Strict pull-payment accounting (`claimable: TreeMap[Address, u256]`).

REUSE
  Usable for automated bug bounties, open-source vulnerability reward programs,
  hackathon prize judging, and algorithmic code security competitions.
"""

from genlayer import *
import json
from dataclasses import dataclass

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


@allow_storage
@dataclass
class BountyClaim:
    author: Address
    summary: str
    reward: u256
    severity: str
    valid: bool


class SpecBounty(gl.Contract):
    owner: Address
    scope: str
    pool_balance: u256
    tolerance_pct: u256
    claims: DynArray[BountyClaim]
    claimable: TreeMap[Address, u256]

    def __init__(self, owner: Address, scope: str, tolerance_pct: int = 20):
        require(len(scope.strip()) > 0, "empty scope policy")
        require(0 < tolerance_pct <= 50, "invalid tolerance percentage")

        self.owner = owner
        self.scope = scope.strip()
        self.pool_balance = u256(0)
        self.tolerance_pct = u256(tolerance_pct)

    @gl.public.write.payable
    def fund_pool(self) -> None:
        require(int(gl.message.value) > 0, "deposit must be positive")
        self.pool_balance = u256(int(self.pool_balance) + int(gl.message.value))

    @gl.public.write
    def submit_claim(self, summary: str, proof_details: str) -> int:
        current_pool = int(self.pool_balance)
        require(current_pool > 0, "bounty pool has no funds")
        require(len(summary.strip()) > 0, "empty summary")
        require(len(proof_details.strip()) > 0, "empty proof details")

        author = gl.message.sender_address
        scope_text = self.scope
        tol = int(self.tolerance_pct)
        sum_text = summary.strip()[:150]
        details = proof_details.strip()[:3000]

        def evaluate_submission() -> str:
            prompt = f"""You are a senior security researcher triaging a bug bounty claim.

PROGRAM SCOPE:
{scope_text}

SUBMISSION SUMMARY: {sum_text}
PROOF AND REPRODUCTION DETAILS:
{details}

Evaluate whether this vulnerability is valid and within scope.
Assign a severity tier and payout percentage:
- CRITICAL: valid, severe impact (up to 100%)
- HIGH: valid, major impact (up to 50%)
- MEDIUM: valid, moderate impact (up to 20%)
- NONE: invalid, duplicate, or out-of-scope (0%)

Return strict JSON only with no markdown wrapping:
{{
  "valid": true or false,
  "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "NONE",
  "payout_pct": <integer 0 to 100>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            valid = bool(data.get("valid", False))
            sev = str(data.get("severity", "NONE")).strip().upper()
            if sev not in ("CRITICAL", "HIGH", "MEDIUM", "NONE"):
                sev = "NONE"

            pct = int(data.get("payout_pct", 0))
            pct = max(0, min(100, pct))
            if not valid or sev == "NONE":
                pct = 0

            max_allowed = 100 if sev == "CRITICAL" else (50 if sev == "HIGH" else (20 if sev == "MEDIUM" else 0))
            payout_pct = min(pct, max_allowed)
            reason = str(data.get("reason", "")).strip()[:120]

            return canonical(
                {
                    "valid": valid,
                    "severity": sev,
                    "payout_pct": payout_pct,
                    "reason": reason,
                }
            )

        principle = (
            "The two validators triage the bug bounty claim against the program scope. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'valid' boolean, "
            "(2) their 'severity' strings match, and (3) their payout_pct values differ by "
            f"at most {tol} percentage points. If validity or severity tier diverges, they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(evaluate_submission, principle)
        parsed = json.loads(agreed)

        valid = bool(parsed["valid"])
        sev = str(parsed["severity"])
        payout_pct = int(parsed["payout_pct"])

        max_allowed = 100 if sev == "CRITICAL" else (50 if sev == "HIGH" else (20 if sev == "MEDIUM" else 0))
        require(payout_pct <= max_allowed, "payout percentage exceeds tier cap")

        reward = 0
        if valid and payout_pct > 0:
            reward = (current_pool * payout_pct) // 100
            self.pool_balance = u256(current_pool - reward)
            prev_author = int(self.claimable.get(author, u256(0)))
            self.claimable[author] = u256(prev_author + reward)

        claim = BountyClaim(
            author=author,
            summary=sum_text,
            reward=u256(reward),
            severity=sev,
            valid=valid,
        )
        self.claims.append(claim)
        return len(self.claims) - 1

    @gl.public.write
    def withdraw(self) -> None:
        bal = int(self.claimable.get(gl.message.sender_address, u256(0)))
        require(bal > 0, "no claimable balance")
        self.claimable[gl.message.sender_address] = u256(0)
        _NativeRecipient(gl.message.sender_address).emit_transfer(value=u256(bal))

    @gl.public.view
    def get_pool_balance(self) -> int:
        return int(self.pool_balance)

    @gl.public.view
    def get_claimable(self, account: Address) -> int:
        return int(self.claimable.get(account, u256(0)))

    @gl.public.view
    def count(self) -> int:
        return len(self.claims)
