# tests/test_contracts_syntax_and_lint.py
"""
Unit tests validating that all Slate Intelligent Contracts adhere strictly to
GenVM source, typing, docstring, and custody transfer standards.
"""

from pathlib import Path
import pytest
from scripts.lint_contracts import check_contract


def get_contract_files():
    contracts_dir = Path(__file__).resolve().parent.parent / "contracts"
    return [p for p in sorted(contracts_dir.glob("*.py")) if p.name != "__init__.py"]


@pytest.mark.parametrize("contract_path", get_contract_files(), ids=lambda p: p.name)
def test_contract_passes_all_genvm_checks(contract_path):
    results = check_contract(contract_path)
    failures = [r for r in results if not r.passed]
    assert not failures, f"{contract_path.name} failed GenVM checks: " + "; ".join(
        f"{r.name}: {r.detail}" for r in failures
    )


def test_contract_count():
    files = get_contract_files()
    assert len(files) == 8, f"Expected 8 contracts in Slate library, found {len(files)}"
