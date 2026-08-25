# contracts/spec_bounty.py
from genlayer import *
import json

@gl.contract
class SpecBounty:
    """
    Bounty pool for issues and security submissions.
    Validators evaluate submitted reports against the project's plain-text scope policy.
    """

    def __init__(self, owner: str, scope: str):
        self.owner: str = owner
        self.scope: str = scope
        self.pool: int = 0
        self.balances: dict[str, int] = {}
        self.claims: dict[int, dict] = {}
        self.claim_counter: int = 0

    @gl.public.write
    def fund(self) -> None:
        assert gl.message.value > 0, "zero value"
        self.pool += gl.message.value

    @gl.public.write
    def submit_claim(self, summary: str, proof: str) -> int:
        assert self.pool > 0, "empty pool"
        
        claim_id = self.claim_counter
        self.claim_counter += 1

        prompt = f"""
        Review this bounty submission against the program scope.
        
        Scope:
        {self.scope}
        
        Submission:
        Title: {summary}
        Details: {proof[:3500]}
        
        Classify severity and reward percentage:
        - Critical: 100%
        - High: 50%
        - Medium: 20%
        - Low / Out of scope: 0%
        
        Return JSON:
        {{
            "valid": true,
            "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "NONE",
            "payout_pct": 0 to 100,
            "notes": "brief comment"
        }}
        """

        data = json.loads(gl.exec_prompt(prompt))
        valid = bool(data.get("valid", False))
        payout_pct = min(100, max(0, int(data.get("payout_pct", 0))))

        reward = 0
        if valid and payout_pct > 0:
            reward = (self.pool * payout_pct) // 100
            self.pool -= reward
            self.balances[gl.message.sender] = self.balances.get(gl.message.sender, 0) + reward

        self.claims[claim_id] = {
            "author": gl.message.sender,
            "summary": summary,
            "reward": reward,
            "severity": data.get("severity", "NONE"),
            "notes": data.get("notes", "")
        }

        return claim_id

    @gl.public.write
    def withdraw(self) -> None:
        bal = self.balances.get(gl.message.sender, 0)
        assert bal > 0, "no funds"
        self.balances[gl.message.sender] = 0
        gl.transfer(gl.message.sender, bal)
