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

def test_init_db_creates_categories_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
    ).fetchone()
    conn.close()
    assert row is not None

def test_init_db_creates_category_rules_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='category_rules'"
    ).fetchone()
    conn.close()
    assert row is not None

def test_init_db_adds_category_id_to_bank_transactions(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bank_transactions)").fetchall()]
    conn.close()
    assert "category_id" in cols

def test_init_db_adds_category_id_to_card_transactions(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(card_transactions)").fetchall()]
    conn.close()
    assert "category_id" in cols

def test_init_db_seeds_card_deduction_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT * FROM categories WHERE name = 'カード引き落とし'"
    ).fetchone()
    conn.close()
    assert row is not None

def test_init_db_seeds_card_deduction_rule(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT * FROM category_rules WHERE keyword = 'ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ'"
    ).fetchone()
    conn.close()
    assert row is not None
