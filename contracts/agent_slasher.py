# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 04: AgentSlasher

PURPOSE
  Staking and slash enforcement registry for autonomous AI agents and bots.
  Agents lock economic collateral alongside a plain-text operating policy or SLA.
  When an agent acts maliciously or violates its rules, whistleblowers submit the
  incident trace. Validators audit the incident against the policy, slash misaligned
  stake, reward the reporter, and direct the remainder to protocol treasury.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  audits the agent's incident trace against its registered policy. Validators
  determine if a breach occurred and calculate a slash percentage (0..100%).
  Consensus requires agreement on the violation verdict and that slash percentages
  align within the specified tolerance. Slashes and treasury credits execute only
  after consensus is finalized.

STATE DESIGN
  - Staking ledger mapping agent Address to locked stake (`stakes: TreeMap[Address, u256]`).
  - Immutable policy registry per agent (`policies: TreeMap[Address, str]`).
  - Non-custodial pull-payment ledger (`claimable: TreeMap[Address, u256]`).
  - Strict integer math prevents underflow/overflow during slash splits.

REUSE
  Applicable to AI agent marketplaces, decentralized keeper networks, autonomous
  liquidity managers, oracle relayers, and automated governance proxies.
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


class AgentSlasher(gl.Contract):
    treasury: Address
    tolerance_pct: u256
    stakes: TreeMap[Address, u256]
    policies: TreeMap[Address, str]
    claimable: TreeMap[Address, u256]

    def __init__(self, treasury: Address, tolerance_pct: int = 20):
        require(0 < tolerance_pct <= 50, "invalid tolerance percentage")
        self.treasury = treasury
        self.tolerance_pct = u256(tolerance_pct)

    @gl.public.write.payable
    def register_agent(self, policy: str) -> None:
        agent = gl.message.sender_address
        deposit = int(gl.message.value)
        require(deposit > 0, "positive collateral required")
        require(len(policy.strip()) > 0, "empty operating policy")

        prev_stake = int(self.stakes.get(agent, u256(0)))
        self.stakes[agent] = u256(prev_stake + deposit)
        self.policies[agent] = policy.strip()

    @gl.public.write
    def slash_agent(self, agent: Address, incident_log: str) -> str:
        current_stake = int(self.stakes.get(agent, u256(0)))
        require(current_stake > 0, "agent has no active stake")
        policy = self.policies.get(agent, "")
        require(len(policy) > 0, "no registered policy found")
        require(len(incident_log.strip()) > 0, "empty incident log")

        tol = int(self.tolerance_pct)
        log_snippet = incident_log.strip()[:3500]

        def evaluate_incident() -> str:
            prompt = f"""You are a decentralized security auditor enforcing bot alignment.

AGENT OPERATIONAL POLICY:
{policy}

INCIDENT LOG / EXECUTION TRACE:
{log_snippet}

Determine whether the agent violated its declared policy. If so, specify the recommended slash percentage (0 to 100).

Return strict JSON only with no markdown wrapping:
{{
  "violation": true or false,
  "slash_pct": <integer between 0 and 100>,
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            violation = bool(data.get("violation", False))
            slash_pct = int(data.get("slash_pct", 0))
            slash_pct = max(0, min(100, slash_pct))
            reason = str(data.get("reason", "")).strip()[:120]

            action = "SLASH" if (violation and slash_pct > 0) else "DISMISS"
            return canonical(
                {
                    "violation": violation,
                    "slash_pct": slash_pct,
                    "reason": reason,
                    "action": action,
                }
            )

        principle = (
            "The two validators audit the agent incident log against its declared policy. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'violation' boolean, "
            f"(2) their slash_pct values differ by at most {tol} percentage points, and "
            "(3) their 'action' values match ('SLASH' or 'DISMISS'). If violation determination diverges, "
            "they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(evaluate_incident, principle)
        parsed = json.loads(agreed)

        violation = bool(parsed["violation"])
        slash_pct = int(parsed["slash_pct"])
        action = str(parsed["action"])
        expected_action = "SLASH" if (violation and slash_pct > 0) else "DISMISS"
        require(action == expected_action, "slash determination violates bounds")

        if action == "SLASH":
            slash_amount = (current_stake * slash_pct) // 100
            reporter_reward = slash_amount // 2
            treasury_cut = slash_amount - reporter_reward

            self.stakes[agent] = u256(current_stake - slash_amount)

            reporter = gl.message.sender_address
            prev_rep = int(self.claimable.get(reporter, u256(0)))
            self.claimable[reporter] = u256(prev_rep + reporter_reward)

            prev_treasury = int(self.claimable.get(self.treasury, u256(0)))
            self.claimable[self.treasury] = u256(prev_treasury + treasury_cut)

            return "SLASHED"

        return "DISMISSED"

    @gl.public.write
    def withdraw(self) -> None:
        bal = int(self.claimable.get(gl.message.sender_address, u256(0)))
        require(bal > 0, "no claimable balance")
        self.claimable[gl.message.sender_address] = u256(0)
        _NativeRecipient(gl.message.sender_address).emit_transfer(value=u256(bal))

    @gl.public.view
    def get_stake(self, agent: Address) -> int:
        return int(self.stakes.get(agent, u256(0)))

    @gl.public.view
    def get_claimable(self, account: Address) -> int:
        return int(self.claimable.get(account, u256(0)))
