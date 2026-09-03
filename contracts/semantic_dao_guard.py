# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 03: SemanticDAOGuard

PURPOSE
  Constitutional guard for DAO governance. Audits proposed executive transactions
  and calldata payloads against the DAO's plain-text constitution to detect and block
  Trojan proposals, treasury drains, or rogue parameter changes before execution.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  analyzes the proposal description and execution payload against the constitutional
  articles. Validators must reach consensus on whether the proposal is compliant and
  measure a calibrated risk score (0..1000). A proposal is approved only when validators
  agree it complies with constitutional limits and risk stays strictly below threshold.

STATE DESIGN
  - Immutable constitutional reference set at initialization.
  - Append-only registry of evaluated proposals (`proposals: DynArray[ProposalRecord]`).
  - Storage uses `@allow_storage` dataclasses and strict integer milli-units.
  - Proposals are non-reentrant and deterministically indexed.

REUSE
  Acts as a semantic timelock or pre-execution filter for on-chain DAOs, multisig
  treasuries, protocol parameter upgrades, and council veto mechanisms.
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


_MILLI = 1000


@allow_storage
@dataclass
class ProposalRecord:
    proposer: Address
    title: str
    approved: bool
    risk_score_milli: u256
    reason: str


class SemanticDAOGuard(gl.Contract):
    dao_treasury: Address
    constitution: str
    max_risk_milli: u256
    tolerance_milli: u256
    proposals: DynArray[ProposalRecord]

    def __init__(
        self,
        dao_treasury: Address,
        constitution: str,
        max_risk_milli: int = 300,
        tolerance_milli: int = 200,
    ):
        require(len(constitution.strip()) > 0, "empty constitution")
        require(0 <= max_risk_milli <= 1000, "invalid max risk threshold")
        require(0 < tolerance_milli <= 500, "invalid tolerance")

        self.dao_treasury = dao_treasury
        self.constitution = constitution.strip()
        self.max_risk_milli = u256(max_risk_milli)
        self.tolerance_milli = u256(tolerance_milli)

    @gl.public.write
    def audit_proposal(
        self,
        title: str,
        description: str,
        execution_payload: str,
    ) -> int:
        require(len(title.strip()) > 0, "empty title")
        require(len(description.strip()) > 0, "empty description")
        require(len(execution_payload.strip()) > 0, "empty payload")

        proposer = gl.message.sender_address
        const_text = self.constitution
        max_risk = int(self.max_risk_milli)
        tol = int(self.tolerance_milli)

        t = title.strip()[:100]
        desc = description.strip()[:1500]
        payload = execution_payload.strip()[:1500]

        def evaluate_proposal() -> str:
            prompt = f"""You are an incorruptible constitutional DAO guard.

DAO CONSTITUTION:
{const_text}

PROPOSAL TITLE: {t}
PROPOSAL DESCRIPTION: {desc}
EXECUTION PAYLOAD / RAW ACTIONS: {payload}

Audit whether this proposal violates any constitutional guarantees or poses governance attack risk.

Return strict JSON only with no markdown wrapping:
{{
  "compliant": true or false,
  "risk_score": <float 0..1 representing governance risk>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            compliant = bool(data.get("compliant", False))
            risk = float(data.get("risk_score", 1.0))
            risk = max(0.0, min(1.0, risk))
            risk_milli = int(round(risk * _MILLI))
            reason = str(data.get("reason", "")).strip()[:120]

            approved = compliant and (risk_milli <= max_risk)
            return canonical(
                {
                    "compliant": compliant,
                    "risk_milli": risk_milli,
                    "approved": approved,
                    "reason": reason,
                }
            )

        principle = (
            "The two validators audit the governance proposal against the DAO constitution. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'compliant' boolean, "
            f"(2) their risk_milli values differ by at most {tol}, and (3) their 'approved' "
            "determination matches exactly. If compliance or approval diverges, they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(evaluate_proposal, principle)
        parsed = json.loads(agreed)

        compliant = bool(parsed["compliant"])
        risk_milli = int(parsed["risk_milli"])
        approved = bool(parsed["approved"])
        reason = str(parsed["reason"])

        expected_approved = compliant and (risk_milli <= max_risk)
        require(approved == expected_approved, "approval state violates risk policy")

        rec = ProposalRecord(
            proposer=proposer,
            title=t,
            approved=approved,
            risk_score_milli=u256(risk_milli),
            reason=reason,
        )
        self.proposals.append(rec)
        return len(self.proposals) - 1

    @gl.public.view
    def count(self) -> int:
        return len(self.proposals)

    @gl.public.view
    def is_approved(self, proposal_id: int) -> bool:
        require(0 <= proposal_id < len(self.proposals), "proposal does not exist")
        return self.proposals[proposal_id].approved

    @gl.public.view
    def get_proposal(self, proposal_id: int) -> str:
        require(0 <= proposal_id < len(self.proposals), "proposal does not exist")
        p = self.proposals[proposal_id]
        return canonical(
            {
                "proposer": str(p.proposer),
                "title": p.title,
                "approved": p.approved,
                "risk_score_milli": int(p.risk_score_milli),
                "reason": p.reason,
            }
        )
