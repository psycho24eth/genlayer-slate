# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 07: CrossLingualOracle

PURPOSE
  Resolves real-world factual claims by corroborating independent news reports
  published in different languages (e.g., Japanese, Spanish, German, French, Mandarin).
  Eliminates single-language media bias and regional reporting siloes to establish
  global consensus on contested events.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  fetches the multi-lingual primary sources, analyzes cross-lingual semantic alignment,
  and evaluates the target factual query. Validators must agree on the final categorical
  verdict (YES, NO, or AMBIGUOUS) and their confidence measurements must align within
  the configured tolerance. If sources conflict or fail to corroborate, the oracle
  safely falls back to AMBIGUOUS.

STATE DESIGN
  - Immutable query and source URLs defined upon contract creation.
  - One-way state transition: UNRESOLVED -> RESOLVED.
  - Integer milli-units (`confidence_milli: u256`) preserve exact on-chain certainty.
  - Read queries expose resolution status and final consensus answer.

REUSE
  Vital primitive for prediction markets, global supply chain event verifiers,
  international insurance triggers, and cross-border settlement protocols.
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


_MILLI = 1000


class CrossLingualOracle(gl.Contract):
    query: str
    source_url_a: str
    source_url_b: str
    resolved: bool
    outcome: str
    confidence_milli: u256
    confidence_threshold_milli: u256
    tolerance_milli: u256

    def __init__(
        self,
        query: str,
        source_url_a: str,
        source_url_b: str,
        confidence_threshold_milli: int = 750,
        tolerance_milli: int = 200,
    ):
        require(len(query.strip()) > 0, "empty query")
        require(len(source_url_a.strip()) > 0, "empty source a")
        require(len(source_url_b.strip()) > 0, "empty source b")
        require(0 < confidence_threshold_milli <= 1000, "invalid confidence threshold")
        require(0 < tolerance_milli <= 500, "invalid tolerance")

        self.query = query.strip()
        self.source_url_a = source_url_a.strip()
        self.source_url_b = source_url_b.strip()
        self.resolved = False
        self.outcome = "UNRESOLVED"
        self.confidence_milli = u256(0)
        self.confidence_threshold_milli = u256(confidence_threshold_milli)
        self.tolerance_milli = u256(tolerance_milli)

    @gl.public.write
    def resolve(self) -> str:
        require(not self.resolved, "oracle already resolved")

        q = self.query
        url_a = self.source_url_a
        url_b = self.source_url_b
        threshold = int(self.confidence_threshold_milli)
        tol = int(self.tolerance_milli)

        def cross_examine() -> str:
            try:
                page_a = gl.nondet.web.render(url_a, mode="text")
                body_a = page_a[:2500] if page_a else "[EMPTY SOURCE A]"
            except Exception as exc:
                body_a = f"[FETCH A FAILED: {exc}]"[:200]

            try:
                page_b = gl.nondet.web.render(url_b, mode="text")
                body_b = page_b[:2500] if page_b else "[EMPTY SOURCE B]"
            except Exception as exc:
                body_b = f"[FETCH B FAILED: {exc}]"[:200]

            prompt = f"""You are a cross-lingual intelligence analyst resolving an international claim.

QUERY TO VERIFY:
{q}

SOURCE REPORT A ({url_a}):
{body_a}

SOURCE REPORT B ({url_b}):
{body_b}

Compare both international sources across languages. Do both sources agree and corroborate the factual answer to the query?
If sources conflict, are in doubt, or failed to fetch, mark answer as AMBIGUOUS with low confidence.

Return strict JSON only with no markdown wrapping:
{{
  "agreed": true or false,
  "answer": "YES" | "NO" | "AMBIGUOUS",
  "confidence": <float 0..1 representing corroboration certainty>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            agreed = bool(data.get("agreed", False))
            ans = str(data.get("answer", "AMBIGUOUS")).strip().upper()
            if ans not in ("YES", "NO", "AMBIGUOUS"):
                ans = "AMBIGUOUS"

            conf = float(data.get("confidence", 0.0))
            conf = max(0.0, min(1.0, conf))
            conf_milli = int(round(conf * _MILLI))
            reason = str(data.get("reason", "")).strip()[:120]

            outcome = ans if (agreed and conf_milli >= threshold and ans in ("YES", "NO")) else "AMBIGUOUS"
            return canonical(
                {
                    "agreed": agreed,
                    "outcome": outcome,
                    "confidence_milli": conf_milli,
                    "reason": reason,
                }
            )

        principle = (
            "The two validators compare multilingual news reports to resolve the query. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'outcome' string ('YES', 'NO', 'AMBIGUOUS'), "
            f"and (2) their confidence_milli values differ by at most {tol}. "
            "If the resolved outcome diverges, they are NOT equivalent."
        )

        agreed_res = gl.eq_principle.prompt_comparative(cross_examine, principle)
        parsed = json.loads(agreed_res)

        agreed = bool(parsed["agreed"])
        outcome = str(parsed["outcome"])
        conf_milli = int(parsed["confidence_milli"])

        expected_outcome = outcome if (agreed and conf_milli >= threshold and outcome in ("YES", "NO")) else "AMBIGUOUS"
        require(outcome == expected_outcome, "resolved outcome violates confidence threshold")

        self.resolved = True
        self.outcome = outcome
        self.confidence_milli = u256(conf_milli)
        return self.outcome

    @gl.public.view
    def get_result(self) -> str:
        return canonical(
            {
                "query": self.query,
                "resolved": self.resolved,
                "outcome": self.outcome,
                "confidence_milli": int(self.confidence_milli),
                "source_url_a": self.source_url_a,
                "source_url_b": self.source_url_b,
            }
        )
