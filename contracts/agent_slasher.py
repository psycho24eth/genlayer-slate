# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SLATE -- 04: AgentSlasher

PURPOSE
  Staking and slash enforcement registry for autonomous AI agents and bots.
  Agents lock economic collateral alongside a plain-text operating policy or SLA.
  When an agent acts maliciously or violates its rules, whistleblowers submit the
  incident trace. Validators audit the incident against the policy, slash misaligned
  stake based on canonical discrete severity buckets, reward the reporter, and direct
  the remainder to protocol treasury.

CONSENSUS
  Consensus uses the COMPARATIVE equivalence principle. Each validator independently
  audits the agent's incident trace against its registered policy. Validators
  determine if a breach occurred and select an exact canonical discrete severity tier:
  NONE (0%), MINOR (25%), MAJOR (50%), or CRITICAL (100%).
  Consensus requires exact categorical agreement on both the violation verdict and
  the canonical tier string. Slashing calculations and treasury credits execute only
  after consensus is finalized and are 100% deterministically derived from the agreed tier.

STATE DESIGN
  - Staking ledger mapping agent Address to locked stake (stakes: TreeMap[Address, u256]).
  - Immutable policy registry per agent (policies: TreeMap[Address, str]).
  - Non-custodial pull-payment ledger (claimable: TreeMap[Address, u256]).
  - Deterministic discrete bucket mapping guarantees zero percentage drift across validators.
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
    stakes: TreeMap[Address, u256]
    policies: TreeMap[Address, str]
    claimable: TreeMap[Address, u256]

    def __init__(self, treasury: Address):
        self.treasury = treasury

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

        log_snippet = incident_log.strip()[:3500]

        def evaluate_incident() -> str:
            prompt = f"""You are a decentralized security auditor enforcing bot alignment.

AGENT OPERATIONAL POLICY:
{policy}

INCIDENT LOG / EXECUTION TRACE:
{log_snippet}

Determine whether the agent violated its declared policy and assign an exact canonical severity tier:
- NONE: No violation occurred or incident is within acceptable policy bounds (0% slash).
- MINOR: Low-severity infraction or minor non-compliance (25% slash).
- MAJOR: Significant operational failure or policy breach (50% slash).
- CRITICAL: Catastrophic failure, malicious exploit, or complete breach of trust (100% slash).

Return strict JSON only with no markdown wrapping:
{{
  "violation": true or false,
  "tier": "NONE" | "MINOR" | "MAJOR" | "CRITICAL",
  "reason": "<summary in <= 20 words>"
}}"""
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)

            violation = bool(data.get("violation", False))
            tier = str(data.get("tier", "NONE")).strip().upper()
            if tier not in ("NONE", "MINOR", "MAJOR", "CRITICAL"):
                tier = "NONE"

            if not violation or tier == "NONE":
                violation = False
                tier = "NONE"

            reason = str(data.get("reason", "")).strip()[:120]
            action = "SLASH" if (violation and tier != "NONE") else "DISMISS"
            return canonical(
                {
                    "violation": violation,
                    "tier": tier,
                    "reason": reason,
                    "action": action,
                }
            )

        principle = (
            "The two validators audit the agent incident log against its declared policy. "
            "They are EQUIVALENT if and only if: (1) both agree on the 'violation' boolean, "
            "(2) their 'tier' values match exactly ('NONE', 'MINOR', 'MAJOR', or 'CRITICAL'), and "
            "(3) their 'action' values match ('SLASH' or 'DISMISS'). If violation or tier determination diverges, "
            "they are NOT equivalent."
        )

        agreed = gl.eq_principle.prompt_comparative(evaluate_incident, principle)
        parsed = json.loads(agreed)

        violation = bool(parsed["violation"])
        tier = str(parsed["tier"])
        action = str(parsed["action"])
        expected_action = "SLASH" if (violation and tier != "NONE") else "DISMISS"
        require(action == expected_action, "slash determination violates bounds")
        require(tier in ("NONE", "MINOR", "MAJOR", "CRITICAL"), "invalid slash tier")

        if action == "SLASH":
            pct = 25 if tier == "MINOR" else (50 if tier == "MAJOR" else (100 if tier == "CRITICAL" else 0))
            require(pct > 0, "positive slash percentage required")

            slash_amount = (current_stake * pct) // 100
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
