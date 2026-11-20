"""
Database tools for Database Agent and MCP Server.

Provides safe, audited database interactions:
- Schema discovery: list_tables, describe_table
- Safe query execution: execute_read_query (enforces read-only safety, query validation, row limits)
- Sample row inspection: get_sample_rows
- Auto-initializes a sample SQLite database (customers, products, orders) if none exists.
"""

import logging
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_db_lock = threading.Lock()


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get SQLite database connection, ensuring directories exist and sample data is initialized."""
    target_path = db_path or settings.DATABASE_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)

    with _db_lock:
        conn = sqlite3.connect(target_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _init_sample_database(conn)
        return conn


def _init_sample_database(conn: sqlite3.Connection) -> None:
    """Initialize sample tables and records if database is empty."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='customers'"
    )
    if cursor.fetchone()[0] == 0:
        logger.info("Initializing sample database schema (customers, products, orders)...")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                total_spend REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL,
                stock_quantity INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );

            INSERT INTO customers (name, email, company, total_spend, status) VALUES
                ('Alice Johnson', 'alice@acme.com', 'Acme Corp', 14500.0, 'active'),
                ('Bob Smith', 'bob@globex.org', 'Globex', 8200.0, 'active'),
                ('Charlie Brown', 'charlie@initech.com', 'Initech', 23400.0, 'active'),
                ('Diana Prince', 'diana@themyscira.io', 'Themyscira Inc', 19800.0, 'active'),
                ('Ethan Hunt', 'ethan@imf.gov', 'Impossible Logistics', 5400.0, 'active');

            INSERT INTO products (product_name, category, unit_price, stock_quantity) VALUES
                ('AI Analytics Suite', 'Software', 1200.0, 50),
                ('Cloud Orchestrator', 'Infrastructure', 2400.0, 25),
                ('Vector Index Gateway', 'Software', 850.0, 100),
                ('Edge Agent Hardware', 'Hardware', 450.0, 15);

            INSERT INTO orders (customer_id, product_id, order_date, quantity, total_amount) VALUES
                (1, 1, '2026-03-01', 5, 6000.0),
                (3, 2, '2026-03-05', 4, 9600.0),
                (4, 1, '2026-03-10', 8, 9600.0),
                (3, 3, '2026-03-12', 10, 8500.0),
                (2, 4, '2026-03-14', 6, 2700.0);
            """
        )
        conn.commit()


def list_tables(db_path: Optional[str] = None) -> List[str]:
    """Return list of user tables in the database."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        return [row[0] for row in cursor.fetchall()]


def describe_table(table_name: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Inspect schema and columns of a table."""
    cleaned = table_name.strip()
    if not re.match(r"^[a-zA-Z0-9_]+$", cleaned):
        return {"error": f"Invalid table name '{table_name}'."}

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({cleaned});")
        columns = [
            {
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "dflt_value": row[4],
                "pk": bool(row[5]),
            }
            for row in cursor.fetchall()
        ]
        if not columns:
            return {"error": f"Table '{table_name}' not found."}
        return {"table": cleaned, "columns": columns}


def is_safe_read_query(query: str) -> bool:
    """Verify that query is strictly a read operation (SELECT, EXPLAIN, PRAGMA)."""
    cleaned = query.strip()
    # Remove leading comments
    cleaned = re.sub(r"^/\*.*?\*/", "", cleaned, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^--.*?\n", "", cleaned).strip()

    # Must start with SELECT, EXPLAIN, or PRAGMA
    if not re.match(r"^(SELECT|EXPLAIN|PRAGMA)\b", cleaned, re.IGNORECASE):
        return False

    # Block destructive keywords anywhere in query
    forbidden = [
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bDROP\b",
        r"\bALTER\b",
        r"\bTRUNCATE\b",
        r"\bCREATE\b",
        r"\bREPLACE\b",
        r"\bATTACH\b",
        r"\bDETACH\b",
    ]
    for pattern in forbidden:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return False

    return True


def execute_read_query(
    query: str,
    params: Optional[List[Any]] = None,
    max_rows: int = 100,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Safely execute a read-only SQL query with security validation and row limits.

    Args:
        query: SQL SELECT query string.
        params: Optional query parameters.
        max_rows: Maximum rows to return (default: 100).
        db_path: Optional SQLite database file path.

    Returns:
        Dict with 'columns', 'rows', 'row_count', or 'error'.
    """
    logger.info("[DB Tool] Validating read query: %s", query[:120])

    if settings.DATABASE_READ_ONLY and not is_safe_read_query(query):
        logger.warning("[DB Tool] Rejected unsafe non-read query: %s", query)
        return {
            "error": "Query rejected by database security policy. Only read-only operations (SELECT) are permitted."
        }

    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            rows_raw = cursor.fetchmany(max_rows)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row)) for row in rows_raw]

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "capped": len(rows) == max_rows,
            }
    except Exception as err:
        logger.error("[DB Tool] SQL execution error: %s", err)
        return {"error": f"SQL execution error: {str(err)}"}


def get_sample_rows(table_name: str, limit: int = 5, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Get sample rows from a table."""
    cleaned = table_name.strip()
    if not re.match(r"^[a-zA-Z0-9_]+$", cleaned):
        return {"error": f"Invalid table name '{table_name}'."}

    query = f"SELECT * FROM {cleaned} LIMIT {max(1, min(limit, 20))};"
    return execute_read_query(query, db_path=db_path)
