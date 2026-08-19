import os
import time
import sqlite3

from vesper.config import get_vesper_home

MEMORY_TOKEN_CAP = 8000

def estimate_tokens(text: str) -> int:
    """Approximates the token count of a string for overflow truncation."""
    return max(1, len(text) // 4)

class MemoryStore:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(get_vesper_home(), "memory.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.setup_tables()

    def _get_connection(self):
        """Helper method to get a configured database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_tables(self) -> None:
        """Creates the 'memory' table if it does not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tokens INTEGER NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

    def load(self, agent_name: str, scope_key: str, retention_days: int) -> list:
        """Loads the retained conversation history, truncating oldest turns past the token cap."""
        cutoff = time.time() - retention_days * 86400

        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM memory WHERE agent_name = ? AND scope_key = ? AND created_at < ?",
                (agent_name, scope_key, cutoff)
            )
            rows = conn.execute(
                "SELECT role, content, tokens FROM memory WHERE agent_name = ? AND scope_key = ? ORDER BY created_at ASC, id ASC",
                (agent_name, scope_key)
            ).fetchall()

        total = sum(row["tokens"] for row in rows)
        start = 0
        while total > MEMORY_TOKEN_CAP and start < len(rows):
            total -= rows[start]["tokens"]
            start += 1

        return [{"role": row["role"], "content": row["content"]} for row in rows[start:]]

    def save(self, agent_name: str, scope_key: str, messages: list) -> None:
        """Appends conversation turns to the store."""
        now = time.time()
        with self._get_connection() as conn:
            for message in messages:
                conn.execute(
                    "INSERT INTO memory (agent_name, scope_key, role, content, tokens, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (agent_name, scope_key, message["role"], message["content"], estimate_tokens(message["content"]), now)
                )

    def delete(self, agent_name: str) -> None:
        """Deletes all stored memory for an agent."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM memory WHERE agent_name = ?", (agent_name,))
