import os
import sqlite3
from typing import Optional, List
from pydantic import BaseModel

from vesper.config import get_vesper_home

class RunRecord(BaseModel):
    run_id: str
    agent_name: str
    session_id: Optional[str] = None
    input: str
    output: Optional[str] = None
    cost: Optional[float] = None
    prompt_tokens: int
    completion_tokens: int
    status: str
    created_at: float

class AuditStore:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(get_vesper_home(), "audit.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.setup_tables()

    def _get_connection(self):
        """Helper method to get a configured database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_tables(self) -> None:
        """Creates the 'runs' table if it does not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    session_id TEXT,
                    input TEXT NOT NULL,
                    output TEXT,
                    cost REAL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

    def record(self, run: RunRecord) -> None:
        """Persists a single run record."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, agent_name, session_id, input, output, cost, prompt_tokens, completion_tokens, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run.run_id, run.agent_name, run.session_id, run.input, run.output, run.cost, run.prompt_tokens, run.completion_tokens, run.status, run.created_at)
            )

    def list(self, agent_name: str) -> List[RunRecord]:
        """Returns the run history for an agent, newest first."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE agent_name = ? ORDER BY created_at DESC",
                (agent_name,)
            ).fetchall()
        return [RunRecord(**dict(row)) for row in rows]

    def delete(self, agent_name: str) -> None:
        """Deletes all run history for an agent."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM runs WHERE agent_name = ?", (agent_name,))
