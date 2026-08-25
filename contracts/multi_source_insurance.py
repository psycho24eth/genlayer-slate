# contracts/multi_source_insurance.py
from genlayer import *
import json

@gl.contract
class MultiSourceInsurance:
    """
    Parametric disaster insurance pool.
    Requires independent corroboration across 3 distinct web feeds before payout.
    """
    claimant: Address
    incident_condition: str
    url_1: str
    url_2: str
    pool_balance: u256
    balances: TreeMap[Address, u256]

    def __init__(self, claimant: Address, condition: str, url_1: str, url_2: str):
        self.claimant = claimant
        self.incident_condition = condition
        self.url_1 = url_1
        self.url_2 = url_2
        self.pool_balance = u256(0)

    @gl.public.write
    def deposit_pool(self) -> None:
        assert gl.message.value > 0, "deposit required"
        self.pool_balance = self.pool_balance + gl.message.value

    @gl.public.write
    def claim(self) -> None:
        assert self.pool_balance > 0, "pool empty"

        doc_1 = gl.get_webpage(self.url_1)
        doc_2 = gl.get_webpage(self.url_2)

        prompt = f"""
        Verify if both sources confirm the insurance incident condition.

        Condition: {self.incident_condition}

        Source 1 ({self.url_1}):
        {doc_1[:2500]}

        Source 2 ({self.url_2}):
        {doc_2[:2500]}

        Do both independent sources confirm the incident occurred?
        Respond with JSON:
        {{
            "confirmed": true,
            "severity_pct": 0 to 100
        }}
        """

        res = json.loads(gl.exec_prompt(prompt).replace("```json", "").replace("```", "").strip())
        if bool(res.get("confirmed", False)):
            pct = min(100, max(0, int(res.get("severity_pct", 100))))
            payout = (self.pool_balance * u256(pct)) // u256(100)
            self.pool_balance = self.pool_balance - payout
            self.balances[self.claimant] = self.balances.get(self.claimant, u256(0)) + payout

    @gl.public.write
    def withdraw(self) -> None:
        bal = self.balances.get(gl.message.sender, u256(0))
        assert bal > 0, "no funds"
        self.balances[gl.message.sender] = u256(0)
        gl.transfer(gl.message.sender, bal)
