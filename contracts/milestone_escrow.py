# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 01: MilestoneEscrow

PURPOSE
  Holds client funds in escrow for a freelance or vendor deliverable.
  Validators fetch live deliverable evidence from a target URL (e.g. GitHub release,
  hosted documentation, API response) and evaluate whether it satisfies the
  plain-text milestone specification before releasing payment.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  fetches the evidence URL and prompts an LLM to evaluate the deliverable against
  the specification. The prompt outputs a boolean pass flag, a confidence score, and
  a rationale. Validators must agree on the pass/fail outcome and their confidence
  scores must fall within the configured tolerance window. If consensus cannot be
  reached or confidence falls below threshold, the escrow safely refunds the client.

STATE DESIGN
  - Strict pull-payment ledger (`claimable: TreeMap[Address, u256]`) isolates accounting.
  - Funds are held in contract custody until evaluation lands.
  - Linear lifecycle: PENDING -> SUBMITTED -> SETTLED | REFUNDED.
  - Non-deterministic web access and prompt evaluation are quarantined in closures;
    state and balance mutations are strictly deterministic and independently validated.

REUSE
  Usable for bounty payouts, freelance milestone escrows, grant tranches, and
  automated vendor settlement where delivery can be verified via public web endpoints.
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


_MILLI = 1000


class MilestoneEscrow(gl.Contract):
    client: Address
    contractor: Address
    spec: str
    evidence_url: str
    escrow_amount: u256
    status: str
    verdict_notes: str
    confidence_threshold_milli: u256
    tolerance_milli: u256
    claimable: TreeMap[Address, u256]

    def __init__(
        self,
        client: Address,
        contractor: Address,
        spec: str,
        evidence_url: str,
        confidence_threshold_milli: int = 700,
        tolerance_milli: int = 250,
    ):
        require(len(spec.strip()) > 0, "empty specification")
        require(len(evidence_url.strip()) > 0, "empty evidence url")
        require(0 < confidence_threshold_milli <= 1000, "invalid confidence threshold")
        require(0 < tolerance_milli <= 500, "invalid tolerance")

        self.client = client
        self.contractor = contractor
        self.spec = spec.strip()
        self.evidence_url = evidence_url.strip()
        self.escrow_amount = u256(0)
        self.status = "PENDING"
        self.verdict_notes = ""
        self.confidence_threshold_milli = u256(confidence_threshold_milli)
        self.tolerance_milli = u256(tolerance_milli)

    @gl.public.write.payable
    def lock_funds(self) -> None:
        require(gl.message.sender_address == self.client, "only client can fund")
        require(self.status == "PENDING", "contract not in pending state")
        require(int(gl.message.value) > 0, "deposit must be positive")

        self.escrow_amount = u256(int(self.escrow_amount) + int(gl.message.value))

    @gl.public.write
    def submit(self) -> None:
        require(gl.message.sender_address == self.contractor, "only contractor can submit")
        require(self.status == "PENDING", "already submitted or settled")
        require(int(self.escrow_amount) > 0, "escrow is not funded")

        self.status = "SUBMITTED"

    @gl.public.write
    def evaluate(self) -> str:
        require(self.status == "SUBMITTED", "milestone must be submitted")
        require(int(self.escrow_amount) > 0, "no escrow balance")

        target_url = self.evidence_url
        spec_text = self.spec
        threshold = int(self.confidence_threshold_milli)
        tol = int(self.tolerance_milli)

        def verify_deliverable() -> str:
            try:
                page_content = gl.nondet.web.render(target_url, mode="text")
                body = page_content[:3000] if page_content else "[EMPTY WEB PAGE]"
            except Exception as exc:
                body = f"[FETCH FAILED: {exc}]"[:200]

            prompt = f"""You are an objective auditor verifying a deliverable against a specification.

SPECIFICATION:
{spec_text}

EVIDENCE CONTENT FROM {target_url}:
{body}

Determine whether the evidence proves the milestone specification has been fully met.
If the fetch failed or evidence is empty, passed must be false with low confidence.

Return strict JSON only with no markdown wrapping:
{{
  "passed": true or false,
  "confidence": <float 0..1 representing certainty>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            passed = bool(data.get("passed", False))
            conf = float(data.get("confidence", 0.0))
            conf = max(0.0, min(1.0, conf))
            conf_milli = int(round(conf * _MILLI))
            reason = str(data.get("reason", "")).strip()[:120]

            action = "SETTLE" if (passed and conf_milli >= threshold) else "REFUND"
            return canonical(
                {
                    "passed": passed,
                    "confidence_milli": conf_milli,
                    "reason": reason,
                    "action": action,
                }
            )

        principle = (
            "The two validators audit the milestone evidence deliverable. They are EQUIVALENT "
            "if and only if: (1) both agree on the 'passed' boolean, (2) their confidence_milli "
            f"values differ by at most {tol}, and (3) their 'action' values are identical ('SETTLE' or 'REFUND'). "
            "If the pass determination differs or actions diverge, they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(verify_deliverable, principle)
        parsed = json.loads(agreed)

        passed = bool(parsed["passed"])
        conf_milli = int(parsed["confidence_milli"])
        action = str(parsed["action"])
        reason = str(parsed["reason"])

        expected_action = "SETTLE" if (passed and conf_milli >= threshold) else "REFUND"
        require(action == expected_action, "consequential action violates policy bounds")

        payout = int(self.escrow_amount)
        self.escrow_amount = u256(0)
        self.verdict_notes = reason

        if action == "SETTLE":
            self.status = "SETTLED"
            prev = int(self.claimable.get(self.contractor, u256(0)))
            self.claimable[self.contractor] = u256(prev + payout)
        else:
            self.status = "REFUNDED"
            prev = int(self.claimable.get(self.client, u256(0)))
            self.claimable[self.client] = u256(prev + payout)

        return self.status

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
                "client": str(self.client),
                "contractor": str(self.contractor),
                "status": self.status,
                "escrow_amount": int(self.escrow_amount),
                "evidence_url": self.evidence_url,
                "verdict_notes": self.verdict_notes,
            }
        )

    @gl.public.view
    def get_claimable(self, account: Address) -> int:
        return int(self.claimable.get(account, u256(0)))
