# カテゴリ分類・収支分析機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 銀行・カード取引にキーワードルールで自動分類＋手動補完のカテゴリを付与し、カテゴリ別支出円グラフ・推移棒グラフ・収支バランスシートを表示できるようにする。

**Architecture:** FastAPI + SQLite 構成に `categories` / `category_rules` テーブルを追加。インポート時にルールマッチングで `category_id` を付与。新ルーター `categories.py` と `analytics.py` を追加。フロントエンドは既存 ECharts を使って分析タブとカテゴリ管理タブを追加する。

**Tech Stack:** Python 3.12, FastAPI, SQLite (sqlite3), Pydantic v2, pytest + TestClient, ECharts 5 (CDN済み), バニラ JS

---

## ファイル構成

| 操作 | ファイル | 内容 |
|---|---|---|
| 修正 | `src/pinance/database.py` | categories/category_rules テーブル追加、PRAGMA、ALTER TABLE、シードデータ |
| 修正 | `src/pinance/models.py` | Category, CategoryRule, Analytics モデル追加。BankTransaction/CardTransaction に category フィールド追加 |
| 新規 | `src/pinance/classifier.py` | キーワードマッチングの分類ヘルパー |
| 新規 | `src/pinance/routers/categories.py` | カテゴリ・ルール CRUD |
| 新規 | `src/pinance/routers/analytics.py` | breakdown / trends / balance-sheet エンドポイント |
| 修正 | `src/pinance/routers/bank.py` | インポート時自動分類、PATCH カテゴリ変更、GET にカテゴリ名追加 |
| 修正 | `src/pinance/routers/card.py` | 同上 |
| 修正 | `src/pinance/main.py` | 新ルーター登録 |
| 修正 | `src/pinance/static/index.html` | 分析タブ・カテゴリ管理タブの HTML 追加 |
| 修正 | `src/pinance/static/app.js` | 分析・カテゴリ管理の JS 追加 |
| 修正 | `src/pinance/static/style.css` | 新タブ用スタイル追加 |
| 新規 | `tests/test_categories_router.py` | カテゴリ・ルール CRUD テスト |
| 新規 | `tests/test_analytics_router.py` | 分析エンドポイントテスト |
| 修正 | `tests/test_bank_router.py` | category_id/category_name フィールドの検証追加 |
| 修正 | `tests/test_card_router.py` | 同上 |

---

## Task 1: DBスキーマ拡張

**Files:**
- Modify: `src/pinance/database.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: 既存の `test_database.py` を確認する**

```bash
cat tests/test_database.py
```

- [ ] **Step 2: `test_database.py` に新テーブルのテストを追記する**

```python
# tests/test_database.py の末尾に追記

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

def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # 2回呼んでもエラーにならないこと
```

- [ ] **Step 3: テストを実行して失敗することを確認する**

```bash
pytest tests/test_database.py -v -k "categories or category_id or seeds"
```

Expected: FAIL

- [ ] **Step 4: `database.py` を更新する**

```python
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
    conn.commit()
    conn.close()
```

- [ ] **Step 5: テストを実行してパスすることを確認する**

```bash
pytest tests/test_database.py -v
```

Expected: PASS（既存テストを含む全件）

- [ ] **Step 6: コミットする**

```bash
git add src/pinance/database.py tests/test_database.py
git commit -m "feat: DBにcategories/category_rulesテーブルを追加、外部キー有効化"
```

---

## Task 2: Pydantic モデルの追加・更新

**Files:**
- Modify: `src/pinance/models.py`

- [ ] **Step 1: `models.py` を更新する**

```python
from pydantic import BaseModel

# --- 既存モデル（category フィールド追加） ---

class BankTransaction(BaseModel):
    id: int
    date: str
    withdrawal: int
    deposit: int
    description: str
    balance: int
    category_id: int | None = None
    category_name: str | None = None

class BankTransactionsResponse(BaseModel):
    period_label: str
    transactions: list[BankTransaction]

class CardTransaction(BaseModel):
    id: int
    date: str
    merchant: str
    amount: int
    category_id: int | None = None
    category_name: str | None = None

class CardTransactionsResponse(BaseModel):
    period_label: str
    transactions: list[CardTransaction]

class ImportResponse(BaseModel):
    imported: int
    skipped: int

class BankSummary(BaseModel):
    period_label: str
    total_deposit: int
    total_withdrawal: int
    net: int

class ChartData(BaseModel):
    labels: list[str]
    deposits: list[int]
    withdrawals: list[int]
    nets: list[int]
    balances: list[int]

class DeleteResponse(BaseModel):
    deleted: int

# --- カテゴリ管理モデル ---

class Category(BaseModel):
    id: int
    name: str
    type: str

class CategoryCreate(BaseModel):
    name: str
    type: str

class CategoryRule(BaseModel):
    id: int
    keyword: str
    category_id: int
    category_name: str | None = None
    target: str

class CategoryRuleCreate(BaseModel):
    keyword: str
    category_id: int
    target: str = "both"

class CategoryPatch(BaseModel):
    category_id: int | None

# --- 分析モデル ---

class AnalyticsBreakdownItem(BaseModel):
    category: str
    amount: int

class AnalyticsBreakdown(BaseModel):
    period_label: str
    items: list[AnalyticsBreakdownItem]
    unclassified_count: int

class AnalyticsTrendsItem(BaseModel):
    month: str
    label: str
    amounts: dict[str, int]  # category_name -> amount

class AnalyticsTrends(BaseModel):
    months: list[str]
    labels: list[str]
    category_names: list[str]
    data: dict[str, list[int]]  # category_name -> [amount per month]
    unclassified_count: int

class BalanceSheetItem(BaseModel):
    category: str
    amount: int

class BalanceSheet(BaseModel):
    period_label: str
    income: list[BalanceSheetItem]
    expense: list[BalanceSheetItem]
    total_income: int
    total_expense: int
    net: int
    unclassified_count: int
```

- [ ] **Step 2: インポートエラーがないことを確認する**

```bash
python -c "from pinance.models import BankTransaction, Category, AnalyticsBreakdown, BalanceSheet; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: コミットする**

```bash
git add src/pinance/models.py
git commit -m "feat: カテゴリ・分析用Pydanticモデルを追加"
```

---

## Task 3: 分類ヘルパー

**Files:**
- Create: `src/pinance/classifier.py`
- Test: なし（Task 4 のテスト内で検証）

- [ ] **Step 1: `classifier.py` を作成する**

```python
# src/pinance/classifier.py

def fetch_rules(conn) -> list[dict]:
    """DB から category_rules を全件取得して辞書のリストで返す"""
    rows = conn.execute(
        "SELECT id, keyword, category_id, target FROM category_rules ORDER BY id ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def classify_text(text: str, rules: list[dict], target: str) -> int | None:
    """text に最初にマッチしたルール（id昇順）の category_id を返す。マッチなしは None"""
    for rule in rules:
        if rule["target"] in (target, "both") and rule["keyword"] in text:
            return rule["category_id"]
    return None
```

- [ ] **Step 2: インポートできることを確認する**

```bash
python -c "from pinance.classifier import fetch_rules, classify_text; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: コミットする**

```bash
git add src/pinance/classifier.py
git commit -m "feat: キーワードマッチング分類ヘルパーを追加"
```

---

## Task 4: カテゴリ CRUD ルーター

**Files:**
- Create: `src/pinance/routers/categories.py`
- Create: `tests/test_categories_router.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# tests/test_categories_router.py
import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

# --- カテゴリ CRUD ---

def test_list_categories_includes_seed(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    names = [c["name"] for c in res.json()]
    assert "カード引き落とし" in names

def test_create_category(client):
    res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "食費"
    assert data["type"] == "expense"
    assert "id" in data

def test_create_category_duplicate_returns_409(client):
    client.post("/api/categories", json={"name": "食費", "type": "expense"})
    res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    assert res.status_code == 409

def test_create_category_invalid_type_returns_422(client):
    res = client.post("/api/categories", json={"name": "テスト", "type": "invalid"})
    assert res.status_code in (422, 400)

def test_update_category(client):
    create_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = create_res.json()["id"]
    res = client.put(f"/api/categories/{cat_id}", json={"name": "食費・日用品", "type": "expense"})
    assert res.status_code == 200
    assert res.json()["name"] == "食費・日用品"

def test_delete_category(client):
    create_res = client.post("/api/categories", json={"name": "テスト", "type": "expense"})
    cat_id = create_res.json()["id"]
    res = client.delete(f"/api/categories/{cat_id}")
    assert res.status_code == 200
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert "テスト" not in names

def test_delete_category_nullifies_transaction_category(client):
    """カテゴリ削除時に取引の category_id が NULL になること"""
    # カテゴリを作成してルールを追加
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    # 銀行取引をインポートして手動分類
    SAMPLE_CSV = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,スーパー,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    tx_res = client.get("/api/bank/transactions?period=all")
    tx_id = tx_res.json()["transactions"][0]["id"]
    client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": cat_id})
    # カテゴリ削除
    client.delete(f"/api/categories/{cat_id}")
    # 取引の category_id が NULL になっていること
    tx_res2 = client.get("/api/bank/transactions?period=all")
    assert tx_res2.json()["transactions"][0]["category_id"] is None

# --- ルール CRUD ---

def test_list_rules_includes_seed(client):
    res = client.get("/api/categories/rules")
    assert res.status_code == 200
    keywords = [r["keyword"] for r in res.json()]
    assert "ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ" in keywords

def test_create_rule(client):
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    res = client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    assert res.status_code == 201
    data = res.json()
    assert data["keyword"] == "イオン"
    assert data["category_id"] == cat_id

def test_create_rule_duplicate_keyword_target_returns_409(client):
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    res = client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    assert res.status_code == 409

def test_delete_rule(client):
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    rule_res = client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    rule_id = rule_res.json()["id"]
    res = client.delete(f"/api/categories/rules/{rule_id}")
    assert res.status_code == 200
    keywords = [r["keyword"] for r in client.get("/api/categories/rules").json()]
    assert "イオン" not in keywords
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```bash
pytest tests/test_categories_router.py -v
```

Expected: FAIL（ルーターが存在しないため）

- [ ] **Step 3: `categories.py` ルーターを作成する**

```python
# src/pinance/routers/categories.py
import sqlite3
from fastapi import APIRouter, HTTPException
from pinance.models import Category, CategoryCreate, CategoryRule, CategoryRuleCreate

def make_categories_router(db_path: str):
    router = APIRouter(prefix="/api/categories", tags=["categories"])

    @router.get("", response_model=list[Category])
    def list_categories():
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM categories ORDER BY id ASC").fetchall()
        finally:
            conn.close()
        return [Category(id=r["id"], name=r["name"], type=r["type"]) for r in rows]

    @router.post("", response_model=Category, status_code=201)
    def create_category(payload: CategoryCreate):
        if payload.type not in ("income", "expense", "exclude"):
            raise HTTPException(status_code=400, detail="type は income/expense/exclude のいずれかです")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            cursor = conn.execute(
                "INSERT INTO categories (name, type) VALUES (?, ?)",
                (payload.name, payload.type),
            )
            conn.commit()
            cat_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="カテゴリ名が重複しています")
        finally:
            conn.close()
        return Category(id=cat_id, name=payload.name, type=payload.type)

    @router.put("/{cat_id}", response_model=Category)
    def update_category(cat_id: int, payload: CategoryCreate):
        if payload.type not in ("income", "expense", "exclude"):
            raise HTTPException(status_code=400, detail="type は income/expense/exclude のいずれかです")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        not_found = False
        try:
            cursor = conn.execute(
                "UPDATE categories SET name = ?, type = ? WHERE id = ?",
                (payload.name, payload.type, cat_id),
            )
            if cursor.rowcount == 0:
                not_found = True
            else:
                conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="カテゴリ名が重複しています")
        finally:
            conn.close()
        if not_found:
            raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
        return Category(id=cat_id, name=payload.name, type=payload.type)

    @router.delete("/{cat_id}")
    def delete_category(cat_id: int):
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        not_found = False
        try:
            # 参照取引の category_id を NULL にしてから削除
            conn.execute("UPDATE bank_transactions SET category_id = NULL WHERE category_id = ?", [cat_id])
            conn.execute("UPDATE card_transactions SET category_id = NULL WHERE category_id = ?", [cat_id])
            cursor = conn.execute("DELETE FROM categories WHERE id = ?", [cat_id])
            if cursor.rowcount == 0:
                not_found = True
            else:
                conn.commit()
        finally:
            conn.close()
        if not_found:
            raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
        return {"deleted": 1}

    @router.get("/rules", response_model=list[CategoryRule])
    def list_rules():
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT cr.*, c.name AS category_name
                   FROM category_rules cr
                   JOIN categories c ON cr.category_id = c.id
                   ORDER BY cr.id ASC"""
            ).fetchall()
        finally:
            conn.close()
        return [
            CategoryRule(
                id=r["id"], keyword=r["keyword"],
                category_id=r["category_id"], category_name=r["category_name"],
                target=r["target"],
            )
            for r in rows
        ]

    @router.post("/rules", response_model=CategoryRule, status_code=201)
    def create_rule(payload: CategoryRuleCreate):
        if payload.target not in ("bank", "card", "both"):
            raise HTTPException(status_code=400, detail="target は bank/card/both のいずれかです")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        rule_id = None
        category_name = None
        try:
            cat = conn.execute(
                "SELECT name FROM categories WHERE id = ?", [payload.category_id]
            ).fetchone()
            cursor = conn.execute(
                "INSERT INTO category_rules (keyword, category_id, target) VALUES (?, ?, ?)",
                (payload.keyword, payload.category_id, payload.target),
            )
            conn.commit()
            rule_id = cursor.lastrowid
            category_name = cat["name"] if cat else None
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="同じキーワードと対象の組み合わせが既に存在します")
        finally:
            conn.close()
        return CategoryRule(
            id=rule_id, keyword=payload.keyword,
            category_id=payload.category_id,
            category_name=category_name,
            target=payload.target,
        )

    @router.delete("/rules/{rule_id}")
    def delete_rule(rule_id: int):
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            cursor = conn.execute("DELETE FROM category_rules WHERE id = ?", [rule_id])
            conn.commit()
        finally:
            conn.close()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="ルールが見つかりません")
        return {"deleted": 1}

    return router
```

- [ ] **Step 4: `main.py` にルーターを追加する**

```python
# src/pinance/main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pinance.database import init_db, DEFAULT_DB_PATH
from pinance.routers.bank import make_bank_router
from pinance.routers.card import make_card_router
from pinance.routers.categories import make_categories_router

def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    init_db(db_path)
    app = FastAPI(title="Pinance")
    app.include_router(make_bank_router(db_path))
    app.include_router(make_card_router(db_path))
    app.include_router(make_categories_router(db_path))

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(static_dir, "index.html"))

    return app

app = create_app()
```

- [ ] **Step 5: テストを実行してパスすることを確認する**

```bash
pytest tests/test_categories_router.py -v
```

Expected: PASS

- [ ] **Step 6: コミットする**

```bash
git add src/pinance/routers/categories.py src/pinance/main.py tests/test_categories_router.py
git commit -m "feat: カテゴリ・ルールCRUDエンドポイントを追加"
```

---

## Task 5: インポート時の自動分類 + PATCH エンドポイント

**Files:**
- Modify: `src/pinance/routers/bank.py`
- Modify: `src/pinance/routers/card.py`
- Modify: `tests/test_bank_router.py`
- Modify: `tests/test_card_router.py`

- [ ] **Step 1: `test_bank_router.py` に自動分類のテストを追記する**

```python
# tests/test_bank_router.py の末尾に追記

SAMPLE_BANK_FOR_CLASSIFY = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,イオンモール,100000\n"

def test_import_auto_classifies_by_rule(client):
    """インポート時にルールでカテゴリが付与されること"""
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "bank"})
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE_BANK_FOR_CLASSIFY.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/transactions?period=all")
    tx = res.json()["transactions"][0]
    assert tx["category_id"] == cat_id
    assert tx["category_name"] == "食費"

def test_import_unmatched_transaction_has_no_category(client):
    """マッチするルールがない取引は category_id が None であること"""
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE_BANK_FOR_CLASSIFY.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/transactions?period=all")
    assert res.json()["transactions"][0]["category_id"] is None

def test_patch_bank_transaction_category(client):
    """PATCH で手動カテゴリ変更できること"""
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    SAMPLE = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,スーパー,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE.encode("utf-8-sig"), "text/csv")})
    tx_id = client.get("/api/bank/transactions?period=all").json()["transactions"][0]["id"]
    res = client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": cat_id})
    assert res.status_code == 200
    tx = client.get("/api/bank/transactions?period=all").json()["transactions"][0]
    assert tx["category_id"] == cat_id
    assert tx["category_name"] == "食費"

def test_patch_bank_transaction_category_clear(client):
    """category_id: null で分類をクリアできること"""
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    SAMPLE = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,スーパー,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE.encode("utf-8-sig"), "text/csv")})
    tx_id = client.get("/api/bank/transactions?period=all").json()["transactions"][0]["id"]
    client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": cat_id})
    res = client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": None})
    assert res.status_code == 200
    assert client.get("/api/bank/transactions?period=all").json()["transactions"][0]["category_id"] is None

def test_patch_bank_transaction_category_not_found(client):
    res = client.patch("/api/bank/transactions/9999/category", json={"category_id": None})
    assert res.status_code == 404

def test_bank_import_card_deduction_auto_excluded(client):
    """カード引き落とし行がシードルールで自動的に exclude カテゴリに分類されること"""
    CARD_CSV = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,50000,,ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ (ｶ,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", CARD_CSV.encode("utf-8-sig"), "text/csv")})
    tx = client.get("/api/bank/transactions?period=all").json()["transactions"][0]
    assert tx["category_name"] == "カード引き落とし"
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```bash
pytest tests/test_bank_router.py -v -k "classify or patch or excluded"
```

Expected: FAIL

- [ ] **Step 3: `bank.py` を更新する**

`bank.py` の `make_bank_router` 内で以下を変更：

**インポート関数に分類を追加：**
```python
# make_bank_router の import エンドポイントを更新
from pinance.classifier import fetch_rules, classify_text

# import_bank_csv 関数内、conn = sqlite3.connect(db_path) の直後：
# ※ fetch_rules は sqlite3.Row を前提とするため row_factory を設定する
conn.row_factory = sqlite3.Row
imported = 0
skipped = 0
try:
    rules = fetch_rules(conn)
    for row in rows:
        cat_id = classify_text(row["description"], rules, "bank")
        cursor = conn.execute(
            """INSERT OR IGNORE INTO bank_transactions
               (date, withdrawal, deposit, description, balance, category_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (row["date"], row["withdrawal"], row["deposit"],
             row["description"], row["balance"], cat_id),
        )
        if cursor.rowcount == 1:
            imported += 1
        else:
            skipped += 1
    conn.commit()
```

**GET /transactions に category JOIN を追加：**
```python
@router.get("/transactions", response_model=BankTransactionsResponse)
def get_transactions(period: str = "all", date: str | None = None):
    where, params = _build_where_clause(period, date)
    query = f"""
        SELECT bt.*, c.name AS category_name
        FROM bank_transactions bt
        LEFT JOIN categories c ON bt.category_id = c.id
        {where}
        ORDER BY bt.date DESC, bt.id DESC
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    transactions = [
        BankTransaction(
            id=r["id"], date=r["date"], withdrawal=r["withdrawal"],
            deposit=r["deposit"], description=r["description"], balance=r["balance"],
            category_id=r["category_id"],
            category_name=r["category_name"],
        )
        for r in rows
    ]
    return BankTransactionsResponse(
        period_label=_make_period_label(period, date),
        transactions=transactions,
    )
```

**PATCH エンドポイントを追加（router の return の直前）：**
```python
from pinance.models import CategoryPatch

@router.patch("/transactions/{transaction_id}/category")
def set_transaction_category(transaction_id: int, payload: CategoryPatch):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "UPDATE bank_transactions SET category_id = ? WHERE id = ?",
            [payload.category_id, transaction_id],
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="取引が見つかりません")
        row = conn.execute(
            """SELECT bt.*, c.name AS category_name
               FROM bank_transactions bt
               LEFT JOIN categories c ON bt.category_id = c.id
               WHERE bt.id = ?""",
            [transaction_id],
        ).fetchone()
    finally:
        conn.close()
    return BankTransaction(
        id=row["id"], date=row["date"], withdrawal=row["withdrawal"],
        deposit=row["deposit"], description=row["description"], balance=row["balance"],
        category_id=row["category_id"], category_name=row["category_name"],
    )
```

- [ ] **Step 4: `card.py` を同様に更新する**

```python
# card.py の import 関数に分類を追加
from pinance.classifier import fetch_rules, classify_text

# import_card_csv の conn 取得後：
rules = fetch_rules(conn)
for row in rows:
    cat_id = classify_text(row["merchant"], rules, "card")
    cursor = conn.execute(
        """INSERT OR IGNORE INTO card_transactions
           (date, merchant, amount, row_index, category_id)
           VALUES (?, ?, ?, ?, ?)""",
        (row["date"], row["merchant"], row["amount"], row["row_index"], cat_id),
    )

# GET /transactions のクエリを更新
query = f"""
    SELECT ct.*, c.name AS category_name
    FROM card_transactions ct
    LEFT JOIN categories c ON ct.category_id = c.id
    {where}
    ORDER BY ct.date DESC, ct.id DESC
"""
# CardTransaction の生成時に category_id, category_name を追加

# PATCH エンドポイントを追加（bank.py と同じパターン）
@router.patch("/transactions/{transaction_id}/category")
def set_transaction_category(transaction_id: int, payload: CategoryPatch):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "UPDATE card_transactions SET category_id = ? WHERE id = ?",
            [payload.category_id, transaction_id],
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="取引が見つかりません")
        row = conn.execute(
            """SELECT ct.*, c.name AS category_name
               FROM card_transactions ct
               LEFT JOIN categories c ON ct.category_id = c.id
               WHERE ct.id = ?""",
            [transaction_id],
        ).fetchone()
    finally:
        conn.close()
    return CardTransaction(
        id=row["id"], date=row["date"], merchant=row["merchant"],
        amount=row["amount"], category_id=row["category_id"],
        category_name=row["category_name"],
    )
```

- [ ] **Step 5: テストを実行してパスすることを確認する**

```bash
pytest tests/test_bank_router.py tests/test_card_router.py -v
```

Expected: PASS（既存テストを含む全件）

- [ ] **Step 6: コミットする**

```bash
git add src/pinance/routers/bank.py src/pinance/routers/card.py tests/test_bank_router.py tests/test_card_router.py
git commit -m "feat: インポート時の自動分類とPATCHエンドポイントを追加"
```

---

## Task 6: 分析エンドポイント

**Files:**
- Create: `src/pinance/routers/analytics.py`
- Create: `tests/test_analytics_router.py`
- Modify: `src/pinance/main.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# tests/test_analytics_router.py
import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app

BANK_CSV = (
    "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n"
    "2024/8/27,3000,,イオンモール,100000\n"
    "2024/8/20,2000,,松屋,98000\n"
    "2024/8/15,,300000,給料,96000\n"
    "2024/7/25,5000,,スーパー,100000\n"
)

CARD_CSV = (
    "\ufeff田中　太郎　様,4990-06**-****-****,ダミーカード,,,,,,,,\n"
    "2024/7/10,コンビニ,500,1,1,500,,,,,\n"
    "2024/7/20,イオン,1500,2,1,1500,,,,,\n"
)

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

@pytest.fixture
def client_with_data(client):
    # カテゴリとルールを設定
    food_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    food_id = food_res.json()["id"]
    income_res = client.post("/api/categories", json={"name": "給与", "type": "income"})
    income_id = income_res.json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": food_id, "target": "both"})
    client.post("/api/categories/rules", json={"keyword": "松屋", "category_id": food_id, "target": "bank"})
    client.post("/api/categories/rules", json={"keyword": "給料", "category_id": income_id, "target": "bank"})
    # データをインポート
    client.post("/api/bank/import", files={"file": ("b.csv", BANK_CSV.encode("utf-8-sig"), "text/csv")})
    client.post("/api/card/import", files={"file": ("c.csv", CARD_CSV.encode("utf-8-sig"), "text/csv")})
    return client

def test_breakdown_returns_expense_by_category(client_with_data):
    res = client_with_data.get("/api/analytics/breakdown?period=month&date=2024-08")
    assert res.status_code == 200
    data = res.json()
    assert data["period_label"] == "2024年8月"
    amounts = {item["category"]: item["amount"] for item in data["items"]}
    assert amounts.get("食費", 0) == 5000  # 3000(イオン) + 2000(松屋)

def test_breakdown_unclassified_count(client_with_data):
    res = client_with_data.get("/api/analytics/breakdown?period=month&date=2024-07")
    assert res.status_code == 200
    data = res.json()
    # スーパー5000 は未分類
    assert data["unclassified_count"] >= 1

def test_breakdown_empty_period(client_with_data):
    res = client_with_data.get("/api/analytics/breakdown?period=month&date=2000-01")
    assert res.status_code == 200
    assert res.json()["items"] == []

def test_balance_sheet_income_and_expense(client_with_data):
    res = client_with_data.get("/api/analytics/balance-sheet?period=month&date=2024-08")
    assert res.status_code == 200
    data = res.json()
    income_names = [i["category"] for i in data["income"]]
    assert "給与" in income_names
    total_income = sum(i["amount"] for i in data["income"])
    assert total_income == 300000
    assert data["total_income"] == 300000
    assert data["net"] == data["total_income"] - data["total_expense"]

def test_balance_sheet_excludes_card_deduction(client_with_data):
    """カード引き落としは集計から除外されること"""
    DEDUCTION_CSV = (
        "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n"
        "2024/8/10,50000,,ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ (ｶ,50000\n"
    )
    client_with_data.post("/api/bank/import",
        files={"file": ("d.csv", DEDUCTION_CSV.encode("utf-8-sig"), "text/csv")})
    res = client_with_data.get("/api/analytics/balance-sheet?period=month&date=2024-08")
    expense_names = [e["category"] for e in res.json()["expense"]]
    assert "カード引き落とし" not in expense_names

def test_trends_returns_last_n_months(client_with_data):
    res = client_with_data.get("/api/analytics/trends?months=3")
    assert res.status_code == 200
    data = res.json()
    assert len(data["months"]) == 3
    assert len(data["labels"]) == 3

def test_trends_empty_db(client):
    res = client.get("/api/analytics/trends?months=6")
    assert res.status_code == 200
    data = res.json()
    assert data["months"] == []
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```bash
pytest tests/test_analytics_router.py -v
```

Expected: FAIL

- [ ] **Step 3: `analytics.py` を作成する**

```python
# src/pinance/routers/analytics.py
import sqlite3
from datetime import datetime, timedelta
from fastapi import APIRouter
from pinance.models import (
    AnalyticsBreakdown, AnalyticsBreakdownItem,
    AnalyticsTrends,
    BalanceSheet, BalanceSheetItem,
)
from pinance.routers.bank import _make_period_label


def _date_filter(period: str, date_str: str | None, alias: str) -> tuple[str, list]:
    """テーブルエイリアス付きの日付フィルタ句を返す"""
    col = f"{alias}.date"
    if period == "all" or not date_str:
        return "", []
    if period == "day":
        return f"{col} = ?", [date_str]
    if period == "week":
        d = datetime.strptime(date_str, "%Y-%m-%d")
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        return f"{col} BETWEEN ? AND ?", [
            monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d"),
        ]
    if period in ("month", "year"):
        return f"{col} LIKE ?", [f"{date_str}-%"]
    return "", []


def make_analytics_router(db_path: str):
    router = APIRouter(prefix="/api/analytics", tags=["analytics"])

    @router.get("/breakdown", response_model=AnalyticsBreakdown)
    def get_breakdown(period: str = "month", date: str | None = None):
        bk_f, bk_p = _date_filter(period, date, "bt")
        cd_f, cd_p = _date_filter(period, date, "ct")
        bk_where = f"WHERE c.type = 'expense'" + (f" AND {bk_f}" if bk_f else "")
        cd_where = f"WHERE c.type = 'expense'" + (f" AND {cd_f}" if cd_f else "")
        bk_null = f"WHERE bt.category_id IS NULL" + (f" AND {bk_f}" if bk_f else "")
        cd_null = f"WHERE ct.category_id IS NULL" + (f" AND {cd_f}" if cd_f else "")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            bank_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(bt.withdrawal), 0) AS amount
                    FROM bank_transactions bt
                    JOIN categories c ON bt.category_id = c.id
                    {bk_where} GROUP BY c.id""",
                bk_p,
            ).fetchall()
            card_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(ct.amount), 0) AS amount
                    FROM card_transactions ct
                    JOIN categories c ON ct.category_id = c.id
                    {cd_where} GROUP BY c.id""",
                cd_p,
            ).fetchall()
            bank_null_count = conn.execute(
                f"SELECT COUNT(*) FROM bank_transactions bt {bk_null}", bk_p
            ).fetchone()[0]
            card_null_count = conn.execute(
                f"SELECT COUNT(*) FROM card_transactions ct {cd_null}", cd_p
            ).fetchone()[0]
        finally:
            conn.close()

        totals: dict[str, int] = {}
        for r in list(bank_rows) + list(card_rows):
            totals[r["category"]] = totals.get(r["category"], 0) + r["amount"]

        items = sorted(
            [AnalyticsBreakdownItem(category=k, amount=v) for k, v in totals.items()],
            key=lambda x: -x.amount,
        )
        return AnalyticsBreakdown(
            period_label=_make_period_label(period, date),
            items=items,
            unclassified_count=bank_null_count + card_null_count,
        )

    @router.get("/trends", response_model=AnalyticsTrends)
    def get_trends(months: int = 6):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            latest_bk = conn.execute(
                "SELECT MAX(substr(date,1,7)) AS ym FROM bank_transactions"
            ).fetchone()["ym"]
            latest_cd = conn.execute(
                "SELECT MAX(substr(date,1,7)) AS ym FROM card_transactions"
            ).fetchone()["ym"]
        finally:
            conn.close()

        candidates = [ym for ym in [latest_bk, latest_cd] if ym]
        if not candidates:
            return AnalyticsTrends(months=[], labels=[], category_names=[], data={}, unclassified_count=0)

        latest_ym = max(candidates)
        year, month = map(int, latest_ym.split("-"))

        month_list: list[str] = []
        for i in range(months - 1, -1, -1):
            m = month - i
            y = year
            while m <= 0:
                m += 12
                y -= 1
            month_list.append(f"{y}-{m:02d}")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cat_rows = conn.execute(
                "SELECT id, name FROM categories WHERE type = 'expense' ORDER BY name ASC"
            ).fetchall()
            category_names = [r["name"] for r in cat_rows]
            category_ids = {r["name"]: r["id"] for r in cat_rows}

            data: dict[str, list[int]] = {name: [0] * months for name in category_names}
            unclassified_count = 0

            for i, ym in enumerate(month_list):
                bk_rows = conn.execute(
                    """SELECT c.name AS category, COALESCE(SUM(bt.withdrawal),0) AS amount
                       FROM bank_transactions bt
                       JOIN categories c ON bt.category_id = c.id
                       WHERE c.type = 'expense' AND bt.date LIKE ?
                       GROUP BY c.id""",
                    [f"{ym}-%"],
                ).fetchall()
                cd_rows = conn.execute(
                    """SELECT c.name AS category, COALESCE(SUM(ct.amount),0) AS amount
                       FROM card_transactions ct
                       JOIN categories c ON ct.category_id = c.id
                       WHERE c.type = 'expense' AND ct.date LIKE ?
                       GROUP BY c.id""",
                    [f"{ym}-%"],
                ).fetchall()
                for r in list(bk_rows) + list(cd_rows):
                    if r["category"] in data:
                        data[r["category"]][i] += r["amount"]

                unclassified_count += conn.execute(
                    "SELECT COUNT(*) FROM bank_transactions WHERE category_id IS NULL AND date LIKE ?",
                    [f"{ym}-%"],
                ).fetchone()[0]
                unclassified_count += conn.execute(
                    "SELECT COUNT(*) FROM card_transactions WHERE category_id IS NULL AND date LIKE ?",
                    [f"{ym}-%"],
                ).fetchone()[0]
        finally:
            conn.close()

        def label(ym: str) -> str:
            y, m = ym.split("-")
            return f"{y}年{int(m)}月"

        return AnalyticsTrends(
            months=month_list,
            labels=[label(ym) for ym in month_list],
            category_names=category_names,
            data=data,
            unclassified_count=unclassified_count,
        )

    @router.get("/balance-sheet", response_model=BalanceSheet)
    def get_balance_sheet(period: str = "month", date: str | None = None):
        bk_f, bk_p = _date_filter(period, date, "bt")
        cd_f, cd_p = _date_filter(period, date, "ct")
        bk_income_where = "WHERE c.type = 'income'" + (f" AND {bk_f}" if bk_f else "")
        bk_expense_where = "WHERE c.type = 'expense'" + (f" AND {bk_f}" if bk_f else "")
        cd_expense_where = "WHERE c.type = 'expense'" + (f" AND {cd_f}" if cd_f else "")
        bk_null = "WHERE bt.category_id IS NULL" + (f" AND {bk_f}" if bk_f else "")
        cd_null = "WHERE ct.category_id IS NULL" + (f" AND {cd_f}" if cd_f else "")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            income_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(bt.deposit),0) AS amount
                    FROM bank_transactions bt
                    JOIN categories c ON bt.category_id = c.id
                    {bk_income_where} GROUP BY c.id""",
                bk_p,
            ).fetchall()
            bk_expense_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(bt.withdrawal),0) AS amount
                    FROM bank_transactions bt
                    JOIN categories c ON bt.category_id = c.id
                    {bk_expense_where} GROUP BY c.id""",
                bk_p,
            ).fetchall()
            cd_expense_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(ct.amount),0) AS amount
                    FROM card_transactions ct
                    JOIN categories c ON ct.category_id = c.id
                    {cd_expense_where} GROUP BY c.id""",
                cd_p,
            ).fetchall()
            bank_null_count = conn.execute(
                f"SELECT COUNT(*) FROM bank_transactions bt {bk_null}", bk_p
            ).fetchone()[0]
            card_null_count = conn.execute(
                f"SELECT COUNT(*) FROM card_transactions ct {cd_null}", cd_p
            ).fetchone()[0]
        finally:
            conn.close()

        expense_totals: dict[str, int] = {}
        for r in list(bk_expense_rows) + list(cd_expense_rows):
            expense_totals[r["category"]] = expense_totals.get(r["category"], 0) + r["amount"]

        income = sorted(
            [BalanceSheetItem(category=r["category"], amount=r["amount"]) for r in income_rows],
            key=lambda x: -x.amount,
        )
        expense = sorted(
            [BalanceSheetItem(category=k, amount=v) for k, v in expense_totals.items()],
            key=lambda x: -x.amount,
        )
        total_income = sum(i.amount for i in income)
        total_expense = sum(e.amount for e in expense)
        return BalanceSheet(
            period_label=_make_period_label(period, date),
            income=income,
            expense=expense,
            total_income=total_income,
            total_expense=total_expense,
            net=total_income - total_expense,
            unclassified_count=bank_null_count + card_null_count,
        )

    return router
```

- [ ] **Step 4: `main.py` に analytics ルーターを登録する**

```python
from pinance.routers.analytics import make_analytics_router

# create_app 内に追加：
app.include_router(make_analytics_router(db_path))
```

- [ ] **Step 5: テストを実行してパスすることを確認する**

```bash
pytest tests/test_analytics_router.py -v
```

Expected: PASS

- [ ] **Step 6: 全テストを実行して既存テストが壊れていないことを確認する**

```bash
pytest -v
```

Expected: PASS（全件）

- [ ] **Step 7: コミットする**

```bash
git add src/pinance/routers/analytics.py src/pinance/main.py tests/test_analytics_router.py
git commit -m "feat: 分析エンドポイント（breakdown/trends/balance-sheet）を追加"
```

---

## Task 7: フロントエンド - カテゴリ管理タブ

**Files:**
- Modify: `src/pinance/static/index.html`
- Modify: `src/pinance/static/style.css`
- Modify: `src/pinance/static/app.js`

- [ ] **Step 1: `index.html` にタブナビゲーションとカテゴリ管理パネルを追加する**

`<body>` の `<header>` の直後にタブナビゲーションを追加：

```html
<!-- header の直後 -->
<nav class="tab-nav">
  <button class="tab-btn active" data-tab="transactions">取引一覧</button>
  <button class="tab-btn" data-tab="analytics">分析</button>
  <button class="tab-btn" data-tab="categories">カテゴリ管理</button>
</nav>
```

既存コンテンツ（period-nav, chart-section, summary-cards, table-container）を `<div id="tab-transactions" class="tab-panel active">` で囲む。

分析パネルを追加：

```html
<div id="tab-analytics" class="tab-panel hidden">
  <div class="analytics-header">
    <select id="analytics-month-select"></select>
  </div>
  <div class="analytics-grid">
    <div class="analytics-card">
      <h3>カテゴリ別支出（円グラフ）</h3>
      <div id="breakdown-chart" style="height:300px;"></div>
    </div>
    <div class="analytics-card">
      <h3>カテゴリ別推移（直近6ヶ月）</h3>
      <div id="trends-chart" style="height:300px;"></div>
    </div>
  </div>
  <div class="analytics-card">
    <h3>収支バランスシート</h3>
    <div id="balance-sheet-container"></div>
  </div>
  <div id="unclassified-warning" class="warning hidden"></div>
</div>
```

カテゴリ管理パネルを追加：

```html
<div id="tab-categories" class="tab-panel hidden">
  <div class="category-grid">
    <div>
      <h3>カテゴリ</h3>
      <table id="categories-table">
        <thead><tr><th>名前</th><th>種別</th><th></th></tr></thead>
        <tbody id="categories-tbody"></tbody>
      </table>
      <form id="category-form" class="inline-form">
        <input type="text" id="cat-name-input" placeholder="カテゴリ名" required>
        <select id="cat-type-select">
          <option value="expense">支出</option>
          <option value="income">収入</option>
          <option value="exclude">除外</option>
        </select>
        <button type="submit" class="btn">追加</button>
      </form>
    </div>
    <div>
      <h3>キーワードルール</h3>
      <table id="rules-table">
        <thead><tr><th>キーワード</th><th>カテゴリ</th><th>対象</th><th></th></tr></thead>
        <tbody id="rules-tbody"></tbody>
      </table>
      <form id="rule-form" class="inline-form">
        <input type="text" id="rule-keyword-input" placeholder="キーワード" required>
        <select id="rule-category-select"></select>
        <select id="rule-target-select">
          <option value="both">両方</option>
          <option value="bank">銀行のみ</option>
          <option value="card">カードのみ</option>
        </select>
        <button type="submit" class="btn">追加</button>
      </form>
    </div>
  </div>
</div>
```

- [ ] **Step 2: `style.css` にタブ・分析・カテゴリ管理のスタイルを追加する**

```css
/* タブナビゲーション */
.tab-nav {
  display: flex;
  gap: 4px;
  padding: 8px 16px 0;
  border-bottom: 2px solid #e5e7eb;
  background: #fff;
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.9rem;
  color: #6b7280;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
}

.tab-btn.active {
  color: #1d4ed8;
  border-bottom-color: #1d4ed8;
  font-weight: 600;
}

.tab-panel { display: none; }
.tab-panel.active { display: block; }
.hidden { display: none !important; }

/* 分析タブ */
.analytics-header { padding: 16px; }
.analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px; }
.analytics-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }
.analytics-card h3 { margin: 0 0 12px; font-size: 0.95rem; color: #374151; }

/* バランスシート表 */
.balance-sheet { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.balance-sheet th, .balance-sheet td { padding: 6px 12px; border-bottom: 1px solid #e5e7eb; }
.balance-sheet .amount { text-align: right; }
.balance-sheet .section-header { background: #f9fafb; font-weight: 600; }
.balance-sheet .total-row { font-weight: 700; background: #f3f4f6; }
.balance-sheet .net-row { font-weight: 700; font-size: 1rem; background: #eff6ff; }

/* 警告 */
.warning { color: #b45309; background: #fef3c7; border: 1px solid #fde68a; border-radius: 6px; padding: 8px 16px; margin: 8px 16px; font-size: 0.85rem; }

/* カテゴリ管理タブ */
.category-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 24px; }
.inline-form { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.inline-form input, .inline-form select { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 4px; }
#categories-table, #rules-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
#categories-table td, #categories-table th,
#rules-table td, #rules-table th { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; }

/* カテゴリバッジ */
.cat-badge { display: inline-block; padding: 1px 8px; border-radius: 12px; font-size: 0.75rem; }
.cat-badge.expense { background: #fee2e2; color: #dc2626; }
.cat-badge.income { background: #dcfce7; color: #16a34a; }
.cat-badge.exclude { background: #f3f4f6; color: #6b7280; }

/* 取引一覧のカテゴリ表示 */
.tx-category { font-size: 0.75rem; color: #6b7280; cursor: pointer; border: none; background: none; padding: 0; }
.tx-category.unclassified { color: #d97706; }
```

- [ ] **Step 3: `app.js` にタブ切り替えとカテゴリ管理 JS を追加する**

`app.js` の末尾に以下を追加：

```javascript
// ===== タブ切り替え =====
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => { p.classList.remove('active'); p.classList.add('hidden'); });
    btn.classList.add('active');
    const panel = document.getElementById('tab-' + btn.dataset.tab);
    panel.classList.remove('hidden');
    panel.classList.add('active');
    if (btn.dataset.tab === 'analytics') loadAnalytics();
    if (btn.dataset.tab === 'categories') loadCategories();
  });
});

// ===== カテゴリ管理 =====
let allCategories = [];

async function loadCategories() {
  const [catRes, ruleRes] = await Promise.all([
    fetch('/api/categories'),
    fetch('/api/categories/rules'),
  ]);
  allCategories = catRes.ok ? await catRes.json() : [];
  const rules = ruleRes.ok ? await ruleRes.json() : [];

  // カテゴリ一覧テーブル
  const tbody = document.getElementById('categories-tbody');
  tbody.innerHTML = '';
  allCategories.forEach(c => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${c.name}</td>
      <td><span class="cat-badge ${c.type}">${{income:'収入',expense:'支出',exclude:'除外'}[c.type]}</span></td>
      <td><button class="btn btn-icon" onclick="deleteCategory(${c.id})">✕</button></td>`;
    tbody.appendChild(tr);
  });

  // ルール一覧テーブル
  const rulesTbody = document.getElementById('rules-tbody');
  rulesTbody.innerHTML = '';
  rules.forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.keyword}</td>
      <td>${r.category_name || ''}</td>
      <td>${{both:'両方',bank:'銀行',card:'カード'}[r.target]}</td>
      <td><button class="btn btn-icon" onclick="deleteRule(${r.id})">✕</button></td>`;
    rulesTbody.appendChild(tr);
  });

  // ルールフォームのカテゴリセレクト
  const sel = document.getElementById('rule-category-select');
  sel.innerHTML = '';
  allCategories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    sel.appendChild(opt);
  });
}

document.getElementById('category-form').addEventListener('submit', async e => {
  e.preventDefault();
  const name = document.getElementById('cat-name-input').value.trim();
  const type = document.getElementById('cat-type-select').value;
  const res = await fetch('/api/categories', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, type}),
  });
  if (!res.ok) { showToast('カテゴリの追加に失敗しました', true); return; }
  document.getElementById('cat-name-input').value = '';
  loadCategories();
});

document.getElementById('rule-form').addEventListener('submit', async e => {
  e.preventDefault();
  const keyword = document.getElementById('rule-keyword-input').value.trim();
  const category_id = parseInt(document.getElementById('rule-category-select').value);
  const target = document.getElementById('rule-target-select').value;
  const res = await fetch('/api/categories/rules', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({keyword, category_id, target}),
  });
  if (!res.ok) { showToast('ルールの追加に失敗しました', true); return; }
  document.getElementById('rule-keyword-input').value = '';
  loadCategories();
});

async function deleteCategory(id) {
  if (!confirm('このカテゴリを削除しますか？\n（このカテゴリが付いた取引の分類は解除されます）')) return;
  await fetch(`/api/categories/${id}`, {method: 'DELETE'});
  loadCategories();
}

async function deleteRule(id) {
  await fetch(`/api/categories/rules/${id}`, {method: 'DELETE'});
  loadCategories();
}
```

- [ ] **Step 4: ブラウザで動作確認する**

```bash
uvicorn pinance.main:app --reload
```

http://localhost:8000 を開き、「カテゴリ管理」タブで：
- カテゴリを追加・削除できること
- キーワードルールを追加・削除できること

- [ ] **Step 5: コミットする**

```bash
git add src/pinance/static/index.html src/pinance/static/style.css src/pinance/static/app.js
git commit -m "feat: カテゴリ管理タブのフロントエンドを追加"
```

---

## Task 8: フロントエンド - 分析タブ + 取引一覧カテゴリ表示

**Files:**
- Modify: `src/pinance/static/app.js`
- Modify: `src/pinance/static/index.html`

- [ ] **Step 1: `app.js` に分析タブの JS を追加する**

```javascript
// ===== 分析タブ =====
let breakdownChartInstance = null;
let trendsChartInstance = null;

async function loadAnalytics() {
  // 月セレクトを bank/card の月リストから生成
  const [bankRes, cardRes] = await Promise.all([
    fetch('/api/bank/months'),
    fetch('/api/card/months'),
  ]);
  const bankMonths = bankRes.ok ? await bankRes.json() : [];
  const cardMonths = cardRes.ok ? await cardRes.json() : [];
  const allMonths = [...new Set([...bankMonths, ...cardMonths])].sort().reverse();

  const sel = document.getElementById('analytics-month-select');
  sel.innerHTML = '';
  allMonths.forEach(ym => {
    const opt = document.createElement('option');
    opt.value = ym;
    opt.textContent = formatYearMonth(ym);
    sel.appendChild(opt);
  });

  if (allMonths.length > 0) {
    await loadBreakdownAndBalanceSheet(allMonths[0]);
    await loadTrends();
  }
}

document.getElementById('analytics-month-select')?.addEventListener('change', async e => {
  await Promise.all([
    loadBreakdownAndBalanceSheet(e.target.value),
  ]);
});

async function loadBreakdownAndBalanceSheet(ym) {
  const params = `period=month&date=${ym}`;
  const [bkRes, bsRes] = await Promise.all([
    fetch(`/api/analytics/breakdown?${params}`),
    fetch(`/api/analytics/balance-sheet?${params}`),
  ]);

  if (bkRes.ok) {
    const bk = await bkRes.json();
    renderBreakdownChart(bk);
    const warning = document.getElementById('unclassified-warning');
    if (bk.unclassified_count > 0) {
      warning.textContent = `${bk.unclassified_count}件の取引が未分類です。カテゴリ管理タブでルールを設定するか、取引一覧から手動で分類してください。`;
      warning.classList.remove('hidden');
    } else {
      warning.classList.add('hidden');
    }
  }

  if (bsRes.ok) {
    const bs = await bsRes.json();
    renderBalanceSheet(bs);
  }
}

function renderBreakdownChart(data) {
  const container = document.getElementById('breakdown-chart');
  if (!container) return;
  if (breakdownChartInstance) breakdownChartInstance.dispose();
  breakdownChartInstance = echarts.init(container);

  if (data.items.length === 0) {
    breakdownChartInstance.setOption({title: {text: 'データなし', left: 'center', top: 'middle'}});
    return;
  }

  breakdownChartInstance.setOption({
    tooltip: { trigger: 'item', valueFormatter: v => '¥' + v.toLocaleString('ja-JP') },
    series: [{
      type: 'pie',
      radius: '70%',
      data: data.items.map(item => ({name: item.category, value: item.amount})),
      label: { formatter: '{b}: ¥{c}' },
    }],
  });
}

async function loadTrends() {
  const res = await fetch('/api/analytics/trends?months=6');
  if (!res.ok) return;
  const data = await res.json();
  renderTrendsChart(data);
}

function renderTrendsChart(data) {
  const container = document.getElementById('trends-chart');
  if (!container) return;
  if (trendsChartInstance) trendsChartInstance.dispose();
  trendsChartInstance = echarts.init(container);

  if (data.months.length === 0) {
    trendsChartInstance.setOption({title: {text: 'データなし', left: 'center', top: 'middle'}});
    return;
  }

  const series = data.category_names.map(name => ({
    name,
    type: 'bar',
    stack: 'total',
    data: data.data[name] || [],
  }));

  trendsChartInstance.setOption({
    tooltip: { trigger: 'axis', valueFormatter: v => '¥' + (v || 0).toLocaleString('ja-JP') },
    legend: { bottom: 0 },
    xAxis: { type: 'category', data: data.labels },
    yAxis: { type: 'value', axisLabel: { formatter: v => '¥' + v.toLocaleString('ja-JP') } },
    series,
  });
}

function renderBalanceSheet(data) {
  const container = document.getElementById('balance-sheet-container');
  if (!container) return;

  const fmt = v => v === 0 ? '—' : '¥' + v.toLocaleString('ja-JP');
  const netClass = data.net >= 0 ? 'color:#16a34a' : 'color:#dc2626';

  let rows = '';
  rows += `<tr class="section-header"><td colspan="2">収入</td></tr>`;
  data.income.forEach(i => {
    rows += `<tr><td>${i.category}</td><td class="amount">${fmt(i.amount)}</td></tr>`;
  });
  rows += `<tr class="total-row"><td>収入合計</td><td class="amount">${fmt(data.total_income)}</td></tr>`;
  rows += `<tr class="section-header"><td colspan="2">支出</td></tr>`;
  data.expense.forEach(e => {
    rows += `<tr><td>${e.category}</td><td class="amount">${fmt(e.amount)}</td></tr>`;
  });
  rows += `<tr class="total-row"><td>支出合計</td><td class="amount">${fmt(data.total_expense)}</td></tr>`;
  rows += `<tr class="net-row"><td>差引</td><td class="amount" style="${netClass}">${data.net >= 0 ? '+' : ''}${fmt(data.net)}</td></tr>`;

  container.innerHTML = `<table class="balance-sheet"><tbody>${rows}</tbody></table>`;
}
```

- [ ] **Step 2: 取引一覧にカテゴリ表示と手動変更 UI を追加する**

`loadTransactions()` 関数の `tr.innerHTML` を以下に変更：

```javascript
// loadTransactions の tr.innerHTML を更新（category 列を追加）
const catName = t.category_name || null;
const catDisplay = catName
  ? `<button class="tx-category" onclick="openCategoryPicker(event, 'bank', ${t.id}, this)">${catName}</button>`
  : `<button class="tx-category unclassified" onclick="openCategoryPicker(event, 'bank', ${t.id}, this)">未分類</button>`;

tr.innerHTML = `
  <td>${t.date}</td>
  <td class="text-right amount-out">${fmt(t.withdrawal)}</td>
  <td class="text-right amount-in">${fmt(t.deposit)}</td>
  <td>${t.description}${isCard ? ' <span class="expand-icon">▶</span>' : ''}</td>
  <td class="text-right">${t.balance.toLocaleString('ja-JP')}</td>
  <td>${catDisplay}</td>`;
```

テーブルのヘッダーに `<th>カテゴリ</th>` を追加（`index.html` の `<thead>` 修正）。

カテゴリピッカーの実装を `app.js` に追加：

```javascript
async function openCategoryPicker(event, source, txId, btn) {
  event.stopPropagation();
  // allCategories が未ロードの場合は取得する（カテゴリ管理タブを開く前でも動作させるため）
  if (allCategories.length === 0) await loadCategories();

  // 既存ピッカーを閉じる
  document.querySelectorAll('.cat-picker').forEach(el => el.remove());

  const picker = document.createElement('select');
  picker.className = 'cat-picker';
  picker.style.cssText = 'position:absolute;z-index:100;border:1px solid #d1d5db;border-radius:4px;padding:4px;';

  const clearOpt = document.createElement('option');
  clearOpt.value = '';
  clearOpt.textContent = '（未分類）';
  picker.appendChild(clearOpt);

  allCategories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    picker.appendChild(opt);
  });

  picker.addEventListener('change', async () => {
    const category_id = picker.value ? parseInt(picker.value) : null;
    const endpoint = source === 'bank'
      ? `/api/bank/transactions/${txId}/category`
      : `/api/card/transactions/${txId}/category`;
    const res = await fetch(endpoint, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({category_id}),
    });
    picker.remove();
    if (res.ok) {
      const data = await res.json();
      btn.textContent = data.category_name || '未分類';
      btn.className = 'tx-category' + (data.category_name ? '' : ' unclassified');
    } else {
      showToast('カテゴリの変更に失敗しました', true);
    }
  });

  btn.parentNode.style.position = 'relative';
  btn.parentNode.appendChild(picker);
  picker.focus();
  document.addEventListener('click', () => picker.remove(), {once: true});
}
```

- [ ] **Step 3: ブラウザで動作確認する**

```bash
uvicorn pinance.main:app --reload
```

確認事項：
- 「分析」タブで月を選択すると円グラフとバランスシートが表示される
- カード CSV・銀行 CSV をインポートすると積み上げ棒グラフに反映される
- 取引一覧で「未分類」ボタンをクリックするとカテゴリを選択できる
- カテゴリ選択後、取引行のカテゴリ表示が更新される

- [ ] **Step 4: コミットする**

```bash
git add src/pinance/static/index.html src/pinance/static/style.css src/pinance/static/app.js
git commit -m "feat: 分析タブと取引一覧のカテゴリ表示・手動変更UIを追加"
```

---

## 完了確認

- [ ] **全テストを実行して PASS することを確認する**

```bash
pytest -v
```

Expected: 全件 PASS

- [ ] **README.md の機能表を更新する**

`README.md` の機能テーブルに以下を追記：

```markdown
| カテゴリ管理 | カテゴリの作成・編集・削除 | income/expense/exclude の3種類。キーワードルールで取引を自動分類する。 |
| カテゴリ管理 | キーワードルールの管理 | キーワードに一致する取引を自動的にカテゴリ分類する。 |
| 閲覧 | カテゴリ別支出の円グラフ | 月ごとのカテゴリ別支出内訳を円グラフで表示する。 |
| 閲覧 | カテゴリ別推移グラフ | 直近6ヶ月のカテゴリ別支出推移を積み上げ棒グラフで表示する。 |
| 閲覧 | 収支バランスシート | 月・年ごとの収入・支出カテゴリ一覧と差引残高を表示する。 |
```

- [ ] **最終コミット**

```bash
git add README.md
git commit -m "docs: カテゴリ分類・収支分析機能をREADMEに追記"
```
