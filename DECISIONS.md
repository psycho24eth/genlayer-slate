# DECISIONS -- Slate

This document records the architectural decisions, migration rationale, and security invariants adopted across the **Slate** Intelligent Contract library.

---

## 1. Migration from Prototype to Current GenVM SDK

### Context & Steward Feedback
The initial submission was rejected due to four fundamental issues:
1. Contracts did not pass GenVM source checks (unsupported `@gl.contract` decorator, `gl.get_webpage()`, `gl.exec_prompt()`).
2. Consequential prompt results directly altered state and released funds without independent validation.
3. Untyped storage collections (`dict`, `list`, raw `int`) and UTF-8 byte order mark (BOM) signatures failed the compiler/linter.
4. Explorer addresses had no matching deployed contracts.

### Decisions Made
- **Pinned Runner Hash**: Every contract defines `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }` on line 1, ensuring deterministic execution on the current GenVM testnet runner.
- **Pure ASCII Encoding**: All files are stripped of UTF-8 BOM markers (`0xEF 0xBB 0xBF`) and non-ASCII characters, validated by our automated lint suite.
- **Single-File Standalone Architecture**: GenVM contracts run as isolated single-file Python modules. All necessary consensus helpers, canonical serialization, and EVM interface adapters are self-contained within each file.
- **Inheritance from `gl.Contract`**: Replaced obsolete `@gl.contract` decorators with `class ContractName(gl.Contract):`.

---

## 2. Quarantining Non-Determinism and Consensus Equivalence

### The Cardinal Rule
Non-deterministic operations (calling LLMs, fetching external webpages) are inherently variable across validator nodes. They **must never touch `self` or write to storage**.

### Implementation Pattern
1. Read all needed storage fields into plain local variables before entering the non-deterministic block.
2. Encapsulate all non-deterministic logic in an argument-free inner closure:
   ```python
   def evaluate_milestone() -> str:
       # Local reads only; no self access
       ...
       return canonical({...})
   ```
3. Wrap all web network calls (`gl.nondet.web.render`) in `try/except` blocks so that offline domains or timeouts degrade into an explicit failure signal rather than aborting the transaction.
4. Execute consensus using the appropriate Equivalence Principle:
   ```python
   agreed = gl.eq_principle.prompt_comparative(evaluate_milestone, principle)
   ```

---

## 3. Independent Deterministic Validation

### The Problem
A major vulnerability in naive AI smart contracts is allowing an LLM's raw output to directly set state or disburse funds. An adversarial prompt injection or hallucinated token could credit unintended addresses or drain pools.

### The Solution
Every contract strictly enforces independent deterministic validation after consensus lands:
1. Parse the consensus result into structured data.
2. Re-derive the expected deterministic action from contract parameters and consensus values:
   ```python
   expected_action = "SETTLE" if (passed and conf_milli >= threshold) else "REFUND"
   require(action == expected_action, "consequential action violates policy bounds")
   ```
3. Only if the derived action matches the agreed consensus outcome does the contract proceed with state or ledger modifications.

---

## 4. Integer Scaling vs Floating Point Drift

### Decision
Floats are permitted inside non-deterministic closures (where LLMs return probabilities between `0.0` and `1.0`), but are **strictly banned from on-chain storage and comparisons**.

### Scale Factors
- Confidences, merit scores, and risk scores are scaled to milli-units (`_MILLI = 1000`):
  `0.85 -> 850 milli-units`.
- Percentages are represented as exact integers (`0..100`).
- Storage uses `u256` integers exclusively for financial quantities and timestamps.

---

## 5. Pull-Payment Accounting & Custody Transfer

### Decision
Direct native token transfers inside complex decision paths (`evaluate()`, `slash()`, `settle()`) introduce reentrancy and unexpected revert risks.

### Architecture
1. In-contract accounting is held in an isolated `claimable: TreeMap[Address, u256]` ledger.
2. State settlement methods only credit the `claimable` ledger.
3. Users and contractors call a dedicated `withdraw()` method to claim their balance:
   ```python
   @gl.public.write
   def withdraw(self) -> None:
       bal = int(self.claimable.get(gl.message.sender_address, u256(0)))
       require(bal > 0, "no claimable balance")
       self.claimable[gl.message.sender_address] = u256(0)
       _NativeRecipient(gl.message.sender_address).emit_transfer(value=u256(bal))
   ```
4. Transfers interface directly with EVM native emission (`_NativeRecipient.emit_transfer`).

---

## 6. Verification and Studionet Deployment

### Verification Evidence
- `scripts/lint_contracts.py` validates all 8 contracts against the 8 GenVM checks:
  1. Pure ASCII encoding
  2. Syntax compilation (`py_compile`)
  3. Pinned runner hash
  4. Mandatory docstrings (`PURPOSE`, `CONSENSUS`, `STATE DESIGN`, `REUSE`)
  5. Public return type safety
  6. Storage type safety (`u256`, `Address`, `TreeMap`, `DynArray`)
  7. No custom appeal/reroll methods
  8. Balance payout paths emit native transfer
- Full pytest test suite (`pytest -v`) passed with 33 test cases.
- All 8 contracts successfully deployed to Studionet with 5 validator consensus (`MAJORITY_AGREE`, status: `ACCEPTED`).
