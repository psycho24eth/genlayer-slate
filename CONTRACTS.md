# Slate: Intelligent Contract Specifications

Slate is a collection of 8 standalone GenLayer Intelligent Contract primitives exploring semantic consensus, web corroboration, and pull-payment accounting.

Each contract is a self-contained, single-file Python module executing inside GenVM under the pinned runner `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`.

---

## 1. MilestoneEscrow

- **File**: `contracts/milestone_escrow.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0x66138e7F98A9CaEF7250f6619cc54d6dF4134140`](https://explorer-studio.genlayer.com/address/0x66138e7F98A9CaEF7250f6619cc54d6dF4134140)
- **Deployment Transaction**: `0xfccf20d6fbc071dd0ef8404bc2a78d21ddccdbea0521403b9e8eb8dae27f402c`

### Purpose
Holds client funds in escrow for freelance, contractor, or vendor deliverables. Validators independently fetch deliverable evidence from a target URL (e.g. GitHub release, documentation page, API endpoint) and verify whether the delivered work satisfies the plain-text agreement before releasing funds.

### Constructor
```python
def __init__(
    self,
    client: Address,
    contractor: Address,
    spec: str,
    evidence_url: str,
    confidence_threshold_milli: int = 700,
    tolerance_milli: int = 250,
)
```

### Storage Layout
- `client: Address` - Depositor authorized to fund.
- `contractor: Address` - Payee deliverer.
- `spec: str` - Immutable plain-text deliverable requirements.
- `evidence_url: str` - Live URL where deliverable is verified.
- `escrow_amount: u256` - Escrowed native GEN balance.
- `status: str` - `PENDING` -> `SUBMITTED` -> `SETTLED` | `REFUNDED`.
- `verdict_notes: str` - Consensus summary rationale.
- `confidence_threshold_milli: u256` - Minimum confidence required to settle (default: 700 / 1000 = 70%).
- `tolerance_milli: u256` - Allowed gap between validator confidence scores (default: 250).
- `claimable: TreeMap[Address, u256]` - Pull-payment balances.

### Consensus & Equivalence Principle
- Non-deterministic inner closure `verify_deliverable()` fetches `evidence_url` via `gl.nondet.web.render(target_url, mode="text")` wrapped in exception guards, and prompts the LLM for `passed: bool`, `confidence: float`, and `reason: str`.
- Equivalence principle: `gl.eq_principle.prompt_comparative` requires validators to agree on the `passed` boolean, have `confidence_milli` within `tolerance_milli`, and match on the resulting action (`SETTLE` vs `REFUND`).
- **Independent Validation**: Asserts `expected_action == "SETTLE" if (passed and conf_milli >= threshold) else "REFUND"`.

### Fallback Mode
If evidence fetch fails or confidence falls below threshold, the contract safely settles as `REFUND`, returning 100% of escrow back to the client.

---

## 2. IntentSolverVerifier

- **File**: `contracts/intent_solver_verifier.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0x61631822286c65b7B9078ee7dfc7C64D1981e88c`](https://explorer-studio.genlayer.com/address/0x61631822286c65b7B9078ee7dfc7C64D1981e88c)
- **Deployment Transaction**: `0x55a9727c5d1fcf4d35ed474a353777911c92d5d108939ddeca2805bd0ced6a42`

### Purpose
Verifies that an off-chain intent solver (e.g. DEX aggregator, routing auctioneer, account abstraction bundler) fulfilled the user's natural language execution constraints without slippage exploitation or frontrunning before releasing settlement funds and solver bonds. Directly fetches authoritative on-chain transaction evidence from block explorer or RPC endpoints inside the non-deterministic flow.

### Constructor
```python
def __init__(
    self,
    user: Address,
    solver: Address,
    intent_spec: str,
)
```

### Storage Layout
- `user: Address` - User initiating the intent.
- `solver: Address` - Off-chain execution solver.
- `intent_spec: str` - Plain-text constraints (limits, routes, acceptable slippage).
- `user_deposit: u256` - Escrowed user funds.
- `solver_bond: u256` - Fidelity collateral bond posted by solver.
- `settled: bool` - One-way completion latch.
- `verdict: str` - `UNSETTLED`, `FULFILLED`, or `SLASHED`.
- `claimable: TreeMap[Address, u256]` - Pull-payment balances.

### Consensus & Equivalence Principle
- Closure `evaluate_execution()` fetches live transaction evidence via `gl.nondet.web.render(evidence_url, mode="text")` and feeds user constraints, expected transaction hash, and authoritative trace into `gl.nondet.exec_prompt`.
- Principle: `gl.eq_principle.prompt_comparative` requires validators to agree on `confirmed: bool`, agree on `fulfilled: bool`, and reach exact categorical consensus on `outcome` (`PASS` vs `FAIL`).
- **Independent Validation**: Enforces `expected_outcome == "PASS" if (confirmed and fulfilled) else "FAIL"`.

### Economic Settlement
- `PASS`: Solver receives user escrow + bond deposit.
- `FAIL`: User receives 100% refund of escrow + entire solver bond as compensation for griefing/slippage.

---

## 3. SemanticDAOGuard

- **File**: `contracts/semantic_dao_guard.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0x260c37fD22DCa0A8d519903113681ef55f8ABFf3`](https://explorer-studio.genlayer.com/address/0x260c37fD22DCa0A8d519903113681ef55f8ABFf3)
- **Deployment Transaction**: `0x30d11ba576788d2d3ae0f7da38b2f0e912d02a8b2570d2ec6ea0d7cb36eeb304`

### Purpose
Pre-execution constitutional filter for DAOs. Audits proposed transactions and calldata payloads against the DAO's immutable plain-text constitution to block Trojan proposals, parameter exploits, or unauthorized treasury drains.

### Constructor
```python
def __init__(
    self,
    dao_treasury: Address,
    constitution: str,
    max_risk_milli: int = 300,
    tolerance_milli: int = 200,
)
```

### Storage Layout
- `dao_treasury: Address` - DAO treasury address.
- `constitution: str` - Immutable constitutional articles and bylaws.
- `max_risk_milli: u256` - Maximum acceptable governance risk threshold (default: 300 = 30%).
- `tolerance_milli: u256` - Allowed difference between validator risk assessments.
- `proposals: DynArray[ProposalRecord]` - Append-only record of audited proposals.

### Consensus & Equivalence Principle
- Closure `evaluate_proposal()` compares proposal title, description, and execution payload against constitutional articles.
- Principle: `gl.eq_principle.prompt_comparative` verifies that validators agree on `compliant: bool`, keep `risk_milli` within tolerance, and produce identical `approved` decisions.
- **Independent Validation**: `require(approved == (compliant and risk_milli <= max_risk))`.

---

## 4. AgentSlasher

- **File**: `contracts/agent_slasher.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0x9B76cD8bCd2EB012cd2018dE59B930e0B4d78CF9`](https://explorer-studio.genlayer.com/address/0x9B76cD8bCd2EB012cd2018dE59B930e0B4d78CF9)
- **Deployment Transaction**: `0x7db9e4439d4a090d9b43c235b2e86fa621e2ab3e998c3be27ffd4911c338ef04`

### Purpose
Staking and slash enforcement registry for autonomous AI agents and automated bots. Agents lock economic collateral alongside a declared operational policy. If a bot behaves maliciously, any observer can submit the incident trace; validators audit the trace against the policy and slash misaligned collateral using exact canonical discrete severity buckets.

### Constructor
```python
def __init__(self, treasury: Address)
```

### Storage Layout
- `treasury: Address` - Protocol treasury destination for slashed funds.
- `stakes: TreeMap[Address, u256]` - Collateral balances per agent.
- `policies: TreeMap[Address, str]` - Plain-text operational policies per agent.
- `claimable: TreeMap[Address, u256]` - Pull-payment reward balances.

### Consensus & Equivalence Principle
- Closure `evaluate_incident()` analyzes the incident trace against the bot's declared policy and assigns an exact canonical tier: `NONE` (0%), `MINOR` (25%), `MAJOR` (50%), or `CRITICAL` (100%).
- Principle: `gl.eq_principle.prompt_comparative` ensures validators agree on `violation: bool`, match exactly on the canonical `tier` string (`NONE`, `MINOR`, `MAJOR`, `CRITICAL`), and agree on action (`SLASH` vs `DISMISS`).
- **Independent Validation**: Enforces `expected_action == "SLASH" if (violation and tier != "NONE") else "DISMISS"`.
- Slashing accounting: Slash percentage is strictly derived from the agreed canonical bucket (100% deterministic). 50% of slashed stake rewards the whistleblower reporter, and 50% is credited to the treasury.

---

## 5. SpecBounty

- **File**: `contracts/spec_bounty.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0x02A3ef75206C58D49201a4E66249f0f57C5d8D47`](https://explorer-studio.genlayer.com/address/0x02A3ef75206C58D49201a4E66249f0f57C5d8D47)
- **Deployment Transaction**: `0xcf4699750e9b52e74e9c3f9af63fb060698f85bf5ad2cef652a5aedab9b37e15`

### Purpose
Autonomous bug bounty pool triaging vulnerability submissions against a plain-text scope policy. Categorizes severity into exact canonical discrete buckets and computes reward amounts strictly derived from the agreed bucket.

### Constructor
```python
def __init__(self, owner: Address, scope: str)
```

### Storage Layout
- `owner: Address` - Program manager.
- `scope: str` - Written scope policy (in-scope targets, out-of-scope bugs).
- `pool_balance: u256` - Active funding pool.
- `claims: DynArray[BountyClaim]` - History of evaluated submissions.
- `claimable: TreeMap[Address, u256]` - Bounty reward pull balances.

### Consensus & Equivalence Principle
- Closure `evaluate_submission()` classifies vulnerability severity into exact canonical tiers: `CRITICAL` (fixed 50% of active pool), `HIGH` (fixed 25% of active pool), `MEDIUM` (fixed 10% of active pool), or `NONE` (0%).
- Principle: `gl.eq_principle.prompt_comparative` requires exact agreement on validity and exact matching on the canonical `severity` string (`CRITICAL`, `HIGH`, `MEDIUM`, `NONE`).
- **Independent Validation**: Payout is strictly calculated from the agreed bucket (`50%` for CRITICAL, `25%` for HIGH, `10%` for MEDIUM, `0%` for NONE), ensuring 100% deterministic transfers across all validators.

---

## 6. DisputeCourt

- **File**: `contracts/dispute_court.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0x5c3fa2bDF022ac31724963C53285d565FCc189B3`](https://explorer-studio.genlayer.com/address/0x5c3fa2bDF022ac31724963C53285d565FCc189B3)
- **Deployment Transaction**: `0x99030cc43b24fcd98a1f1ebb658d4b0211dcc3f9dcbd9c60266819f86d6f41a2`

### Purpose
Arbitration court for two-party commercial disputes. If evidence is ambiguous or evenly balanced (45%-55% merit range), the court refuses to force an arbitrary binary winner and safely splits escrow 50/50 back to both parties. If one party clearly prevails, the winner receives the full escrow.

### Constructor
```python
def __init__(self, max_ambiguity_milli: int = 350, tolerance_milli: int = 200)
```

### Storage Layout
- `max_ambiguity_milli: u256` - Threshold beyond which ambiguity triggers a 50/50 split.
- `tolerance_milli: u256` - Allowed merit score difference between validators.
- `cases: DynArray[CaseRecord]` - Historical case arbitration log.
- `claimable: TreeMap[Address, u256]` - Pull-payment arbitration disbursements.

### Consensus & Equivalence Principle
- Closure `arbitrate()` evaluates contract terms, plaintiff claims, and defendant defense, returning `merit_score` and `ambiguity_score`.
- Principle: `gl.eq_principle.prompt_comparative` checks that merit scores match within tolerance and that validators concur on action (`PLAINTIFF_WINS`, `DEFENDANT_WINS`, or `SPLIT`).
- **Independent Validation**: Verifies action satisfies decision boundaries before escrow redistribution.

---

## 7. CrossLingualOracle

- **File**: `contracts/cross_lingual_oracle.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0x5c6Eeef3338A63EbADb2FEA12fa94847A6af469d`](https://explorer-studio.genlayer.com/address/0x5c6Eeef3338A63EbADb2FEA12fa94847A6af469d)
- **Deployment Transaction**: `0x09ca249ff63289b8f78bc30b71064e8b6a92c1b3df63166a878d8c5e36923217`

### Purpose
Resolves real-world claims by comparing and corroborating news reports published in different languages (e.g. Japanese, Spanish, English, French). Eliminates single-language reporting bias.

### Constructor
```python
def __init__(
    self,
    query: str,
    source_url_a: str,
    source_url_b: str,
    confidence_threshold_milli: int = 750,
    tolerance_milli: int = 200,
)
```

### Storage Layout
- `query: str` - Factual question to resolve.
- `source_url_a: str` - First multilingual source endpoint.
- `source_url_b: str` - Second multilingual source endpoint.
- `resolved: bool` - One-way resolution flag.
- `outcome: str` - `UNRESOLVED`, `YES`, `NO`, or `AMBIGUOUS`.
- `confidence_milli: u256` - Corroboration confidence recorded at resolution.
- `confidence_threshold_milli: u256` - Threshold required for decisive resolution.
- `tolerance_milli: u256` - Allowed spread in confidence metrics.

### Consensus & Equivalence Principle
- Closure `cross_examine()` fetches both URLs via `gl.nondet.web.render(..., mode="text")` and checks cross-lingual factual alignment.
- Principle: `gl.eq_principle.prompt_comparative` requires exact agreement on the outcome token (`YES`, `NO`, `AMBIGUOUS`) and confidence within tolerance.
- **Independent Validation**: Re-asserts `expected_outcome == outcome if (agreed and conf >= threshold) else "AMBIGUOUS"`.

---

## 8. MultiSourceInsurance

- **File**: `contracts/multi_source_insurance.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0xB01f2103b82c720E08aCBeB91bCEE1bCd5535cC0`](https://explorer-studio.genlayer.com/address/0xB01f2103b82c720E08aCBeB91bCEE1bCd5535cC0)
- **Deployment Transaction**: `0x49b8d5a69449bbb47f4be572a927dfb23a26beba4c9da99ca6942fc760c42d92`

### Purpose
Parametric disaster insurance pool. Requires independent corroboration across multiple distinct web feeds (e.g. NOAA, USGS, meteorological feeds) before releasing insurance claim disbursements using exact canonical disaster severity tiers.

### Constructor
```python
def __init__(
    self,
    claimant: Address,
    incident_condition: str,
    source_url_1: str,
    source_url_2: str,
)
```

### Storage Layout
- `claimant: Address` - Policyholder beneficiary.
- `incident_condition: str` - Written parametric threshold (e.g. wind speed, flood stage, magnitude).
- `source_url_1: str` - Primary sensor/agency feed.
- `source_url_2: str` - Secondary corroborating agency feed.
- `pool_balance: u256` - Active insurance capital pool.
- `claim_settled: bool` - One-way claim resolution latch.
- `severity_tier: str` - Evaluated canonical disaster tier (`CATASTROPHIC`, `SEVERE`, `MODERATE`, `NONE`).
- `claimable: TreeMap[Address, u256]` - Pull-payment disbursement ledger.

### Consensus & Equivalence Principle
- Closure `corroborate_incident()` fetches data feeds via `gl.nondet.web.render` and assigns an exact canonical disaster tier: `CATASTROPHIC` (100% of pool), `SEVERE` (50% of pool), `MODERATE` (25% of pool), or `NONE` (0%).
- Principle: `gl.eq_principle.prompt_comparative` requires agreement on `confirmed: bool`, exact matching on the canonical `tier` string (`CATASTROPHIC`, `SEVERE`, `MODERATE`, `NONE`), and agreement on action (`PAYOUT` vs `DENY`).
- **Independent Validation**: Enforces `expected_action == "PAYOUT" if (confirmed and tier != "NONE") else "DENY"`. Payout percentage is deterministically derived from the canonical tier (100% deterministic).
