# Slate: Minimal Consensus Primitives for GenLayer

A library of 8 standalone GenLayer Intelligent Contract primitives exploring semantic consensus, web corroboration, and deterministic pull-payment ledgers.

Traditional smart contracts only reach consensus on arithmetic calculations. GenLayer expands consensus to qualitative evaluation, natural language agreements, cross-lingual news, and plain-text governance rules.

---

## Deployed Primitives on Studionet

All 8 contracts are deployed and verified on the GenLayer Studio Network (`studionet`):

| # | Primitive | Contract File | Deployed Address | Transaction Hash | Consensus Pattern |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **MilestoneEscrow** | [`milestone_escrow.py`](contracts/milestone_escrow.py) | [`0x66138e7F98A9CaEF7250f6619cc54d6dF4134140`](https://explorer-studio.genlayer.com/address/0x66138e7F98A9CaEF7250f6619cc54d6dF4134140) | `0xfccf20d6fbc071dd0ef8404bc2a78d21ddccdbea0521403b9e8eb8dae27f402c` | Web Evidence Comparative Consensus |
| 2 | **IntentSolverVerifier** | [`intent_solver_verifier.py`](contracts/intent_solver_verifier.py) | [`0x61631822286c65b7B9078ee7dfc7C64D1981e88c`](https://explorer-studio.genlayer.com/address/0x61631822286c65b7B9078ee7dfc7C64D1981e88c) | `0x55a9727c5d1fcf4d35ed474a353777911c92d5d108939ddeca2805bd0ced6a42` | Authoritative On-Chain Evidence Audit |
| 3 | **SemanticDAOGuard** | [`semantic_dao_guard.py`](contracts/semantic_dao_guard.py) | [`0x260c37fD22DCa0A8d519903113681ef55f8ABFf3`](https://explorer-studio.genlayer.com/address/0x260c37fD22DCa0A8d519903113681ef55f8ABFf3) | `0x30d11ba576788d2d3ae0f7da38b2f0e912d02a8b2570d2ec6ea0d7cb36eeb304` | Plain-Text Constitutional Timelock |
| 4 | **AgentSlasher** | [`agent_slasher.py`](contracts/agent_slasher.py) | [`0x9B76cD8bCd2EB012cd2018dE59B930e0B4d78CF9`](https://explorer-studio.genlayer.com/address/0x9B76cD8bCd2EB012cd2018dE59B930e0B4d78CF9) | `0x7db9e4439d4a090d9b43c235b2e86fa621e2ab3e998c3be27ffd4911c338ef04` | Canonical Bucket Staking & Slashing |
| 5 | **SpecBounty** | [`spec_bounty.py`](contracts/spec_bounty.py) | [`0x02A3ef75206C58D49201a4E66249f0f57C5d8D47`](https://explorer-studio.genlayer.com/address/0x02A3ef75206C58D49201a4E66249f0f57C5d8D47) | `0xcf4699750e9b52e74e9c3f9af63fb060698f85bf5ad2cef652a5aedab9b37e15` | Canonical Severity Tier Bug Bounty |
| 6 | **DisputeCourt** | [`dispute_court.py`](contracts/dispute_court.py) | [`0x5c3fa2bDF022ac31724963C53285d565FCc189B3`](https://explorer-studio.genlayer.com/address/0x5c3fa2bDF022ac31724963C53285d565FCc189B3) | `0x99030cc43b24fcd98a1f1ebb658d4b0211dcc3f9dcbd9c60266819f86d6f41a2` | Ambiguity Fallback Arbitration |
| 7 | **CrossLingualOracle** | [`cross_lingual_oracle.py`](contracts/cross_lingual_oracle.py) | [`0x5c6Eeef3338A63EbADb2FEA12fa94847A6af469d`](https://explorer-studio.genlayer.com/address/0x5c6Eeef3338A63EbADb2FEA12fa94847A6af469d) | `0x09ca249ff63289b8f78bc30b71064e8b6a92c1b3df63166a878d8c5e36923217` | Multilingual News Corroboration |
| 8 | **MultiSourceInsurance** | [`multi_source_insurance.py`](contracts/multi_source_insurance.py) | [`0xB01f2103b82c720E08aCBeB91bCEE1bCd5535cC0`](https://explorer-studio.genlayer.com/address/0xB01f2103b82c720E08aCBeB91bCEE1bCd5535cC0) | `0x49b8d5a69449bbb47f4be572a927dfb23a26beba4c9da99ca6942fc760c42d92` | Canonical Disaster Tier Insurance |

---

## Architectural Principles

### 1. Quarantined Non-Determinism
LLM calls (`gl.nondet.exec_prompt`) and web fetches (`gl.nondet.web.render`) are isolated inside zero-argument closure functions. The closures read immutable local copies of storage data, never touch `self`, and return canonicalized JSON data.

### 2. Independent Deterministic Validation & Canonical Discrete Buckets
Consequential prompt outputs are never trusted unconditionally. Every contract independently validates consensus decisions with strict `require(...)` assertions before mutating state, deducting balances, or crediting funds. Variable payout paths bind to exact canonical discrete buckets (`NONE`, `MINOR`, `MAJOR`, `CRITICAL`, `CATASTROPHIC`), preventing payout divergence under comparative consensus.

### 3. Pull-Payment Accounting
State settlement methods never directly push native funds. Instead, verified payouts are credited to an isolated `claimable: TreeMap[Address, u256]` ledger. Claimants invoke `withdraw()` to emit native transfers (`_NativeRecipient.emit_transfer`).

### 4. Authoritative Web Evidence
High-stakes settlement verifiers (such as `MilestoneEscrow` and `IntentSolverVerifier`) independently retrieve authoritative evidence directly from the web or block explorers via `gl.nondet.web.render` rather than trusting caller-provided receipts.

### 5. Pinned Runner & Pure ASCII
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
Runs 45 test cases covering syntax, lint rules, boundary invariants, canonical discrete buckets, JSON cleaners, and pull-payment accounting.

---

## Detailed Documentation
- [`CONTRACTS.md`](CONTRACTS.md): Full technical specifications, constructor parameters, storage layouts, and failure modes for each contract.
- [`DECISIONS.md`](DECISIONS.md): Architectural design decisions and migration logs.
