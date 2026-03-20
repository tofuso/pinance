import sqlite3
import os

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pinance.db")

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bank_transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            withdrawal  INTEGER NOT NULL DEFAULT 0,
            deposit     INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL,
            balance     INTEGER NOT NULL,
            UNIQUE(date, withdrawal, deposit, description, balance)
        );

        CREATE TABLE IF NOT EXISTS card_transactions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT NOT NULL,
            merchant     TEXT NOT NULL,
            amount       INTEGER NOT NULL,
            row_index    INTEGER NOT NULL,
            UNIQUE(date, merchant, amount, row_index)
        );
    """)
    conn.commit()
    conn.close()
