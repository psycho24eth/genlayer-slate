# lib/ledger.py

class Ledger:
    """
    Standard pull-payment ledger.
    Separates state updates from transfers to prevent reentrancy and transfer failures.
    """
    def __init__(self):
        self._balances: dict[str, int] = {}
        self.total_locked: int = 0

    def credit(self, account: str, amount: int) -> None:
        assert amount > 0, "amount must be positive"
        self._balances[account] = self._balances.get(account, 0) + amount
        self.total_locked += amount

    def debit(self, account: str) -> int:
        amount = self._balances.get(account, 0)
        assert amount > 0, "insufficient balance"
        self._balances[account] = 0
        self.total_locked -= amount
        return amount

    def get_balance(self, account: str) -> int:
        return self._balances.get(account, 0)
