import sqlite3
import os

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pinance.db")

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
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

        CREATE TABLE IF NOT EXISTS categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'exclude'))
        );

        CREATE TABLE IF NOT EXISTS category_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword     TEXT    NOT NULL,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            target      TEXT    NOT NULL DEFAULT 'both'
                        CHECK(target IN ('bank', 'card', 'both')),
            UNIQUE(keyword, target)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    # 既存テーブルに category_id 列を追加（既存 DB のマイグレーション）
    for table in ("bank_transactions", "card_transactions"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "category_id" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN category_id INTEGER REFERENCES categories(id)")

    # シードデータ：カード引き落とし用の除外カテゴリ
    conn.execute(
        "INSERT OR IGNORE INTO categories (name, type) VALUES ('カード引き落とし', 'exclude')"
    )
    conn.execute(
        """INSERT OR IGNORE INTO category_rules (keyword, category_id, target)
           SELECT 'ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ', id, 'bank' FROM categories WHERE name = 'カード引き落とし'"""
    )
    # シードデータ：LLM設定のデフォルト値
    for key, value in [
        ("llm_provider", "ollama"),
        ("llm_model", "gemma3:4b-it-qat"),
        ("llm_base_url", "http://localhost:11434"),
        ("llm_api_key", ""),
    ]:
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            [key, value],
        )
    conn.commit()
    conn.close()
