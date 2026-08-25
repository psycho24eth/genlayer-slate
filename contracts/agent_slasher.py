# contracts/agent_slasher.py
from genlayer import *
import json

@gl.contract
class AgentSlasher:
    """
    Staking registry for off-chain automation bots.
    Bots deposit collateral alongside an operating policy.
    If a bot performs an unaligned action, anyone can submit the trace for slash evaluation.
    """

    def __init__(self, treasury: str):
        self.treasury: str = treasury
        self.stakes: dict[str, int] = {}
        self.policies: dict[str, str] = {}
        self.balances: dict[str, int] = {}

    @gl.public.write
    def register(self, policy: str) -> None:
        assert gl.message.value > 0, "deposit required"
        self.stakes[gl.message.sender] = self.stakes.get(gl.message.sender, 0) + gl.message.value
        self.policies[gl.message.sender] = policy

    @gl.public.write
    def slash(self, agent: str, incident_log: str) -> None:
        assert agent in self.stakes and self.stakes[agent] > 0, "no stake"
        policy = self.policies[agent]

        prompt = f"""
        Audit this automated agent incident log against its declared operational policy.
        
        Policy:
        {policy}
        
        Incident Log:
        {incident_log[:3500]}
        
        Did the agent break its operating rules?
        
        Return JSON:
        {{
            "violation": true,
            "slash_pct": 0 to 100,
            "reason": "summary"
        }}
        """

        res = json.loads(gl.exec_prompt(prompt))
        violation = bool(res.get("violation", False))
        slash_pct = min(100, max(0, int(res.get("slash_pct", 0))))

        if violation and slash_pct > 0:
            stake = self.stakes[agent]
            slashed = (stake * slash_pct) // 100
            
            bounty = slashed // 2
            treasury_cut = slashed - bounty

            self.stakes[agent] -= slashed
            self.balances[gl.message.sender] = self.balances.get(gl.message.sender, 0) + bounty
            self.balances[self.treasury] = self.balances.get(self.treasury, 0) + treasury_cut

    @gl.public.write
    def withdraw(self) -> None:
        bal = self.balances.get(gl.message.sender, 0)
        assert bal > 0, "zero balance"
        self.balances[gl.message.sender] = 0
        gl.transfer(gl.message.sender, bal)
