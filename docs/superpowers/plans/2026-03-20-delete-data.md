# データ削除機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 銀行取引・カード取引データを全件または月単位で削除できる設定モーダルを追加する

**Architecture:** バックエンドに DELETE エンドポイントと月一覧 GET エンドポイントを追加し、フロントエンドのヘッダーに⚙ボタンを配置して設定モーダルから削除操作を行う。削除後は画面データを再読み込みし、ドロップダウンの月一覧も更新する。

**Tech Stack:** Python / FastAPI / SQLite / Vanilla JS / HTML / CSS

---

## ファイルマップ

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `src/pinance/models.py` | 修正 | `DeleteResponse` モデル追加 |
| `src/pinance/routers/bank.py` | 修正 | `GET /api/bank/months`・`DELETE /api/bank/transactions` 追加 |
| `src/pinance/routers/card.py` | 修正 | `GET /api/card/months`・`DELETE /api/card/transactions` 追加 |
| `src/pinance/static/index.html` | 修正 | ⚙ボタン・設定モーダルHTML追加 |
| `src/pinance/static/app.js` | 修正 | モーダル開閉・削除APIロジック追加 |
| `src/pinance/static/style.css` | 修正 | モーダルスタイル追加 |
| `tests/test_bank_router.py` | 修正 | 削除・月一覧APIのテスト追加 |
| `tests/test_card_router.py` | 修正 | 削除・月一覧APIのテスト追加 |

---

## Task 1: DeleteResponse モデルを追加する

**Files:**
- Modify: `src/pinance/models.py`

- [ ] **Step 1: `DeleteResponse` モデルを追加する**

`src/pinance/models.py` の末尾に追加：

```python
class DeleteResponse(BaseModel):
    deleted: int
```

- [ ] **Step 2: コミット**

```bash
git add src/pinance/models.py
git commit -m "feat: DeleteResponseモデルを追加"
```

---

## Task 2: 銀行取引の削除・月一覧APIを追加する（TDD）

**Files:**
- Modify: `src/pinance/routers/bank.py`
- Modify: `tests/test_bank_router.py`

> **テスト用CSVについて:** 既存の `SAMPLE_CSV` は 2024-08 のデータのみ。複数月にまたがる削除テストには別途 2 か月分のCSVを定義する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_bank_router.py` に以下を追加：

```python
# 複数月データ（2024-07 と 2024-08 が混在）
SAMPLE_CSV_TWO_MONTHS = (
    "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n"
    "2024/8/27,34291,,ﾔﾁﾝ,1652809\n"
    "2024/7/15,,100000,給料振込,1500000\n"
)

def test_get_bank_months_empty(client):
    res = client.get("/api/bank/months")
    assert res.status_code == 200
    assert res.json() == []

def test_get_bank_months_returns_unique_months(client):
    files = {"file": ("test.csv", SAMPLE_CSV_TWO_MONTHS.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.get("/api/bank/months")
    assert res.status_code == 200
    data = res.json()
    assert data == ["2024-07", "2024-08"]  # 昇順・重複なし

def test_delete_bank_transactions_all(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    # 削除後は空になっていること
    res2 = client.get("/api/bank/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_bank_transactions_all_when_empty(client):
    res = client.delete("/api/bank/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_bank_transactions_by_month(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions?year_month=2024-08")
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    res2 = client.get("/api/bank/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_bank_transactions_by_month_only_deletes_target(client):
    files = {"file": ("test.csv", SAMPLE_CSV_TWO_MONTHS.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions?year_month=2024-08")
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    # 2024-07のデータはDBに残っていること
    res2 = client.get("/api/bank/transactions?period=all")
    assert len(res2.json()["transactions"]) == 1
    assert res2.json()["transactions"][0]["date"] == "2024-07-15"

def test_delete_bank_transactions_by_month_when_no_match(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions?year_month=2023-01")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_bank_transactions_invalid_year_month_returns_400(client):
    res = client.delete("/api/bank/transactions?year_month=invalid")
    assert res.status_code == 400

def test_delete_bank_and_reimport(client):
    """削除後に同じCSVを再インポートできること"""
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    client.delete("/api/bank/transactions")
    res = client.post("/api/bank/import",
        files={"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    assert res.status_code == 200
    assert res.json()["imported"] == 2
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
pytest tests/test_bank_router.py::test_get_bank_months_empty -v
```

期待結果: FAIL（エンドポイントが存在しない）

- [ ] **Step 3: 銀行取引の削除・月一覧エンドポイントを実装する**

`src/pinance/routers/bank.py` のimport行に `DeleteResponse` と `re` を追加：

```python
import re
from pinance.models import (
    BankTransactionsResponse, BankTransaction,
    CardTransactionsResponse, CardTransaction,
    ImportResponse, BankSummary, ChartData, DeleteResponse,
)
```

`make_bank_router` 関数内、`return router` の直前に以下を追加：

```python
    @router.get("/months", response_model=list[str])
    def get_months():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT DISTINCT substr(date, 1, 7) AS ym FROM bank_transactions ORDER BY ym ASC"
            ).fetchall()
        finally:
            conn.close()
        return [row["ym"] for row in rows]

    @router.delete("/transactions", response_model=DeleteResponse)
    def delete_transactions(year_month: str | None = None):
        if year_month is not None and not re.fullmatch(r"\d{4}-\d{2}", year_month):
            raise HTTPException(status_code=400, detail="year_monthはYYYY-MM形式で指定してください")
        conn = sqlite3.connect(db_path)
        try:
            if year_month:
                cursor = conn.execute(
                    "DELETE FROM bank_transactions WHERE date LIKE ?",
                    [f"{year_month}-%"],
                )
            else:
                cursor = conn.execute("DELETE FROM bank_transactions")
            conn.commit()
            deleted = cursor.rowcount
        finally:
            conn.close()
        return DeleteResponse(deleted=deleted)
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
pytest tests/test_bank_router.py -v
```

期待結果: 全テスト PASS

- [ ] **Step 5: コミット**

```bash
git add src/pinance/routers/bank.py tests/test_bank_router.py
git commit -m "feat: 銀行取引の削除・月一覧APIを追加"
```

---

## Task 3: カード取引の削除・月一覧APIを追加する（TDD）

**Files:**
- Modify: `src/pinance/routers/card.py`
- Modify: `tests/test_card_router.py`

まず `tests/test_card_router.py` の内容を確認し、`client` フィクスチャと `SAMPLE_CARD_CSV` 定数が定義されているか確認すること。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_card_router.py` に以下を追加：

> `SAMPLE_CARD_CSV` が未定義の場合はファイル先頭に追加：
> ```python
> SAMPLE_CARD_CSV = """\ufeff田中　太郎　様,4990-06**-****-****,ダミーカード,,,,,,,,
> 2024/7/10,スーパー,3000,1,1,3000,,,,,
> 2024/7/20,コンビニ,500,1,1,500,,,,,
> """
> ```
>
> `client` フィクスチャが未定義の場合も `test_bank_router.py` と同様のパターンで追加：
> ```python
> @pytest.fixture
> def client(tmp_path):
>     db_path = str(tmp_path / "test.db")
>     app = create_app(db_path=db_path)
>     return TestClient(app)
> ```

```python
def test_get_card_months_empty(client):
    res = client.get("/api/card/months")
    assert res.status_code == 200
    assert res.json() == []

def test_get_card_months_returns_unique_months(client):
    files = {"file": ("card.csv", SAMPLE_CARD_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.get("/api/card/months")
    assert res.status_code == 200
    data = res.json()
    assert "2024-07" in data
    assert data == sorted(data)  # 昇順

def test_delete_card_transactions_all(client):
    files = {"file": ("card.csv", SAMPLE_CARD_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.delete("/api/card/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    res2 = client.get("/api/card/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_card_transactions_all_when_empty(client):
    res = client.delete("/api/card/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_card_transactions_by_month(client):
    files = {"file": ("card.csv", SAMPLE_CARD_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.delete("/api/card/transactions?year_month=2024-07")
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    res2 = client.get("/api/card/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_card_transactions_by_month_when_no_match(client):
    files = {"file": ("card.csv", SAMPLE_CARD_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.delete("/api/card/transactions?year_month=2023-01")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_card_transactions_invalid_year_month_returns_400(client):
    res = client.delete("/api/card/transactions?year_month=invalid")
    assert res.status_code == 400

def test_delete_card_and_reimport(client):
    """削除後に同じCSVを再インポートできること"""
    files = {"file": ("card.csv", SAMPLE_CARD_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    client.delete("/api/card/transactions")
    res = client.post("/api/card/import",
        files={"file": ("card.csv", SAMPLE_CARD_CSV.encode("utf-8-sig"), "text/csv")})
    assert res.status_code == 200
    assert res.json()["imported"] == 2
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
pytest tests/test_card_router.py::test_get_card_months_empty -v
```

期待結果: FAIL

- [ ] **Step 3: カード取引の削除・月一覧エンドポイントを実装する**

`src/pinance/routers/card.py` のimport行を更新：

```python
import re
import sqlite3
from fastapi import APIRouter, UploadFile, File, HTTPException
from pinance.models import CardTransactionsResponse, CardTransaction, ImportResponse, DeleteResponse
from pinance.parsers.vpass import parse_vpass_csv
from pinance.routers.bank import _build_where_clause, _make_period_label
from pinance.utils import decode_csv_bytes
```

`make_card_router` 関数内の `return router` 直前に以下を追加：

```python
    @router.get("/months", response_model=list[str])
    def get_months():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT DISTINCT substr(date, 1, 7) AS ym FROM card_transactions ORDER BY ym ASC"
            ).fetchall()
        finally:
            conn.close()
        return [row["ym"] for row in rows]

    @router.delete("/transactions", response_model=DeleteResponse)
    def delete_transactions(year_month: str | None = None):
        if year_month is not None and not re.fullmatch(r"\d{4}-\d{2}", year_month):
            raise HTTPException(status_code=400, detail="year_monthはYYYY-MM形式で指定してください")
        conn = sqlite3.connect(db_path)
        try:
            if year_month:
                cursor = conn.execute(
                    "DELETE FROM card_transactions WHERE date LIKE ?",
                    [f"{year_month}-%"],
                )
            else:
                cursor = conn.execute("DELETE FROM card_transactions")
            conn.commit()
            deleted = cursor.rowcount
        finally:
            conn.close()
        return DeleteResponse(deleted=deleted)
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
pytest tests/test_card_router.py -v
```

期待結果: 全テスト PASS

- [ ] **Step 5: 全テストが通ることを確認する**

```bash
pytest -v
```

期待結果: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add src/pinance/routers/card.py tests/test_card_router.py
git commit -m "feat: カード取引の削除・月一覧APIを追加"
```

---

## Task 4: 設定モーダルのHTMLとCSSを追加する

**Files:**
- Modify: `src/pinance/static/index.html`
- Modify: `src/pinance/static/style.css`

- [ ] **Step 1: ヘッダーに⚙ボタンを追加する**

`src/pinance/static/index.html` の `<div class="import-buttons">` の閉じタグ `</div>` の直後に追加：

```html
      <button id="settings-btn" class="btn btn-icon" title="データ管理">⚙</button>
```

- [ ] **Step 2: 設定モーダルのHTMLを追加する**

`<div id="toast" ...>` の直前に追加：

```html
  <div id="settings-modal" class="modal-overlay hidden">
    <div class="modal">
      <div class="modal-header">
        <h2>データ管理</h2>
        <button id="modal-close-btn" class="modal-close">✕</button>
      </div>
      <div class="modal-body">
        <section class="modal-section">
          <h3>銀行取引</h3>
          <div class="modal-row">
            <select id="bank-month-select" disabled>
              <option value="">（データなし）</option>
            </select>
            <button id="bank-delete-month-btn" class="btn btn-danger-outline" disabled>選択月を削除</button>
          </div>
          <div class="modal-row">
            <button id="bank-delete-all-btn" class="btn btn-danger">全件削除</button>
          </div>
        </section>
        <section class="modal-section">
          <h3>カード取引</h3>
          <div class="modal-row">
            <select id="card-month-select" disabled>
              <option value="">（データなし）</option>
            </select>
            <button id="card-delete-month-btn" class="btn btn-danger-outline" disabled>選択月を削除</button>
          </div>
          <div class="modal-row">
            <button id="card-delete-all-btn" class="btn btn-danger">全件削除</button>
          </div>
        </section>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: モーダルのCSSを追加する**

`src/pinance/static/style.css` の末尾に追加：

```css
/* 設定モーダル */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal-overlay.hidden {
  display: none;
}
.modal {
  background: #fff;
  border-radius: 8px;
  width: min(480px, 90vw);
  box-shadow: 0 4px 24px rgba(0,0,0,0.18);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}
.modal-header h2 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}
.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: #6b7280;
  padding: 4px 8px;
}
.modal-body {
  padding: 16px 20px;
}
.modal-section {
  padding: 12px 0;
}
.modal-section + .modal-section {
  border-top: 1px solid #e5e7eb;
}
.modal-section h3 {
  font-size: 0.85rem;
  font-weight: 600;
  color: #374151;
  margin: 0 0 10px;
}
.modal-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.modal-row select {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 0.85rem;
}
.btn-icon {
  font-size: 1rem;
  padding: 6px 10px;
  line-height: 1;
}
.btn-danger {
  background: #dc2626;
  color: #fff;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}
.btn-danger:hover {
  background: #b91c1c;
}
.btn-danger-outline {
  background: #fff;
  color: #dc2626;
  border: 1px solid #dc2626;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}
.btn-danger-outline:hover {
  background: #fef2f2;
}
.btn-danger:disabled,
.btn-danger-outline:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

- [ ] **Step 4: ブラウザで表示確認する**

サーバーを起動してモーダルが開閉できること、UIレイアウトが崩れていないことを目視確認する。

```bash
uvicorn pinance.main:app --reload
```

- [ ] **Step 5: コミット**

```bash
git add src/pinance/static/index.html src/pinance/static/style.css
git commit -m "feat: データ管理モーダルのHTMLとCSSを追加"
```

---

## Task 5: モーダルのJSロジックを実装する

**Files:**
- Modify: `src/pinance/static/app.js`

> **月表示の変換について:** APIは `"2024-08"` 形式を返すが、ドロップダウンには `"2024年8月"` と表示する。`formatYearMonth()` 関数で変換する。

- [ ] **Step 1: 月一覧ドロップダウンを更新するヘルパー関数を追加する**

`src/pinance/static/app.js` の `// イベントリスナー` コメントの直前に追加：

```js
function formatYearMonth(ym) {
  const [y, m] = ym.split('-');
  return `${y}年${parseInt(m, 10)}月`;
}

async function refreshModalMonths() {
  const [bankRes, cardRes] = await Promise.all([
    fetch('/api/bank/months'),
    fetch('/api/card/months'),
  ]);
  const bankMonths = bankRes.ok ? await bankRes.json() : [];
  const cardMonths = cardRes.ok ? await cardRes.json() : [];

  function populateSelect(selectId, deleteBtnId, months) {
    const sel = document.getElementById(selectId);
    const btn = document.getElementById(deleteBtnId);
    sel.innerHTML = '';
    if (months.length === 0) {
      // データなし: ドロップダウンと削除ボタンを無効化
      sel.innerHTML = '<option value="">（データなし）</option>';
      sel.disabled = true;
      btn.disabled = true;
    } else {
      months.forEach(ym => {
        const opt = document.createElement('option');
        opt.value = ym;
        opt.textContent = formatYearMonth(ym);
        sel.appendChild(opt);
      });
      sel.disabled = false;
      btn.disabled = false;
    }
  }

  populateSelect('bank-month-select', 'bank-delete-month-btn', bankMonths);
  populateSelect('card-month-select', 'card-delete-month-btn', cardMonths);
}
```

- [ ] **Step 2: `importCsv` 関数を修正してインポート後にモーダルの月一覧を更新する**

既存の `importCsv` 関数内の `loadAll()` 呼び出しを以下のように変更する（`loadAll()` の後に `refreshModalMonths()` を追加）：

```js
async function importCsv(endpoint, file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(endpoint, { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.detail || 'インポートに失敗しました', true);
  } else {
    showToast(`${data.imported}件インポート、${data.skipped}件スキップ`);
    loadAll();
    refreshModalMonths();
  }
}
```

- [ ] **Step 3: モーダル開閉・削除のイベントリスナーを追加する**

`// 初期ロード` コメントの直前に追加：

```js
// 設定モーダル
const settingsModal = document.getElementById('settings-modal');

document.getElementById('settings-btn').addEventListener('click', () => {
  settingsModal.classList.remove('hidden');
  refreshModalMonths();
});

document.getElementById('modal-close-btn').addEventListener('click', () => {
  settingsModal.classList.add('hidden');
});

settingsModal.addEventListener('click', e => {
  if (e.target === settingsModal) settingsModal.classList.add('hidden');
});

async function deleteData(endpoint) {
  const res = await fetch(endpoint, { method: 'DELETE' });
  if (!res.ok) { showToast('削除に失敗しました', true); return; }
  const data = await res.json();
  if (data.deleted === 0) {
    showToast('削除するデータがありません');
  } else {
    showToast(`${data.deleted}件削除しました`);
    loadAll();
  }
  refreshModalMonths();
}

document.getElementById('bank-delete-month-btn').addEventListener('click', () => {
  const ym = document.getElementById('bank-month-select').value;
  if (!ym) return;
  deleteData(`/api/bank/transactions?year_month=${ym}`);
});

document.getElementById('bank-delete-all-btn').addEventListener('click', () => {
  if (!confirm('銀行取引データを全件削除しますか？')) return;
  deleteData('/api/bank/transactions');
});

document.getElementById('card-delete-month-btn').addEventListener('click', () => {
  const ym = document.getElementById('card-month-select').value;
  if (!ym) return;
  deleteData(`/api/card/transactions?year_month=${ym}`);
});

document.getElementById('card-delete-all-btn').addEventListener('click', () => {
  if (!confirm('カード取引データを全件削除しますか？')) return;
  deleteData('/api/card/transactions');
});
```

- [ ] **Step 4: ブラウザで動作確認する**

以下のシナリオを手動確認する：

1. ⚙ボタンをクリックするとモーダルが開くこと
2. ✕ボタンおよびオーバーレイクリックでモーダルが閉じること
3. データが0件の状態でモーダルを開くと月選択と削除ボタンが無効化されていること
4. CSVをインポート後にモーダルを開くと月一覧にデータが表示されること（`YYYY年M月` 形式）
5. 月を選択して「選択月を削除」を押すとその月のデータが削除されること
6. 「全件削除」を押すと `confirm()` ダイアログが表示されること
7. `confirm()` でキャンセルすると何も起きないこと
8. 削除後にトーストが表示され、画面の取引一覧とドロップダウンが更新されること
9. CSVインポート後にモーダルを開くとドロップダウンが最新状態になっていること

- [ ] **Step 5: 全テストを実行する**

```bash
pytest -v
```

期待結果: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add src/pinance/static/app.js
git commit -m "feat: データ管理モーダルのJSロジックを追加"
```
