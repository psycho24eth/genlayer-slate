# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 02: IntentSolverVerifier

PURPOSE
  Verifies that an off-chain solver's execution faithfully fulfilled a user's natural
  language transaction intent (e.g., cross-chain swaps, DEX routing, MEV protection,
  execution deadlines) before releasing escrowed funds and solver bonds.
  Fetches authoritative transaction evidence directly from block explorer or RPC endpoints
  inside the non-deterministic verification flow rather than trusting caller-written receipts.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  fetches the authoritative on-chain transaction evidence from the specified endpoint,
  validates on-chain confirmation against the expected transaction hash, and audits the
  execution details against the stated intent constraints.
  Validators reach exact categorical consensus on whether the intent was satisfied in good faith
  without sandwich attacks or excessive slippage (outcome: PASS vs FAIL). Payout or bond
  slashing occurs strictly based on the agreed categorical verdict.

STATE DESIGN
  - Dual custody: holds user settlement funds and solver fidelity bond.
  - State machine: CREATED -> FUNDED -> SETTLED.
  - Pull-payment ledger (claimable: TreeMap[Address, u256]) for withdrawals.
  - Direct web evidence acquisition prevents spoofed or fabricated solver receipts.
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


class IntentSolverVerifier(gl.Contract):
    user: Address
    solver: Address
    intent_spec: str
    user_deposit: u256
    solver_bond: u256
    settled: bool
    verdict: str
    claimable: TreeMap[Address, u256]

    def __init__(
        self,
        user: Address,
        solver: Address,
        intent_spec: str,
    ):
        require(len(intent_spec.strip()) > 0, "empty intent specification")

        self.user = user
        self.solver = solver
        self.intent_spec = intent_spec.strip()
        self.user_deposit = u256(0)
        self.solver_bond = u256(0)
        self.settled = False
        self.verdict = "UNSETTLED"

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
    def verify_execution(self, tx_hash: str, evidence_url: str) -> str:
        require(not self.settled, "already settled")
        require(int(self.user_deposit) > 0, "user escrow not funded")
        require(int(self.solver_bond) > 0, "solver bond not posted")
        require(len(tx_hash.strip()) > 0, "empty transaction hash")
        require(len(evidence_url.strip()) > 0, "empty evidence url")

        intent = self.intent_spec
        tx = tx_hash.strip()
        url = evidence_url.strip()

        def evaluate_execution() -> str:
            try:
                page_content = gl.nondet.web.render(url, mode="text")
                body = page_content[:3500] if page_content else "[EMPTY EVIDENCE FEED]"
            except Exception as exc:
                body = f"[FETCH EVIDENCE FAILED: {exc}]"[:300]

            prompt = f"""You are a decentralized DeFi verifier auditing intent solver execution.

USER INTENT CONSTRAINTS:
{intent}

EXPECTED TRANSACTION HASH:
{tx}

AUTHORITATIVE ON-CHAIN EXECUTION EVIDENCE ({url}):
{body}

Audit the authoritative evidence to verify:
1. The transaction confirmed successfully on-chain and matches the expected transaction hash ({tx}).
2. The execution fulfilled the user's intent constraints faithfully without exploitative slippage, sandwich attacks, or frontrunning.

Return strict JSON only with no markdown wrapping:
{{
  "confirmed": true or false,
  "fulfilled": true or false,
  "outcome": "PASS" | "FAIL",
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            confirmed = bool(data.get("confirmed", False))
            fulfilled = bool(data.get("fulfilled", False))
            outcome = str(data.get("outcome", "FAIL")).strip().upper()
            if outcome not in ("PASS", "FAIL"):
                outcome = "FAIL"

            if not (confirmed and fulfilled):
                outcome = "FAIL"

            reason = str(data.get("reason", "")).strip()[:120]
            return canonical(
                {
                    "confirmed": confirmed,
                    "fulfilled": fulfilled,
                    "outcome": outcome,
                    "reason": reason,
                }
            )

        principle = (
            "The two validators audit the authoritative on-chain execution evidence against the user's intent. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'confirmed' boolean, "
            "(2) both agree on the 'fulfilled' boolean, and (3) their 'outcome' values match exactly ('PASS' or 'FAIL'). "
            "If the categorical outcome diverges, they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(evaluate_execution, principle)
        parsed = json.loads(agreed)

        confirmed = bool(parsed["confirmed"])
        fulfilled = bool(parsed["fulfilled"])
        outcome = str(parsed["outcome"])

        expected_outcome = "PASS" if (confirmed and fulfilled) else "FAIL"
        require(outcome == expected_outcome, "consequential action violates verification bounds")
        require(outcome in ("PASS", "FAIL"), "invalid outcome")

        total_escrow = int(self.user_deposit)
        bond = int(self.solver_bond)
        self.user_deposit = u256(0)
        self.solver_bond = u256(0)
        self.settled = True

        if outcome == "PASS":
            self.verdict = "FULFILLED"
            prev_solver = int(self.claimable.get(self.solver, u256(0)))
            self.claimable[self.solver] = u256(prev_solver + total_escrow + bond)
        else:
            self.verdict = "SLASHED"
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
