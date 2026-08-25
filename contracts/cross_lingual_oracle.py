# contracts/cross_lingual_oracle.py
from genlayer import *
import json

@gl.contract
class CrossLingualOracle:
    """
    Resolves real-world claims by comparing news sources published in different languages.
    Ensures global consensus without relying solely on English feeds.
    """
    query: str
    source_url_a: str
    source_url_b: str
    resolved: bool
    outcome: str

    def __init__(self, query: str, source_url_a: str, source_url_b: str):
        self.query = query
        self.source_url_a = source_url_a
        self.source_url_b = source_url_b
        self.resolved = False
        self.outcome = "UNRESOLVED"

    @gl.public.write
    def resolve(self) -> None:
        assert not self.resolved, "already resolved"

        page_a = gl.get_webpage(self.source_url_a)
        page_b = gl.get_webpage(self.source_url_b)

        prompt = f"""
        Compare two international news reports to answer the target query.

        Query: {self.query}

        Source A ({self.source_url_a}):
        {page_a[:2500]}

        Source B ({self.source_url_b}):
        {page_b[:2500]}

        Do both sources agree on the outcome of the query?
        Respond with JSON:
        {{
            "agreed": true,
            "answer": "YES" | "NO" | "AMBIGUOUS",
            "confidence": 0 to 100
        }}
        """

        res = json.loads(gl.exec_prompt(prompt).replace("```json", "").replace("```", "").strip())
        if bool(res.get("agreed", False)) and int(res.get("confidence", 0)) >= 80:
            self.outcome = str(res.get("answer", "AMBIGUOUS"))
        else:
            self.outcome = "AMBIGUOUS"

        self.resolved = True

    @gl.public.view
    def get_result(self) -> dict:
        return {"resolved": self.resolved, "outcome": self.outcome}
