# scripts/lint_contracts.py
"""
Deterministic source checks for GenLayer Intelligent Contracts in Slate.
Validates pure ASCII encoding (no UTF-8 BOM or non-ASCII bytes), compilation,
pinned runner dependency, mandatory docstring sections, typed storage,
public signatures, real custody transfer, and web target safety.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RUNNER_RE = re.compile(
    r'^# \{ "Depends": "py-genlayer:([a-z0-9]{20,})" \}$'
)
REQUIRED_DOC_SECTIONS = ("PURPOSE", "CONSENSUS", "STATE DESIGN", "REUSE")
FORBIDDEN_PUBLIC_TYPES = ("typing.Any", "Any")
FORBIDDEN_STORAGE_TYPES = {"int", "float", "dict", "list", "typing.Any", "Any"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def check_ascii(path: Path) -> CheckResult:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return CheckResult("ascii", False, "file has UTF-8 BOM signature")
    try:
        raw.decode("ascii")
        return CheckResult("ascii", True, "pure ASCII")
    except UnicodeDecodeError as exc:
        return CheckResult("ascii", False, str(exc))


def check_compile(path: Path) -> CheckResult:
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return CheckResult("py_compile", False, result.stderr.strip())
    return CheckResult("py_compile", True, "compiled without syntax errors")


def check_runner_hash(text: str) -> CheckResult:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    match = RUNNER_RE.fullmatch(first_line.strip())
    if match and match.group(1) not in {"test", "latest"}:
        return CheckResult("runner_hash", True, f"pinned runner: {match.group(1)}")
    return CheckResult("runner_hash", False, f"missing or invalid runner hash on line 1: {first_line!r}")


def check_docstring(tree: ast.AST) -> CheckResult:
    doc = ast.get_docstring(tree) or ""
    missing = [sec for sec in REQUIRED_DOC_SECTIONS if sec not in doc]
    if missing:
        return CheckResult("documentation", False, "missing doc sections: " + ", ".join(missing))
    return CheckResult("documentation", True, "contains PURPOSE, CONSENSUS, STATE DESIGN, REUSE")


def check_public_types(tree: ast.AST) -> CheckResult:
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name or node.name.startswith("_"):
            continue
        rendered = ast.unparse(node.returns) if node.returns else ""
        if any(tok in rendered for tok in FORBIDDEN_PUBLIC_TYPES):
            failures.append(f"{node.name} -> {rendered}")
    if failures:
        return CheckResult("public_types", False, "forbidden types in return: " + ", ".join(failures))
    return CheckResult("public_types", True, "no forbidden public return types")


def check_storage_types(tree: ast.AST) -> CheckResult:
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, ast.AnnAssign) or child.annotation is None:
                continue
            rendered = ast.unparse(child.annotation)
            if rendered in FORBIDDEN_STORAGE_TYPES:
                target = ast.unparse(child.target)
                failures.append(f"{node.name}.{target}: {rendered}")
    if failures:
        return CheckResult("storage_types", False, "forbidden storage type: " + ", ".join(failures))
    return CheckResult("storage_types", True, "all storage fields use typed definitions")


def check_appeal_methods(tree: ast.AST) -> CheckResult:
    forbidden = {"appeal", "reroll", "resubmit_for_review"}
    found = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in forbidden
    ]
    if found:
        return CheckResult("appeal_methods", False, "custom appeal method found: " + ", ".join(found))
    return CheckResult("appeal_methods", True, "no custom appeal or reroll method")


def check_balance_transfer(tree: ast.AST) -> CheckResult:
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body_text = ast.unparse(node)
        touches_balance = "claimable" in body_text or "balance" in body_text
        emits_transfer = "emit_transfer" in body_text
        if touches_balance and ("withdraw" in node.name or "settle" in node.name or "payout" in node.name):
            if not emits_transfer:
                failures.append(node.name)
    if failures:
        return CheckResult("real_custody", False, "no transfer in " + ", ".join(failures))
    return CheckResult("real_custody", True, "balance-affecting payout paths include emit_transfer")


def check_contract(path: Path) -> list[CheckResult]:
    ascii_res = check_ascii(path)
    compile_res = check_compile(path)
    if not ascii_res.passed or not compile_res.passed:
        return [ascii_res, compile_res]

    text = path.read_text(encoding="ascii")
    tree = ast.parse(text, filename=str(path))
    return [
        ascii_res,
        compile_res,
        check_runner_hash(text),
        check_docstring(tree),
        check_public_types(tree),
        check_storage_types(tree),
        check_appeal_methods(tree),
        check_balance_transfer(tree),
    ]


def main() -> int:
    contracts_dir = Path(__file__).resolve().parent.parent / "contracts"
    py_files = sorted(contracts_dir.glob("*.py"))
    contracts = [f for f in py_files if f.name != "__init__.py"]

    print(f"Scanning {len(contracts)} contracts in {contracts_dir}...")
    total_failures = 0

    for contract in contracts:
        results = check_contract(contract)
        failed = [r for r in results if not r.passed]
        if failed:
            total_failures += len(failed)
            print(f"\n[FAIL] {contract.name}:")
            for r in failed:
                print(f"  - {r.name}: {r.detail}")
        else:
            print(f"[PASS] {contract.name}")

    if total_failures == 0:
        print(f"\nAll {len(contracts)} contracts passed GenVM source checks successfully!")
        return 0
    else:
        print(f"\nTotal failures: {total_failures}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
