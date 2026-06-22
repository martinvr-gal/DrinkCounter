from __future__ import annotations

from pathlib import Path

from .storage import CounterStorage


class CounterService:
    def __init__(self, db_path: str | Path) -> None:
        self.storage = CounterStorage(db_path)

    def get_counter(self) -> int:
        return self.storage.get_value()

    def increment(self, amount: int = 1) -> int:
        return self.storage.increment(amount)

    def decrement(self, amount: int = 1) -> int:
        return self.storage.decrement(amount)

    def set_counter(self, value: int) -> int:
        return self.storage.set_value(value)
