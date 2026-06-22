from __future__ import annotations

from pathlib import Path
from threading import RLock
import sqlite3


class CounterStorage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS counter_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    value INTEGER NOT NULL CHECK (value >= 0)
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO counter_state (id, value) VALUES (1, 0)"
            )
            connection.commit()

    def get_value(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM counter_state WHERE id = 1"
            ).fetchone()
            if row is None:
                return 0
            return int(row["value"])

    def set_value(self, value: int) -> int:
        if value < 0:
            raise ValueError("Counter value cannot be negative")
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO counter_state (id, value)
                    VALUES (1, ?)
                    ON CONFLICT(id) DO UPDATE SET value = excluded.value
                    """,
                    (value,),
                )
                connection.commit()
        return value

    def increment(self, amount: int) -> int:
        if amount <= 0:
            raise ValueError("Increment amount must be positive")
        with self._lock:
            current_value = self.get_value()
            new_value = current_value + amount
            return self.set_value(new_value)

    def decrement(self, amount: int) -> int:
        if amount <= 0:
            raise ValueError("Decrement amount must be positive")
        with self._lock:
            current_value = self.get_value()
            new_value = max(0, current_value - amount)
            return self.set_value(new_value)
