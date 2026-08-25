# contracts/dispute_court.py
from genlayer import *
import json

@gl.contract
class DisputeCourt:
    """
    Arbitration contract for two-party disputes.
    If validator disagreement exceeds the max_variance threshold, the contract
    avoids making a false binary call and splits funds 50/50 back to both parties.
    """

    def __init__(self, max_variance: int = 30):
        self.max_variance: int = max_variance
        self.cases: dict[int, dict] = {}
        self.case_count: int = 0
        self.balances: dict[str, int] = {}

    @gl.public.write
    def file_case(self, defendant: str, terms: str, plaintiff_claim: str, defendant_claim: str) -> int:
        assert gl.message.value > 0, "escrow required"
        
        cid = self.case_count
        self.case_count += 1

        self.cases[cid] = {
            "plaintiff": gl.message.sender,
            "defendant": defendant,
            "terms": terms,
            "p_claim": plaintiff_claim,
            "d_claim": defendant_claim,
            "deposit": gl.message.value,
            "closed": False,
            "ruling": ""
        }
        return cid

    @gl.public.write
    def resolve(self, case_id: int) -> None:
        case = self.cases.get(case_id)
        assert case is not None, "not found"
        assert not case["closed"], "already settled"

        prompt = f"""
        Arbitrate this dispute based on original terms and evidence.
        
        Terms: {case['terms']}
        Plaintiff Claim: {case['p_claim']}
        Defendant Claim: {case['d_claim']}
        
        Score Plaintiff adherence and merit from 0 to 100 (100 = full favor to Plaintiff, 0 = Defendant).
        Estimate validator disagreement score (0 to 100).
        
        Return JSON:
        {{
            "plaintiff_score": 0 to 100,
            "variance": 0 to 100,
            "reason": "summary"
        }}
        """

        res = json.loads(gl.exec_prompt(prompt))
        score = int(res.get("plaintiff_score", 50))
        variance = int(res.get("variance", 0))
        deposit = case["deposit"]

        if variance > self.max_variance or 45 <= score <= 55:
            half = deposit // 2
            self.balances[case["plaintiff"]] = self.balances.get(case["plaintiff"], 0) + half
            self.balances[case["defendant"]] = self.balances.get(case["defendant"], 0) + (deposit - half)
            case["ruling"] = f"SPLIT: {res.get('reason', '')}"
        elif score > 55:
            self.balances[case["plaintiff"]] = self.balances.get(case["plaintiff"], 0) + deposit
            case["ruling"] = f"PLAINTIFF_WINS: {res.get('reason', '')}"
        else:
            self.balances[case["defendant"]] = self.balances.get(case["defendant"], 0) + deposit
            case["ruling"] = f"DEFENDANT_WINS: {res.get('reason', '')}"

        case["closed"] = True

    @gl.public.write
    def withdraw(self) -> None:
        bal = self.balances.get(gl.message.sender, 0)
        assert bal > 0, "no funds"
        self.balances[gl.message.sender] = 0
        gl.transfer(gl.message.sender, bal)
