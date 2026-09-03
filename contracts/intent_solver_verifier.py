# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 02: IntentSolverVerifier

PURPOSE
  Verifies that an off-chain solver's execution receipt faithfully fulfilled
  a user's natural language transaction intent (e.g., cross-chain swaps, DEX routing,
  MEV protection, execution deadlines) before releasing escrowed funds and solver bonds.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  analyzes the execution trace against the stated intent constraints.
  Validators determine compliance, estimate execution quality, and reach consensus
  on whether the intent was satisfied in good faith without sandwich attacks or
  excessive slippage. Payout or penalization occurs only after consensus is finalized.

STATE DESIGN
  - Dual custody: holds user settlement funds and solver fidelity bond.
  - State machine: CREATED -> FUNDED -> SETTLED.
  - Pull-payment ledger (`claimable: TreeMap[Address, u256]`) for withdrawals.
  - Deterministic invariant checks enforce that funds can never be credited twice.

REUSE
  Foundational primitive for intent-based architectures, ERC-4337 bundler verification,
  cross-chain settlement bridges, and automated DeFi RFQ protocols.
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


class IntentSolverVerifier(gl.Contract):
    user: Address
    solver: Address
    intent_spec: str
    user_deposit: u256
    solver_bond: u256
    settled: bool
    verdict: str
    claimable: TreeMap[Address, u256]
    tolerance_milli: u256

    def __init__(
        self,
        user: Address,
        solver: Address,
        intent_spec: str,
        tolerance_milli: int = 200,
    ):
        require(len(intent_spec.strip()) > 0, "empty intent specification")
        require(0 < tolerance_milli <= 500, "invalid tolerance")

        self.user = user
        self.solver = solver
        self.intent_spec = intent_spec.strip()
        self.user_deposit = u256(0)
        self.solver_bond = u256(0)
        self.settled = False
        self.verdict = "UNSETTLED"
        self.tolerance_milli = u256(tolerance_milli)

    @gl.public.write.payable
    def fund_user_escrow(self) -> None:
        require(gl.message.sender_address == self.user, "only user can fund escrow")
        require(not self.settled, "already settled")
        require(int(gl.message.value) > 0, "must deposit positive value")
        self.user_deposit = u256(int(self.user_deposit) + int(gl.message.value))

    @gl.public.write.payable
    def post_solver_bond(self) -> None:
        require(gl.message.sender_address == self.solver, "only solver can post bond")
        require(not self.settled, "already settled")
        require(int(gl.message.value) > 0, "must deposit positive value")
        self.solver_bond = u256(int(self.solver_bond) + int(gl.message.value))

    @gl.public.write
    def verify_execution(self, routing_receipt: str) -> str:
        require(not self.settled, "already settled")
        require(int(self.user_deposit) > 0, "user escrow not funded")
        require(int(self.solver_bond) > 0, "solver bond not posted")
        require(len(routing_receipt.strip()) > 0, "empty routing receipt")

        intent = self.intent_spec
        receipt = routing_receipt.strip()[:3500]
        tol = int(self.tolerance_milli)

        def evaluate_intent() -> str:
            prompt = f"""You are a decentralized DeFi verifier auditing intent solver execution.

USER INTENT:
{intent}

SOLVER EXECUTION RECEIPT / ON-CHAIN TRACE:
{receipt}

Evaluate whether the solver's routing fulfilled the user's intent faithfully and without exploitative slippage or frontrunning.

Return strict JSON only with no markdown wrapping:
{{
  "fulfilled": true or false,
  "quality_score": <float 0..1 representing satisfaction of constraints>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            fulfilled = bool(data.get("fulfilled", False))
            score = float(data.get("quality_score", 0.0))
            score = max(0.0, min(1.0, score))
            score_milli = int(round(score * _MILLI))
            reason = str(data.get("reason", "")).strip()[:120]

            outcome = "PASS" if (fulfilled and score_milli >= 700) else "FAIL"
            return canonical(
                {
                    "fulfilled": fulfilled,
                    "score_milli": score_milli,
                    "reason": reason,
                    "outcome": outcome,
                }
            )

        principle = (
            "The two validators audit the solver routing receipt. They are EQUIVALENT "
            "if and only if: (1) both agree on the 'fulfilled' boolean, (2) their score_milli "
            f"values differ by at most {tol}, and (3) their 'outcome' fields match ('PASS' or 'FAIL'). "
            "If the pass/fail determination diverges, they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(evaluate_intent, principle)
        parsed = json.loads(agreed)

        fulfilled = bool(parsed["fulfilled"])
        score_milli = int(parsed["score_milli"])
        outcome = str(parsed["outcome"])
        expected_outcome = "PASS" if (fulfilled and score_milli >= 700) else "FAIL"
        require(outcome == expected_outcome, "consequential action violates policy bounds")

        total_escrow = int(self.user_deposit)
        bond = int(self.solver_bond)
        self.user_deposit = u256(0)
        self.solver_bond = u256(0)
        self.settled = True

        if outcome == "PASS":
            self.verdict = "FULFILLED"
            # Solver receives user escrow payment + their bond back
            prev_solver = int(self.claimable.get(self.solver, u256(0)))
            self.claimable[self.solver] = u256(prev_solver + total_escrow + bond)
        else:
            self.verdict = "SLASHED"
            # Solver violated intent: user refunded escrow + awarded solver's slashed bond
            prev_user = int(self.claimable.get(self.user, u256(0)))
            self.claimable[self.user] = u256(prev_user + total_escrow + bond)

        return self.verdict

    @gl.public.write
    def withdraw(self) -> None:
        bal = int(self.claimable.get(gl.message.sender_address, u256(0)))
        require(bal > 0, "no claimable balance")
        self.claimable[gl.message.sender_address] = u256(0)
        _NativeRecipient(gl.message.sender_address).emit_transfer(value=u256(bal))

    @gl.public.view
    def get_status(self) -> str:
        return canonical(
            {
                "user": str(self.user),
                "solver": str(self.solver),
                "settled": self.settled,
                "verdict": self.verdict,
                "user_deposit": int(self.user_deposit),
                "solver_bond": int(self.solver_bond),
            }
        )

    @gl.public.view
    def get_claimable(self, account: Address) -> int:
        return int(self.claimable.get(account, u256(0)))
