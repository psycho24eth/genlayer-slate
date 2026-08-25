# slate

A library of 8 standalone GenLayer Intelligent Contracts built around semantic verification, live web corroboration, and deterministic pull-payment ledgers.

Traditional smart contracts only reach consensus on arithmetic calculations. GenLayer expands consensus to qualitative evaluation, natural language agreements, cross-lingual news, and plain-text governance rules.

## Core Primitives

### 1. Escrow & Agreements
- **milestone_escrow.py**: Web-verified milestone release for freelance and vendor deliverables.
- **intent_solver_verifier.py**: Verifies that off-chain intent solvers (DEX routing, Account Abstraction) matched user constraints.

### 2. Governance & Security
- **semantic_dao_guard.py**: Audits DAO proposal execution payloads against written constitutions to block Trojan governance attacks.
- **gent_slasher.py**: Staking and slash enforcement contract for off-chain automation bots violating policy.
- **spec_bounty.py**: Automated bounty pool triaging submissions against a written scope policy.

### 3. Oracles & Arbitration
- **dispute_court.py**: Two-party arbitration contract with variance check to safely split funds when evidence is ambiguous.
- **cross_lingual_oracle.py**: Ingests multilingual web sources (e.g. Japanese, Spanish) to verify international consensus.
- **multi_source_insurance.py**: Parametric insurance requiring multi-source corroboration before release.

## Running Tests

`ash
pytest tests/
`
