# Pinance Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 三井住友銀行・Vpass CSVをインポートしてブラウザで閲覧できる家計簿アプリを構築する

**Architecture:** FastAPI バックエンド（REST API）+ SQLite（データ保存）+ バニラHTML/CSS/JS フロントエンド。`src/pinance/` パッケージにバックエンドコードを置き、`src/pinance/static/` に静的ファイルを置く。

**Tech Stack:** Python 3.12, FastAPI, uvicorn, SQLite (stdlib sqlite3), pytest, httpx (TestClient)

---

## ファイルマップ

| ファイル | 責務 |
|---|---|
| `pyproject.toml` | プロジェクト設定・依存関係 |
| `src/pinance/__init__.py` | パッケージ初期化 |
| `src/pinance/database.py` | SQLite接続・スキーマ初期化 |
| `src/pinance/models.py` | Pydanticレスポンスモデル |
| `src/pinance/parsers/smbc.py` | 三井住友銀行CSVパーサー |
| `src/pinance/parsers/vpass.py` | VpassCSVパーサー |
| `src/pinance/routers/bank.py` | 銀行取引APIエンドポイント |
| `src/pinance/routers/card.py` | クレジットカードAPIエンドポイント |
| `src/pinance/main.py` | FastAPIアプリ・静的ファイル配信 |
| `src/pinance/static/index.html` | メイン画面HTML |
| `src/pinance/static/style.css` | スタイル |
| `src/pinance/static/app.js` | フロントエンドロジック（fetch・タブ・ナビ） |
| `tests/conftest.py` | pytest フィクスチャ（テスト用DB・TestClient） |
| `tests/test_database.py` | データベース初期化のテスト |
| `tests/test_smbc_parser.py` | SMBCパーサーのテスト |
| `tests/test_vpass_parser.py` | Vpassパーサーのテスト |
| `tests/test_bank_router.py` | 銀行APIのテスト |
| `tests/test_card_router.py` | カードAPIのテスト |

---

## Task 1: プロジェクトセットアップ

**Files:**
- Create: `pyproject.toml`
- Create: `src/pinance/__init__.py`
- Create: `src/pinance/parsers/__init__.py`
- Create: `src/pinance/routers/__init__.py`
- Create: `tests/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: pyproject.toml を作成する**

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "pinance"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "httpx",
]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: パッケージ初期化ファイルを作成する**

```bash
mkdir -p src/pinance/parsers src/pinance/routers src/pinance/static tests data
touch src/pinance/__init__.py
touch src/pinance/parsers/__init__.py
touch src/pinance/routers/__init__.py
touch tests/__init__.py
```

- [ ] **Step 3: .gitignore に data/ を追加する**

`.gitignore` に以下を追記:
```
/data
```

- [ ] **Step 4: 依存関係をインストールする（開発用含む）**

```bash
source .venv/Scripts/activate
pip install -e ".[dev]"
```

- [ ] **Step 6: pytest が動くことを確認する**

```bash
pytest --co -q
```
Expected: `no tests ran` または `0 items`（エラーなし）

---

## Task 2: データベースレイヤー

**Files:**
- Create: `src/pinance/database.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: テストを書く**

`tests/conftest.py` は空ファイルで作成する（将来の共通フィクスチャ用）:
```python
# 共通フィクスチャはここに追加
```

`tests/test_database.py`:
```python
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
```

- [ ] **Step 2: テストを実行してFAILを確認する**

```bash
pytest tests/test_database.py -v
```
Expected: `ImportError: No module named 'pinance.database'`

- [ ] **Step 3: database.py を実装する**

`src/pinance/database.py`:
```python
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
```

- [ ] **Step 4: テストを実行してPASSを確認する**

```bash
pytest tests/test_database.py -v
```
Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add pyproject.toml src/ tests/ .gitignore
git commit -m "feat: project setup and database schema"
```

---

## Task 3: SMBCパーサー

**Files:**
- Create: `src/pinance/parsers/smbc.py`
- Create: `tests/test_smbc_parser.py`

- [ ] **Step 1: テストを書く**

`tests/test_smbc_parser.py`:
```python
import io
from pinance.parsers.smbc import parse_smbc_csv

SAMPLE_CSV = """\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高
2024/8/27,34291,,ﾔﾁﾝ,1652809
2024/8/27,2434,,ｾｲﾒｲ ﾎｹﾝﾘﾖｳ,1687100
2024/8/23,,229673,給料振込　ｲｯﾊﾟﾝ(ｶ,1813703
"""

def test_parse_smbc_returns_correct_row_count():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    assert len(rows) == 3

def test_parse_smbc_withdrawal_row():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    row = rows[0]
    assert row["date"] == "2024-08-27"
    assert row["withdrawal"] == 34291
    assert row["deposit"] == 0
    assert row["description"] == "ﾔﾁﾝ"
    assert row["balance"] == 1652809

def test_parse_smbc_deposit_row():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    row = rows[2]
    assert row["date"] == "2024-08-23"
    assert row["withdrawal"] == 0
    assert row["deposit"] == 229673

def test_parse_smbc_empty_amounts_become_zero():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    assert rows[0]["deposit"] == 0
    assert rows[2]["withdrawal"] == 0
```

- [ ] **Step 2: テストがFAILすることを確認する**

```bash
pytest tests/test_smbc_parser.py -v
```
Expected: `ImportError`

- [ ] **Step 3: smbc.py を実装する**

`src/pinance/parsers/smbc.py`:
```python
import csv
import io
from typing import TextIO

def parse_smbc_csv(file: TextIO) -> list[dict]:
    """三井住友銀行CSVを解析してdictのリストを返す。

    各dictのキー: date (str), withdrawal (int), deposit (int),
                  description (str), balance (int)
    """
    reader = csv.reader(file)
    next(reader)  # ヘッダー行をスキップ

    rows = []
    for row in reader:
        if len(row) < 5:
            continue
        date_parts = row[0].strip().split("/")
        if len(date_parts) != 3:
            continue
        date = f"{date_parts[0]}-{int(date_parts[1]):02d}-{int(date_parts[2]):02d}"
        rows.append({
            "date": date,
            "withdrawal": int(row[1]) if row[1].strip() else 0,
            "deposit": int(row[2]) if row[2].strip() else 0,
            "description": row[3].strip(),
            "balance": int(row[4]),
        })
    return rows
```

- [ ] **Step 4: テストがPASSすることを確認する**

```bash
pytest tests/test_smbc_parser.py -v
```
Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add src/pinance/parsers/smbc.py tests/test_smbc_parser.py
git commit -m "feat: SMBC CSV parser"
```

---

## Task 4: Vpassパーサー

**Files:**
- Create: `src/pinance/parsers/vpass.py`
- Create: `tests/test_vpass_parser.py`

- [ ] **Step 1: テストを書く**

`tests/test_vpass_parser.py`:
```python
import io
from pinance.parsers.vpass import parse_vpass_csv

SAMPLE_CSV = """\ufeff田中　太郎　様,4990-06**-****-****,ダミー銀行カードＶＩＳＡ（EEEE）,,,,,,,,
2026/3/16,ダミースーパー 世田谷店,1726,1,1,1726,,,,,
2026/3/15,ダミースーパー 世田谷店,2242,1,1,2242,,,,,
2026/3/15,ＮｅｗＤａｙｓ・ＫＩＯＳＫ  世田谷店,291,1,1,291,,,,,
2026/3/15,ダミースーパー 世田谷店,2242,1,1,2242,,,,,
"""

def test_parse_vpass_returns_correct_row_count():
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    assert len(rows) == 4

def test_parse_vpass_first_row():
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    row = rows[0]
    assert row["date"] == "2026-03-16"
    assert row["merchant"] == "ダミースーパー 世田谷店"
    assert row["amount"] == 1726
    assert row["row_index"] == 0

def test_parse_vpass_row_index_increments():
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    assert rows[0]["row_index"] == 0
    assert rows[1]["row_index"] == 1
    assert rows[2]["row_index"] == 2

def test_parse_vpass_same_merchant_same_amount_different_row_index():
    """同日・同店舗・同金額でも row_index が異なれば別レコードになる"""
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    same = [r for r in rows if r["date"] == "2026-03-15" and r["merchant"] == "ダミースーパー 世田谷店"]
    assert len(same) == 2
    assert same[0]["row_index"] != same[1]["row_index"]
```

- [ ] **Step 2: テストがFAILすることを確認する**

```bash
pytest tests/test_vpass_parser.py -v
```
Expected: `ImportError`

- [ ] **Step 3: vpass.py を実装する**

`src/pinance/parsers/vpass.py`:
```python
import csv
from typing import TextIO

def parse_vpass_csv(file: TextIO) -> list[dict]:
    """Vpass CSVを解析してdictのリストを返す。

    各dictのキー: date (str), merchant (str), amount (int), row_index (int)
    1行目はカード会員情報のためスキップ。
    """
    reader = csv.reader(file)
    next(reader)  # カード会員情報行をスキップ

    rows = []
    for row_index, row in enumerate(reader):
        if len(row) < 3:
            continue
        date_str = row[0].strip()
        if not date_str or "/" not in date_str:
            continue
        date_parts = date_str.split("/")
        if len(date_parts) != 3:
            continue
        date = f"{date_parts[0]}-{int(date_parts[1]):02d}-{int(date_parts[2]):02d}"
        rows.append({
            "date": date,
            "merchant": row[1].strip(),
            "amount": int(row[2].strip()),
            "row_index": row_index,
        })
    return rows
```

- [ ] **Step 4: テストがPASSすることを確認する**

```bash
pytest tests/test_vpass_parser.py -v
```
Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add src/pinance/parsers/vpass.py tests/test_vpass_parser.py
git commit -m "feat: Vpass CSV parser"
```

---

## Task 5: Pydanticモデルと銀行APIルーター

**Files:**
- Create: `src/pinance/models.py`
- Create: `src/pinance/routers/bank.py`
- Create: `tests/test_bank_router.py`

- [ ] **Step 1: テストを書く**

`tests/test_bank_router.py`:
```python
import pytest
import io
from fastapi.testclient import TestClient
from pinance.main import create_app

SAMPLE_CSV = """\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高
2024/8/27,34291,,ﾔﾁﾝ,1652809
2024/8/23,,229673,給料振込　ｲｯﾊﾟﾝ(ｶ,1813703
"""

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

def test_import_bank_csv(client):
    response = client.post(
        "/api/bank/import",
        files={"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0

def test_import_bank_csv_deduplicates(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    response = client.post("/api/bank/import", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert data["skipped"] == 2

def test_get_bank_transactions_all(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    response = client.get("/api/bank/transactions?period=all")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 2

def test_get_bank_transactions_by_month(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    response = client.get("/api/bank/transactions?period=month&date=2024-08")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 2
    assert data["period_label"] == "2024年8月"

def test_get_bank_transactions_wrong_month_returns_empty(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    response = client.get("/api/bank/transactions?period=month&date=2024-07")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 0

def test_import_bank_non_csv_returns_400(client):
    response = client.post(
        "/api/bank/import",
        files={"file": ("data.txt", b"not a csv", "text/plain")},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: テストがFAILすることを確認する**

```bash
pytest tests/test_bank_router.py -v
```
Expected: `ImportError: cannot import name 'create_app' from 'pinance.main'`

- [ ] **Step 3: models.py を作成する**

`src/pinance/models.py`:
```python
from pydantic import BaseModel

class BankTransaction(BaseModel):
    id: int
    date: str
    withdrawal: int
    deposit: int
    description: str
    balance: int

class BankTransactionsResponse(BaseModel):
    period_label: str
    transactions: list[BankTransaction]

class CardTransaction(BaseModel):
    id: int
    date: str
    merchant: str
    amount: int

class CardTransactionsResponse(BaseModel):
    period_label: str
    transactions: list[CardTransaction]

class ImportResponse(BaseModel):
    imported: int
    skipped: int
```

- [ ] **Step 4: bank.py ルーターを実装する**

`src/pinance/routers/bank.py`:
```python
import io
import sqlite3
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pinance.models import BankTransactionsResponse, BankTransaction, ImportResponse
from pinance.parsers.smbc import parse_smbc_csv

router = APIRouter(prefix="/api/bank", tags=["bank"])

def _make_period_label(period: str, date: str | None) -> str:
    if period == "all" or not date:
        return "全期間"
    if period == "year":
        return f"{date}年"
    if period == "month":
        parts = date.split("-")
        return f"{parts[0]}年{int(parts[1])}月"
    if period in ("day", "week"):
        parts = date.split("-")
        return f"{parts[0]}年{int(parts[1])}月{int(parts[2])}日"
    return date

def _build_where_clause(period: str, date: str | None) -> tuple[str, list]:
    if period == "all" or not date:
        return "", []
    if period == "day":
        return "WHERE date = ?", [date]
    if period == "week":
        from datetime import datetime, timedelta
        d = datetime.strptime(date, "%Y-%m-%d")
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        return "WHERE date BETWEEN ? AND ?", [
            monday.strftime("%Y-%m-%d"),
            sunday.strftime("%Y-%m-%d"),
        ]
    if period == "month":
        return "WHERE date LIKE ?", [f"{date}-%"]
    if period == "year":
        return "WHERE date LIKE ?", [f"{date}-%"]
    return "", []

def make_bank_router(db_path: str):
    router = APIRouter(prefix="/api/bank", tags=["bank"])

    @router.post("/import", response_model=ImportResponse)
    async def import_bank_csv(file: UploadFile = File(...)):
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="CSVファイルをアップロードしてください")
        content = await file.read()
        try:
            text = content.decode("utf-8-sig")
            rows = parse_smbc_csv(io.StringIO(text))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"不正なCSV形式です: {e}")

        conn = sqlite3.connect(db_path)
        imported = 0
        skipped = 0
        try:
            for row in rows:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO bank_transactions
                       (date, withdrawal, deposit, description, balance)
                       VALUES (?, ?, ?, ?, ?)""",
                    (row["date"], row["withdrawal"], row["deposit"],
                     row["description"], row["balance"]),
                )
                if cursor.rowcount == 1:
                    imported += 1
                else:
                    skipped += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail="データベースエラー")
        finally:
            conn.close()

        return ImportResponse(imported=imported, skipped=skipped)

    @router.get("/transactions", response_model=BankTransactionsResponse)
    def get_transactions(period: str = "all", date: str | None = None):
        where, params = _build_where_clause(period, date)
        query = f"SELECT * FROM bank_transactions {where} ORDER BY date DESC, id DESC"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        transactions = [
            BankTransaction(
                id=r["id"], date=r["date"], withdrawal=r["withdrawal"],
                deposit=r["deposit"], description=r["description"], balance=r["balance"]
            )
            for r in rows
        ]
        return BankTransactionsResponse(
            period_label=_make_period_label(period, date),
            transactions=transactions,
        )

    return router
```

- [ ] **Step 5: card.py のスタブを作る（main.py が import するために必要）**

`src/pinance/routers/card.py`:
```python
from fastapi import APIRouter

def make_card_router(db_path: str):
    router = APIRouter(prefix="/api/card", tags=["card"])
    return router
```

- [ ] **Step 6: main.py を作成する**

`src/pinance/main.py`:
```python
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pinance.database import init_db, DEFAULT_DB_PATH
from pinance.routers.bank import make_bank_router
from pinance.routers.card import make_card_router

def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    init_db(db_path)
    app = FastAPI(title="Pinance")
    app.include_router(make_bank_router(db_path))
    app.include_router(make_card_router(db_path))

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(static_dir, "index.html"))

    return app

app = create_app()
```

注: `src/pinance/static/` ディレクトリはTask 1 Step 2で作成済みなので `StaticFiles` は正常に動く。

- [ ] **Step 7: テストがPASSすることを確認する**

```bash
pytest tests/test_bank_router.py -v
```
Expected: 6 passed

- [ ] **Step 8: コミット**

```bash
git add src/pinance/models.py src/pinance/routers/bank.py src/pinance/routers/card.py src/pinance/main.py tests/test_bank_router.py
git commit -m "feat: bank API router with import and query endpoints"
```

---

## Task 6: カードAPIルーター

**Files:**
- Modify: `src/pinance/routers/card.py`（スタブを本実装に置き換え）
- Create: `tests/test_card_router.py`

- [ ] **Step 1: テストを書く**

`tests/test_card_router.py`:
```python
import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app

SAMPLE_CSV = """\ufeff田中　太郎　様,4990-06**-****-****,ダミー銀行カードＶＩＳＡ（EEEE）,,,,,,,,
2026/3/16,ダミースーパー 世田谷店,1726,1,1,1726,,,,,
2026/3/15,ダミースーパー 世田谷店,2242,1,1,2242,,,,,
2026/3/15,ＮｅｗＤａｙｓ・ＫＩＯＳＫ  世田谷店,291,1,1,291,,,,,
"""

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

def test_import_card_csv(client):
    response = client.post(
        "/api/card/import",
        files={"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 3
    assert data["skipped"] == 0

def test_import_card_csv_deduplicates(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    response = client.post("/api/card/import", files=files)
    assert response.json()["skipped"] == 3

def test_get_card_transactions_all(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    response = client.get("/api/card/transactions?period=all")
    assert response.status_code == 200
    assert len(response.json()["transactions"]) == 3

def test_get_card_transactions_by_month(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    response = client.get("/api/card/transactions?period=month&date=2026-03")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 3
    assert data["period_label"] == "2026年3月"
```

- [ ] **Step 2: テストがFAILすることを確認する**

```bash
pytest tests/test_card_router.py -v
```
Expected: インポートエラーまたはルーターにエンドポイントが存在しないエラー

- [ ] **Step 3: card.py を本実装に置き換える**

`src/pinance/routers/card.py`:
```python
import io
import sqlite3
from fastapi import APIRouter, UploadFile, File, HTTPException
from pinance.models import CardTransactionsResponse, CardTransaction, ImportResponse
from pinance.parsers.vpass import parse_vpass_csv
from pinance.routers.bank import _build_where_clause, _make_period_label

def make_card_router(db_path: str):
    router = APIRouter(prefix="/api/card", tags=["card"])

    @router.post("/import", response_model=ImportResponse)
    async def import_card_csv(file: UploadFile = File(...)):
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="CSVファイルをアップロードしてください")
        content = await file.read()
        try:
            text = content.decode("utf-8-sig")
            rows = parse_vpass_csv(io.StringIO(text))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"不正なCSV形式です: {e}")

        conn = sqlite3.connect(db_path)
        imported = 0
        skipped = 0
        try:
            for row in rows:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO card_transactions
                       (date, merchant, amount, row_index)
                       VALUES (?, ?, ?, ?)""",
                    (row["date"], row["merchant"], row["amount"], row["row_index"]),
                )
                if cursor.rowcount == 1:
                    imported += 1
                else:
                    skipped += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail="データベースエラー")
        finally:
            conn.close()

        return ImportResponse(imported=imported, skipped=skipped)

    @router.get("/transactions", response_model=CardTransactionsResponse)
    def get_transactions(period: str = "all", date: str | None = None):
        where, params = _build_where_clause(period, date)
        query = f"SELECT * FROM card_transactions {where} ORDER BY date DESC, id DESC"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        transactions = [
            CardTransaction(id=r["id"], date=r["date"], merchant=r["merchant"], amount=r["amount"])
            for r in rows
        ]
        return CardTransactionsResponse(
            period_label=_make_period_label(period, date),
            transactions=transactions,
        )

    return router
```

- [ ] **Step 4: 全テストがPASSすることを確認する**

```bash
pytest -v
```
Expected: 全て passed

- [ ] **Step 5: コミット**

```bash
git add src/pinance/routers/card.py tests/test_card_router.py
git commit -m "feat: card API router with import and query endpoints"
```

---

## Task 7: フロントエンド

**Files:**
- Create: `src/pinance/static/index.html`
- Create: `src/pinance/static/style.css`
- Create: `src/pinance/static/app.js`

- [ ] **Step 1: index.html を作成する**

`src/pinance/static/index.html`:
```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pinance</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <h1>Pinance</h1>
    <div class="import-buttons">
      <label class="btn">
        銀行CSV読込
        <input type="file" id="bank-file-input" accept=".csv" hidden>
      </label>
      <label class="btn">
        カードCSV読込
        <input type="file" id="card-file-input" accept=".csv" hidden>
      </label>
    </div>
  </header>

  <div id="toast" class="toast hidden"></div>

  <nav class="tabs">
    <button class="tab active" data-tab="bank">銀行取引</button>
    <button class="tab" data-tab="card">カード明細</button>
  </nav>

  <div class="period-nav">
    <select id="period-select">
      <option value="all">全て</option>
      <option value="month" selected>月</option>
      <option value="year">年</option>
      <option value="week">週</option>
      <option value="day">日</option>
    </select>
    <button id="prev-btn">&#8249; 前へ</button>
    <span id="period-label"></span>
    <button id="next-btn">次へ &#8250;</button>
  </div>

  <div class="table-container">
    <div id="bank-panel">
      <table>
        <thead>
          <tr>
            <th>日付</th>
            <th>引出し</th>
            <th>預入れ</th>
            <th>内容</th>
            <th>残高</th>
          </tr>
        </thead>
        <tbody id="bank-tbody"></tbody>
      </table>
    </div>
    <div id="card-panel" hidden>
      <table>
        <thead>
          <tr>
            <th>日付</th>
            <th>加盟店</th>
            <th>金額</th>
          </tr>
        </thead>
        <tbody id="card-tbody"></tbody>
      </table>
    </div>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css を作成する**

`src/pinance/static/style.css`:
```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body { font-family: sans-serif; font-size: 14px; color: #333; background: #f5f5f5; }

header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: #2c6fad; color: white;
}
header h1 { font-size: 20px; }

.btn {
  display: inline-block; padding: 6px 14px; background: white; color: #2c6fad;
  border-radius: 4px; cursor: pointer; font-size: 13px; margin-left: 8px;
}
.btn:hover { background: #e8f0fb; }

.import-buttons { display: flex; }

.toast {
  position: fixed; top: 16px; right: 16px; padding: 10px 18px;
  border-radius: 4px; font-size: 13px; z-index: 100;
  background: #333; color: white;
}
.toast.error { background: #c0392b; }
.hidden { display: none; }

.tabs { display: flex; border-bottom: 2px solid #2c6fad; margin: 0 20px; padding-top: 12px; }
.tab {
  padding: 8px 20px; border: none; background: none; cursor: pointer;
  font-size: 14px; color: #666; border-bottom: 2px solid transparent; margin-bottom: -2px;
}
.tab.active { color: #2c6fad; border-bottom-color: #2c6fad; font-weight: bold; }

.period-nav {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 20px; background: white; border-bottom: 1px solid #ddd;
}
.period-nav select { padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; }
.period-nav button {
  padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px;
  background: white; cursor: pointer;
}
.period-nav button:hover { background: #f0f0f0; }
#period-label { font-weight: bold; min-width: 120px; text-align: center; }

.table-container { padding: 16px 20px; }

table { width: 100%; border-collapse: collapse; background: white; border-radius: 4px; }
th { background: #f0f4f8; padding: 10px 12px; text-align: left; font-size: 13px; color: #555; }
td { padding: 8px 12px; border-bottom: 1px solid #eee; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }

.amount-out { color: #c0392b; }
.amount-in  { color: #27ae60; }
.text-right { text-align: right; }
```

- [ ] **Step 3: app.js を作成する**

`src/pinance/static/app.js`:
```javascript
const state = {
  tab: 'bank',
  period: 'month',
  date: currentDateForPeriod('month'),
};

function currentDateForPeriod(period) {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  if (period === 'year') return String(y);
  if (period === 'month') return `${y}-${m}`;
  if (period === 'day' || period === 'week') return `${y}-${m}-${d}`;
  return null;
}

function shiftDate(date, period, delta) {
  if (period === 'all') return null;
  if (period === 'year') {
    return String(parseInt(date) + delta);
  }
  if (period === 'month') {
    const [y, m] = date.split('-').map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }
  if (period === 'day' || period === 'week') {
    const [y, mo, dy] = date.split('-').map(Number);
    const d = new Date(y, mo - 1, dy);  // ローカルタイムで構築（タイムゾーンズレなし）
    const days = period === 'week' ? 7 : 1;
    d.setDate(d.getDate() + delta * days);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  return date;
}

function fmt(num) {
  return num === 0 ? '' : num.toLocaleString('ja-JP');
}

async function loadTransactions() {
  const { tab, period, date } = state;
  const params = new URLSearchParams({ period });
  if (period !== 'all' && date) params.set('date', date);

  const res = await fetch(`/api/${tab}/transactions?${params}`);
  if (!res.ok) { showToast('データ取得に失敗しました', true); return; }
  const data = await res.json();

  document.getElementById('period-label').textContent = data.period_label;

  if (tab === 'bank') {
    const tbody = document.getElementById('bank-tbody');
    tbody.innerHTML = data.transactions.map(t => `
      <tr>
        <td>${t.date}</td>
        <td class="text-right amount-out">${fmt(t.withdrawal)}</td>
        <td class="text-right amount-in">${fmt(t.deposit)}</td>
        <td>${t.description}</td>
        <td class="text-right">${t.balance.toLocaleString('ja-JP')}</td>
      </tr>`).join('');
  } else {
    const tbody = document.getElementById('card-tbody');
    tbody.innerHTML = data.transactions.map(t => `
      <tr>
        <td>${t.date}</td>
        <td>${t.merchant}</td>
        <td class="text-right amount-out">${t.amount.toLocaleString('ja-JP')}</td>
      </tr>`).join('');
  }
}

function showToast(msg, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast' + (isError ? ' error' : '');
  setTimeout(() => { el.className = 'toast hidden'; }, 3000);
}

async function importCsv(endpoint, file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(endpoint, { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.detail || 'インポートに失敗しました', true);
  } else {
    showToast(`${data.imported}件インポート、${data.skipped}件スキップ`);
    loadTransactions();
  }
}

// イベントリスナー
document.getElementById('bank-file-input').addEventListener('change', e => {
  if (e.target.files[0]) importCsv('/api/bank/import', e.target.files[0]);
  e.target.value = '';
});

document.getElementById('card-file-input').addEventListener('change', e => {
  if (e.target.files[0]) importCsv('/api/card/import', e.target.files[0]);
  e.target.value = '';
});

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    state.tab = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('bank-panel').hidden = state.tab !== 'bank';
    document.getElementById('card-panel').hidden = state.tab !== 'card';
    loadTransactions();
  });
});

document.getElementById('period-select').addEventListener('change', e => {
  state.period = e.target.value;
  state.date = currentDateForPeriod(state.period);
  const navBtns = document.querySelectorAll('#prev-btn, #next-btn');
  navBtns.forEach(b => b.style.visibility = state.period === 'all' ? 'hidden' : 'visible');
  loadTransactions();
});

document.getElementById('prev-btn').addEventListener('click', () => {
  state.date = shiftDate(state.date, state.period, -1);
  loadTransactions();
});

document.getElementById('next-btn').addEventListener('click', () => {
  state.date = shiftDate(state.date, state.period, 1);
  loadTransactions();
});

// 初期ロード
loadTransactions();
```

- [ ] **Step 4: サーバーを起動してブラウザで動作確認する**

```bash
uvicorn pinance.main:app --reload
```

ブラウザで `http://localhost:8000` を開き、以下を確認:
- ページが表示される
- 銀行CSVをアップロードするとトーストが表示され、一覧が更新される
- カードCSVをアップロードするとカード明細タブに反映される
- 期間ドロップダウンで切り替え、前へ/次へナビが動作する

- [ ] **Step 5: コミット**

```bash
git add src/pinance/static/
git commit -m "feat: frontend HTML/CSS/JS with CSV import and period navigation"
```

---

## Task 8: 全テスト・最終確認

- [ ] **Step 1: 全テストを実行する**

```bash
pytest -v
```
Expected: 全て passed（test_database.py, test_smbc_parser.py, test_vpass_parser.py, test_bank_router.py, test_card_router.py）

- [ ] **Step 2: README.md の起動手順を更新する**

`README.md` の末尾に追記:

```markdown
## セットアップ・起動

```bash
source .venv/Scripts/activate
pip install -e ".[dev]"
uvicorn pinance.main:app --reload
# → http://localhost:8000 をブラウザで開く
```

## テスト実行

```bash
pytest -v
```
```

- [ ] **Step 3: コミット**

```bash
git add README.md
git commit -m "docs: add setup and test instructions to README"
```
