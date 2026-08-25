# slate

A small library of standalone GenLayer Intelligent Contracts built around semantic verification, web evidence, and pull-payment state management.

Traditional smart contracts only verify exact math calculations. GenLayer lets validators reach consensus on unstructured text, live web data, and natural language rules. slate provides 4 self-contained contracts that demonstrate how to structure these systems safely.

## Contracts

- milestone_escrow.py: Locks escrow funds for freelance or vendor work. Validators fetch live web pages and compare them against plain-text specs before releasing funds.
- spec_bounty.py: Bounty pool that reviews submitted bug reports or PRs against a written scope policy and pays out according to classified severity.
- dispute_court.py: Two-party arbitration contract. If validator disagreement exceeds a configured variance threshold, funds split evenly rather than forcing a binary decision on uncertain evidence.
- agent_slasher.py: Staking contract for off-chain bots. Evaluates execution logs against the bot's declared policy and slashes stake on violations.

## Running Tests

pytest tests/
