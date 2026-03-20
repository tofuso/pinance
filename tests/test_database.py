import sqlite3
from pinance.database import init_db

def test_init_db_creates_bank_transactions_table(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    conn = sqlite3.connect(path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='bank_transactions'"
    )
    assert cursor.fetchone() is not None
    conn.close()

def test_init_db_creates_card_transactions_table(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    conn = sqlite3.connect(path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='card_transactions'"
    )
    assert cursor.fetchone() is not None
    conn.close()

def test_init_db_is_idempotent(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    init_db(path)  # 2回呼んでもエラーにならない
