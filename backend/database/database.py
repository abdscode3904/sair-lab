from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORAGE_DIR = PROJECT_ROOT / "storage"
DATABASE_PATH = STORAGE_DIR / "sair_lab.db"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """
    Create a SQLite connection for Sair Lab.
    """

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    """
    Create all required Sair Lab database tables.
    """

    with get_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT,
                plan TEXT NOT NULL DEFAULT 'free',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                usage_month TEXT NOT NULL,
                jobs_count INTEGER NOT NULL DEFAULT 0,
                total_bytes INTEGER NOT NULL DEFAULT 0,
                UNIQUE(customer_id, usage_month)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE NOT NULL,
                customer_id TEXT,
                operation TEXT,
                status TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_usage_customer_month
            ON usage(customer_id, usage_month)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_customer
            ON jobs(customer_id)
            """
        )

        connection.commit()


def execute(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> None:
    """
    Execute a write query.
    """

    with get_connection() as connection:
        connection.execute(query, parameters)
        connection.commit()


def fetch_one(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> dict[str, Any] | None:
    """
    Return one database row as a dictionary.
    """

    with get_connection() as connection:

        row = connection.execute(
            query,
            parameters,
        ).fetchone()

        if row is None:
            return None

        return dict(row)


def fetch_all(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    """
    Return all database rows as dictionaries.
    """

    with get_connection() as connection:

        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

        return [dict(row) for row in rows]

