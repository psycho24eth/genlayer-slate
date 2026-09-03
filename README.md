# Slate: Minimal Consensus Primitives for GenLayer

A library of 8 standalone GenLayer Intelligent Contract primitives exploring semantic consensus, web corroboration, and deterministic pull-payment ledgers.

Traditional smart contracts only reach consensus on arithmetic calculations. GenLayer expands consensus to qualitative evaluation, natural language agreements, cross-lingual news, and plain-text governance rules.

---

## Deployed Primitives on Studionet

All 8 contracts are deployed and verified on the GenLayer Studio Network (`studionet`):

| # | Primitive | Contract File | Deployed Address | Transaction Hash | Consensus Pattern |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **MilestoneEscrow** | [`milestone_escrow.py`](contracts/milestone_escrow.py) | [`0x66138e7F98A9CaEF7250f6619cc54d6dF4134140`](https://explorer-studio.genlayer.com/address/0x66138e7F98A9CaEF7250f6619cc54d6dF4134140) | `0xfccf20d6fbc071dd0ef8404bc2a78d21ddccdbea0521403b9e8eb8dae27f402c` | Web Evidence Comparative Consensus |
| 2 | **IntentSolverVerifier** | [`intent_solver_verifier.py`](contracts/intent_solver_verifier.py) | [`0x17fCdDCCc704f912Ca8737e180bC59d9dB4c80A1`](https://explorer-studio.genlayer.com/address/0x17fCdDCCc704f912Ca8737e180bC59d9dB4c80A1) | `0x58e5c046d55863c009d229f26c8fc0aadc36e6132684c97e8bbafae72294cacb` | Solver Routing Intent Audit |
| 3 | **SemanticDAOGuard** | [`semantic_dao_guard.py`](contracts/semantic_dao_guard.py) | [`0x260c37fD22DCa0A8d519903113681ef55f8ABFf3`](https://explorer-studio.genlayer.com/address/0x260c37fD22DCa0A8d519903113681ef55f8ABFf3) | `0x30d11ba576788d2d3ae0f7da38b2f0e912d02a8b2570d2ec6ea0d7cb36eeb304` | Plain-Text Constitutional Timelock |
| 4 | **AgentSlasher** | [`agent_slasher.py`](contracts/agent_slasher.py) | [`0x4Cb0d78790A58cFCBB01e1b18bdad399d202e098`](https://explorer-studio.genlayer.com/address/0x4Cb0d78790A58cFCBB01e1b18bdad399d202e098) | `0x6d420698047fd01ca38e4098a2bfb648b01b004263355ccb45df88fb6d673dc9` | Bot Policy Staking & Slashing |
| 5 | **SpecBounty** | [`spec_bounty.py`](contracts/spec_bounty.py) | [`0xf9451c01522063BE7f2b41E95fd10f84a695aC23`](https://explorer-studio.genlayer.com/address/0xf9451c01522063BE7f2b41E95fd10f84a695aC23) | `0x9bc104c9b56205b4468bd78fbb3582fe0bebac350321034dc3ac44cfbcc45341` | Scope-Gated Bug Bounty Pool |
| 6 | **DisputeCourt** | [`dispute_court.py`](contracts/dispute_court.py) | [`0x5c3fa2bDF022ac31724963C53285d565FCc189B3`](https://explorer-studio.genlayer.com/address/0x5c3fa2bDF022ac31724963C53285d565FCc189B3) | `0x99030cc43b24fcd98a1f1ebb658d4b0211dcc3f9dcbd9c60266819f86d6f41a2` | Ambiguity Fallback Arbitration |
| 7 | **CrossLingualOracle** | [`cross_lingual_oracle.py`](contracts/cross_lingual_oracle.py) | [`0x5c6Eeef3338A63EbADb2FEA12fa94847A6af469d`](https://explorer-studio.genlayer.com/address/0x5c6Eeef3338A63EbADb2FEA12fa94847A6af469d) | `0x09ca249ff63289b8f78bc30b71064e8b6a92c1b3df63166a878d8c5e36923217` | Multilingual News Corroboration |
| 8 | **MultiSourceInsurance** | [`multi_source_insurance.py`](contracts/multi_source_insurance.py) | [`0x2585C52fdC2B463Af9522EecD60027eDBfb3e3D4`](https://explorer-studio.genlayer.com/address/0x2585C52fdC2B463Af9522EecD60027eDBfb3e3D4) | `0xf87b7ef89ed9161779b8a20d63ae9adcb4842063121368692693caa433030816` | Multi-Feed Disaster Insurance |

---

## Architectural Principles

### 1. Quarantined Non-Determinism
LLM calls (`gl.nondet.exec_prompt`) and web fetches (`gl.nondet.web.render`) are isolated inside zero-argument closure functions. The closures read immutable local copies of storage data, never touch `self`, and return canonicalized JSON data.

### 2. Independent Deterministic Validation
Consequential prompt outputs are never trusted unconditionally. Every contract independently validates consensus decisions with strict `require(...)` assertions before mutating state, deducting balances, or crediting funds.

### 3. Pull-Payment Accounting
State settlement methods never directly push native funds. Instead, verified payouts are credited to an isolated `claimable: TreeMap[Address, u256]` ledger. Claimants invoke `withdraw()` to emit native transfers (`_NativeRecipient.emit_transfer`).

### 4. Pinned Runner & Pure ASCII
Every contract pins runner dependency `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }` and enforces 100% pure ASCII encoding.

---

## Verification & Testing

### 1. Run GenVM Source Checks (Linter)
```bash
python scripts/lint_contracts.py
```
Validates:
- Pure ASCII encoding (no UTF-8 BOM)
- Python syntax compilation
- Pinned runner content hash
- Mandatory docstrings (`PURPOSE`, `CONSENSUS`, `STATE DESIGN`, `REUSE`)
- Public return type annotations
- GenVM storage types (`u256`, `Address`, `TreeMap`, `DynArray`)
- Absence of custom appeal/reroll methods
- Balance-depleting payout paths emit native transfer

### 2. Run Test Suite
```bash
pytest -v
```
Runs 33 test cases covering syntax, lint rules, boundary invariants, JSON cleaners, and pull-payment accounting.

---

## Detailed Documentation
- [`CONTRACTS.md`](CONTRACTS.md): Full technical specifications, constructor parameters, storage layouts, and failure modes for each contract.
- [`DECISIONS.md`](DECISIONS.md): Architectural design decisions and migration logs.
