from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.schemas import Paper


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


class SQLiteMemoryStore:
    """Persistent long-term storage for papers, summaries, chat logs and memories."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS papers (
                    arxiv_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors_json TEXT NOT NULL,
                    abstract TEXT NOT NULL,
                    pdf_url TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    published TEXT,
                    updated TEXT,
                    categories_json TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    arxiv_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_chat_logs_session
                    ON chat_logs(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_kind
                    ON memories(kind, created_at);
                CREATE INDEX IF NOT EXISTS idx_summaries_arxiv
                    ON summaries(arxiv_id, created_at);
                """
            )

    def store_chat_log(self, session_id: str, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_logs(session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, _now()),
            )

    def upsert_paper(self, paper: Paper) -> None:
        payload = paper.model_dump()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO papers(
                    arxiv_id, title, authors_json, abstract, pdf_url, source_url,
                    published, updated, categories_json, raw_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(arxiv_id) DO UPDATE SET
                    title = excluded.title,
                    authors_json = excluded.authors_json,
                    abstract = excluded.abstract,
                    pdf_url = excluded.pdf_url,
                    source_url = excluded.source_url,
                    published = excluded.published,
                    updated = excluded.updated,
                    categories_json = excluded.categories_json,
                    raw_json = excluded.raw_json,
                    updated_at = excluded.updated_at
                """,
                (
                    paper.arxiv_id,
                    paper.title,
                    json.dumps(paper.authors, ensure_ascii=False),
                    paper.abstract,
                    paper.pdf_url,
                    paper.source_url,
                    paper.published,
                    paper.updated,
                    json.dumps(paper.categories, ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                    _now(),
                    _now(),
                ),
            )

    def store_summary(
        self,
        arxiv_id: str,
        title: str,
        summary: str,
        skill_name: str = "paper_summary_skill",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO summaries(arxiv_id, title, summary, skill_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (arxiv_id, title, summary, skill_name, _now()),
            )

    def store_memory(
        self,
        content: str,
        kind: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories(session_id, kind, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    kind,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    _now(),
                ),
            )

    def get_recent_chat(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM chat_logs
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def list_recent_papers(self, limit: int = 10) -> list[Paper]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT raw_json
                FROM papers
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [Paper(**json.loads(row["raw_json"])) for row in rows]

