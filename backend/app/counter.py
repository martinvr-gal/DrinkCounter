from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock


class CounterStorage:
    """Persistent counter stored separately from the gallery database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
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

    def get_value(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM counter_state WHERE id = 1"
            ).fetchone()
        return int(row["value"]) if row else 0

    def set_value(self, value: int) -> int:
        if value < 0:
            raise ValueError("El contador no puede ser negativo.")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO counter_state (id, value) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET value = excluded.value
                """,
                (value,),
            )
        return value

    def increment(self, amount: int) -> int:
        if amount <= 0:
            raise ValueError("El incremento debe ser positivo.")
        with self._lock:
            return self.set_value(self.get_value() + amount)

    def decrement(self, amount: int) -> int:
        if amount <= 0:
            raise ValueError("El decremento debe ser positivo.")
        with self._lock:
            return self.set_value(max(0, self.get_value() - amount))


class CounterService:
    def __init__(self, database_path: str | Path) -> None:
        self.storage = CounterStorage(database_path)

    def get_counter(self) -> int:
        return self.storage.get_value()

    def increment(self, amount: int = 1) -> int:
        return self.storage.increment(amount)

    def decrement(self, amount: int = 1) -> int:
        return self.storage.decrement(amount)

    def set_counter(self, value: int) -> int:
        return self.storage.set_value(value)
