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
- **Deployed Address**: [`0x17fCdDCCc704f912Ca8737e180bC59d9dB4c80A1`](https://explorer-studio.genlayer.com/address/0x17fCdDCCc704f912Ca8737e180bC59d9dB4c80A1)
- **Deployment Transaction**: `0x58e5c046d55863c009d229f26c8fc0aadc36e6132684c97e8bbafae72294cacb`

### Purpose
Verifies that an off-chain intent solver (e.g. DEX aggregator, routing auctioneer, account abstraction bundler) fulfilled the user's natural language execution constraints without slippage exploitation or frontrunning before releasing settlement funds and solver bonds.

### Constructor
```python
def __init__(
    self,
    user: Address,
    solver: Address,
    intent_spec: str,
    tolerance_milli: int = 200,
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
- `tolerance_milli: u256` - Allowed spread in validator execution quality scores.

### Consensus & Equivalence Principle
- Closure `evaluate_intent()` feeds user constraints and solver execution receipt into `gl.nondet.exec_prompt`.
- Principle: `gl.eq_principle.prompt_comparative` requires validators to agree on `fulfilled: bool`, match quality scores within `tolerance_milli`, and concur on outcome (`PASS` vs `FAIL`).
- **Independent Validation**: Enforces `expected_outcome == "PASS" if (fulfilled and score_milli >= 700) else "FAIL"`.

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
- **Deployed Address**: [`0x4Cb0d78790A58cFCBB01e1b18bdad399d202e098`](https://explorer-studio.genlayer.com/address/0x4Cb0d78790A58cFCBB01e1b18bdad399d202e098)
- **Deployment Transaction**: `0x6d420698047fd01ca38e4098a2bfb648b01b004263355ccb45df88fb6d673dc9`

### Purpose
Staking and slash enforcement registry for autonomous AI agents and automated bots. Agents lock economic collateral alongside a declared operational policy. If a bot behaves maliciously, any observer can submit the incident trace; validators audit the trace against the policy and slash misaligned collateral.

### Constructor
```python
def __init__(self, treasury: Address, tolerance_pct: int = 20)
```

### Storage Layout
- `treasury: Address` - Protocol treasury destination for slashed funds.
- `tolerance_pct: u256` - Allowed discrepancy in validator slash percentage calculations.
- `stakes: TreeMap[Address, u256]` - Collateral balances per agent.
- `policies: TreeMap[Address, str]` - Plain-text operational policies per agent.
- `claimable: TreeMap[Address, u256]` - Pull-payment reward balances.

### Consensus & Equivalence Principle
- Closure `evaluate_incident()` analyzes the incident trace against the bot's declared policy.
- Principle: `gl.eq_principle.prompt_comparative` ensures validators agree on `violation: bool`, have `slash_pct` within `tolerance_pct`, and agree on action (`SLASH` vs `DISMISS`).
- **Independent Validation**: Enforces `expected_action == "SLASH" if (violation and slash_pct > 0) else "DISMISS"`.
- Slashing accounting: 50% of slashed stake rewards the whistleblower reporter, and 50% is credited to the treasury.

---

## 5. SpecBounty

- **File**: `contracts/spec_bounty.py`
- **Network**: GenLayer Studio Network (`studionet`)
- **Deployed Address**: [`0xf9451c01522063BE7f2b41E95fd10f84a695aC23`](https://explorer-studio.genlayer.com/address/0xf9451c01522063BE7f2b41E95fd10f84a695aC23)
- **Deployment Transaction**: `0x9bc104c9b56205b4468bd78fbb3582fe0bebac350321034dc3ac44cfbcc45341`

### Purpose
Autonomous bug bounty pool triaging vulnerability submissions against a plain-text scope policy. Categorizes severity, computes reward amounts within deterministic caps, and credits payouts.

### Constructor
```python
def __init__(self, owner: Address, scope: str, tolerance_pct: int = 20)
```

### Storage Layout
- `owner: Address` - Program manager.
- `scope: str` - Written scope policy (in-scope targets, out-of-scope bugs).
- `pool_balance: u256` - Active funding pool.
- `tolerance_pct: u256` - Allowed spread in reward percentages.
- `claims: DynArray[BountyClaim]` - History of evaluated submissions.
- `claimable: TreeMap[Address, u256]` - Bounty reward pull balances.

### Consensus & Equivalence Principle
- Closure `evaluate_submission()` classifies vulnerability severity into tiers: `CRITICAL` (capped at 100%), `HIGH` (capped at 50%), `MEDIUM` (capped at 20%), or `NONE` (0%).
- Principle: `gl.eq_principle.prompt_comparative` requires exact agreement on validity and severity tier, with `payout_pct` within tolerance.
- **Independent Validation**: Asserts `payout_pct <= max_allowed` for the judged tier before pool deduction.

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
- **Deployed Address**: [`0x2585C52fdC2B463Af9522EecD60027eDBfb3e3D4`](https://explorer-studio.genlayer.com/address/0x2585C52fdC2B463Af9522EecD60027eDBfb3e3D4)
- **Deployment Transaction**: `0xf87b7ef89ed9161779b8a20d63ae9adcb4842063121368692693caa433030816`

### Purpose
Parametric disaster insurance pool. Requires independent corroboration across multiple distinct web feeds (e.g. NOAA, USGS, meteorological feeds) before releasing insurance claim disbursements.

### Constructor
```python
def __init__(
    self,
    claimant: Address,
    incident_condition: str,
    source_url_1: str,
    source_url_2: str,
    tolerance_pct: int = 25,
)
```

### Storage Layout
- `claimant: Address` - Policyholder beneficiary.
- `incident_condition: str` - Written parametric threshold (e.g. wind speed, flood stage, magnitude).
- `source_url_1: str` - Primary sensor/agency feed.
- `source_url_2: str` - Secondary corroborating agency feed.
- `pool_balance: u256` - Active insurance capital pool.
- `claim_settled: bool` - One-way claim resolution latch.
- `severity_pct: u256` - Evaluated incident severity (0..100%).
- `tolerance_pct: u256` - Allowed variance in severity scoring.
- `claimable: TreeMap[Address, u256]` - Pull-payment disbursement ledger.

### Consensus & Equivalence Principle
- Closure `corroborate_incident()` fetches data feeds via `gl.nondet.web.render` and determines whether both feeds corroborate the parametric condition.
- Principle: `gl.eq_principle.prompt_comparative` requires agreement on `confirmed: bool` and action (`PAYOUT` vs `DENY`), with severity scores within tolerance.
- **Independent Validation**: Asserts `expected_action == "PAYOUT" if (confirmed and severity_pct > 0) else "DENY"`.
