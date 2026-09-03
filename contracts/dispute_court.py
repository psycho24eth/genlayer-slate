# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 06: DisputeCourt

PURPOSE
  Two-party arbitration court with ambiguity-aware variance fallback.
  Arbitrates disputes between counter-parties over agreements, service contracts,
  or financial claims. If the evidence is genuinely ambiguous or evenly balanced,
  the contract avoids arbitrary binary outcomes and safely splits escrow 50/50.
  When one party clearly proves their claim, full escrow is awarded to the prevailing party.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  analyzes the agreement terms, plaintiff claim, and defendant defense.
  Validators assign a plaintiff merit score (0..1000) and an ambiguity metric.
  Consensus requires validators to agree on the merit score within tolerance and to
  unanimously concur on the action category (PLAINTIFF_WINS, DEFENDANT_WINS, SPLIT).
  Settlement proceeds only after consensus lands.

STATE DESIGN
  - Append-only case registry (`cases: DynArray[CaseRecord]`).
  - Strict pull-payment accounting (`claimable: TreeMap[Address, u256]`).
  - Integer milli-units prevent fractional token loss during 50/50 splits.
  - State machine per case: FILED -> SETTLED.

REUSE
  General-purpose arbitration primitive for peer-to-peer commerce, escrow disputes,
  decentralized freelancing platforms, and mutual insurance claims.
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


_MILLI = 1000


@allow_storage
@dataclass
class CaseRecord:
    plaintiff: Address
    defendant: Address
    escrow: u256
    settled: bool
    ruling: str
    merit_milli: u256


class DisputeCourt(gl.Contract):
    max_ambiguity_milli: u256
    tolerance_milli: u256
    cases: DynArray[CaseRecord]
    claimable: TreeMap[Address, u256]

    def __init__(self, max_ambiguity_milli: int = 350, tolerance_milli: int = 200):
        require(0 < max_ambiguity_milli <= 1000, "invalid max ambiguity")
        require(0 < tolerance_milli <= 500, "invalid tolerance")

        self.max_ambiguity_milli = u256(max_ambiguity_milli)
        self.tolerance_milli = u256(tolerance_milli)

    @gl.public.write.payable
    def file_case(
        self,
        defendant: Address,
        agreement_terms: str,
        plaintiff_claim: str,
    ) -> int:
        plaintiff = gl.message.sender_address
        deposit = int(gl.message.value)
        require(deposit > 0, "dispute requires positive escrow deposit")
        require(len(agreement_terms.strip()) > 0, "empty agreement terms")
        require(len(plaintiff_claim.strip()) > 0, "empty plaintiff claim")

        case = CaseRecord(
            plaintiff=plaintiff,
            defendant=defendant,
            escrow=u256(deposit),
            settled=False,
            ruling="FILED",
            merit_milli=u256(500),
        )
        self.cases.append(case)
        return len(self.cases) - 1

    @gl.public.write
    def resolve_case(
        self,
        case_id: int,
        agreement_terms: str,
        plaintiff_claim: str,
        defendant_defense: str,
    ) -> str:
        require(0 <= case_id < len(self.cases), "case not found")
        case = self.cases[case_id]
        require(not case.settled, "case already settled")

        total_escrow = int(case.escrow)
        require(total_escrow > 0, "zero escrow amount")

        terms = agreement_terms.strip()[:1500]
        p_claim = plaintiff_claim.strip()[:1500]
        d_defense = defendant_defense.strip()[:1500]
        max_ambiguity = int(self.max_ambiguity_milli)
        tol = int(self.tolerance_milli)

        def arbitrate() -> str:
            prompt = f"""You are an impartial decentralized court arbitrator.

AGREEMENT TERMS:
{terms}

PLAINTIFF CLAIM AND EVIDENCE:
{p_claim}

DEFENDANT DEFENSE AND COUNTER-EVIDENCE:
{d_defense}

Evaluate the evidence and score the plaintiff merit from 0.0 to 1.0 (1.0 = full plaintiff favor, 0.0 = full defendant favor).
Also evaluate the ambiguity/uncertainty of the case from 0.0 to 1.0.

Return strict JSON only with no markdown wrapping:
{{
  "merit_score": <float 0..1>,
  "ambiguity_score": <float 0..1>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            merit = float(data.get("merit_score", 0.5))
            merit = max(0.0, min(1.0, merit))
            merit_milli = int(round(merit * _MILLI))

            amb = float(data.get("ambiguity_score", 0.0))
            amb = max(0.0, min(1.0, amb))
            amb_milli = int(round(amb * _MILLI))

            reason = str(data.get("reason", "")).strip()[:120]

            if amb_milli >= max_ambiguity or (450 <= merit_milli <= 550):
                action = "SPLIT"
            elif merit_milli > 550:
                action = "PLAINTIFF_WINS"
            else:
                action = "DEFENDANT_WINS"

            return canonical(
                {
                    "merit_milli": merit_milli,
                    "amb_milli": amb_milli,
                    "action": action,
                    "reason": reason,
                }
            )

        principle = (
            "The two validators arbitrate the dispute case. They are EQUIVALENT if and only if: "
            f"(1) their merit_milli values differ by at most {tol}, and (2) their 'action' values "
            "are identical ('PLAINTIFF_WINS', 'DEFENDANT_WINS', or 'SPLIT'). If action diverges, "
            "they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(arbitrate, principle)
        parsed = json.loads(agreed)

        merit_milli = int(parsed["merit_milli"])
        amb_milli = int(parsed["amb_milli"])
        action = str(parsed["action"])
        reason = str(parsed["reason"])

        expected_action = (
            "SPLIT"
            if (amb_milli >= max_ambiguity or (450 <= merit_milli <= 550))
            else ("PLAINTIFF_WINS" if merit_milli > 550 else "DEFENDANT_WINS")
        )
        require(action == expected_action, "ruling violates decision boundaries")

        case.settled = True
        case.escrow = u256(0)
        case.merit_milli = u256(merit_milli)
        case.ruling = f"{action}: {reason}"

        if action == "SPLIT":
            half = total_escrow // 2
            rem = total_escrow - half
            prev_p = int(self.claimable.get(case.plaintiff, u256(0)))
            prev_d = int(self.claimable.get(case.defendant, u256(0)))
            self.claimable[case.plaintiff] = u256(prev_p + half)
            self.claimable[case.defendant] = u256(prev_d + rem)
        elif action == "PLAINTIFF_WINS":
            prev_p = int(self.claimable.get(case.plaintiff, u256(0)))
            self.claimable[case.plaintiff] = u256(prev_p + total_escrow)
        else:
            prev_d = int(self.claimable.get(case.defendant, u256(0)))
            self.claimable[case.defendant] = u256(prev_d + total_escrow)

        return action

    @gl.public.write
    def withdraw(self) -> None:
        bal = int(self.claimable.get(gl.message.sender_address, u256(0)))
        require(bal > 0, "no claimable balance")
        self.claimable[gl.message.sender_address] = u256(0)
        _NativeRecipient(gl.message.sender_address).emit_transfer(value=u256(bal))

    @gl.public.view
    def get_case(self, case_id: int) -> str:
        require(0 <= case_id < len(self.cases), "case not found")
        c = self.cases[case_id]
        return canonical(
            {
                "plaintiff": str(c.plaintiff),
                "defendant": str(c.defendant),
                "escrow": int(c.escrow),
                "settled": c.settled,
                "ruling": c.ruling,
                "merit_milli": int(c.merit_milli),
            }
        )

    @gl.public.view
    def get_claimable(self, account: Address) -> int:
        return int(self.claimable.get(account, u256(0)))
