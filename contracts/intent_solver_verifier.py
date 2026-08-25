# contracts/intent_solver_verifier.py
from genlayer import *
import json

@gl.contract
class IntentSolverVerifier:
    """
    Verifies that an off-chain solver's transaction routing fulfilled
    the user's plain-language execution intent (preventing MEV/slippage exploitation).
    """
    user_intent: str
    escrow_bond: u256
    solver: Address
    settled: bool
    balances: TreeMap[Address, u256]

    def __init__(self, solver: Address, user_intent: str):
        self.solver = solver
        self.user_intent = user_intent
        self.escrow_bond = u256(0)
        self.settled = False

    @gl.public.write
    def lock_intent(self) -> None:
        assert gl.message.value > 0, "bond required"
        self.escrow_bond = gl.message.value

    @gl.public.write
    def verify_execution(self, routing_receipt: str) -> None:
        assert not self.settled, "already settled"

        prompt = f"""
        Verify if the solver execution trace satisfied the user intent.

        User Intent:
        {self.user_intent}

        Solver Execution Receipt:
        {routing_receipt[:3000]}

        Did the solver fulfill the intent in good faith without slippage abuse?
        Respond with JSON:
        {{
            "valid": true,
            "notes": "summary"
        }}
        """

        res = json.loads(gl.exec_prompt(prompt).replace("```json", "").replace("```", "").strip())
        if bool(res.get("valid", False)):
            self.balances[self.solver] = self.balances.get(self.solver, u256(0)) + self.escrow_bond
        self.settled = True
        self.escrow_bond = u256(0)

    @gl.public.write
    def withdraw(self) -> None:
        bal = self.balances.get(gl.message.sender, u256(0))
        assert bal > 0, "no funds"
        self.balances[gl.message.sender] = u256(0)
        gl.transfer(gl.message.sender, bal)
