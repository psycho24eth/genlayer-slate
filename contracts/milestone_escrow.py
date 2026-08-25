# contracts/milestone_escrow.py
from genlayer import *
import json

@gl.contract
class MilestoneEscrow:
    """
    Holds client funds for a job.
    Validators fetch evidence from a target URL (e.g. GitHub release, API endpoint)
    and verify if the deliverable satisfies the plain-text agreement.
    """

    def __init__(self, client: str, contractor: str):
        self.client: str = client
        self.contractor: str = contractor
        self.spec: str = ""
        self.evidence_url: str = ""
        self.amount: int = 0
        self.status: str = "PENDING"  # PENDING -> SUBMITTED -> SETTLED | REFUNDED
        self.balances: dict[str, int] = {}
        self.verdict_notes: str = ""

    @gl.public.write
    def lock_funds(self, spec: str, evidence_url: str) -> None:
        assert gl.message.sender == self.client, "unauthorized"
        assert self.status == "PENDING", "already funded"
        assert gl.message.value > 0, "zero deposit"

        self.spec = spec
        self.evidence_url = evidence_url
        self.amount = gl.message.value

    @gl.public.write
    def submit(self) -> None:
        assert gl.message.sender == self.contractor, "unauthorized"
        assert self.status == "PENDING" and self.amount > 0, "not ready"
        self.status = "SUBMITTED"

    @gl.public.write
    def evaluate(self) -> None:
        assert self.status == "SUBMITTED", "submission required"
        
        # Read live webpage
        html = gl.get_webpage(self.evidence_url)
        
        prompt = f"""
        Compare the delivered evidence against the agreed specification.
        
        Agreed Specification:
        {self.spec}
        
        Evidence from {self.evidence_url}:
        {html[:3500]}
        
        Does the evidence prove the specification was met?
        Respond with JSON:
        {{
            "passed": true,
            "reason": "summary"
        }}
        """
        
        res = json.loads(gl.exec_prompt(prompt))
        passed = bool(res.get("passed", False))
        self.verdict_notes = res.get("reason", "")

        if passed:
            self.status = "SETTLED"
            self.balances[self.contractor] = self.balances.get(self.contractor, 0) + self.amount
        else:
            self.status = "REFUNDED"
            self.balances[self.client] = self.balances.get(self.client, 0) + self.amount
            
        self.amount = 0

    @gl.public.write
    def withdraw(self) -> None:
        bal = self.balances.get(gl.message.sender, 0)
        assert bal > 0, "zero balance"
        self.balances[gl.message.sender] = 0
        gl.transfer(gl.message.sender, bal)

    @gl.public.view
    def get_details(self) -> dict:
        return {
            "status": self.status,
            "amount": self.amount,
            "notes": self.verdict_notes
        }
