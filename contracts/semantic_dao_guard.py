# contracts/semantic_dao_guard.py
from genlayer import *
import json

@gl.contract
class SemanticDAOGuard:
    """
    Validates DAO proposals against a plain-text constitution.
    Blocks malicious or Trojan proposals before on-chain execution.
    """
    constitution: str
    dao_treasury: Address
    proposals: TreeMap[u256, dict]
    proposal_count: u256

    def __init__(self, dao_treasury: Address, constitution: str):
        self.dao_treasury = dao_treasury
        self.constitution = constitution
        self.proposal_count = u256(0)

    @gl.public.write
    def submit_proposal(self, title: str, description: str, execution_payload: str) -> u256:
        pid = self.proposal_count
        self.proposal_count = pid + u256(1)

        prompt = f"""
        Audit this DAO proposal against the DAO's written constitution.

        DAO Constitution:
        {self.constitution}

        Proposal Title: {title}
        Proposal Description: {description}
        Execution Payload / Actions: {execution_payload}

        Is this proposal aligned with the constitution, or is it a malicious governance attack?
        Respond with JSON:
        {{
            "compliant": true,
            "risk_score": 0 to 100,
            "reason": "summary"
        }}
        """

        res = json.loads(gl.exec_prompt(prompt).replace("```json", "").replace("```", "").strip())
        is_compliant = bool(res.get("compliant", False))
        risk = int(res.get("risk_score", 100))

        self.proposals[pid] = {
            "proposer": str(gl.message.sender),
            "title": title,
            "approved": is_compliant and risk < 30,
            "reason": str(res.get("reason", ""))
        }
        return pid

    @gl.public.view
    def get_proposal(self, pid: u256) -> dict:
        return self.proposals.get(pid, {})
