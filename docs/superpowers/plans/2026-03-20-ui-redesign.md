# UIリッチ化・サマリーカード実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pinanceのフロントエンドをクリーン・ミニマルデザインに刷新し、期間別収支サマリーカードを追加してレスポンシブ対応する。

**Architecture:** バックエンドに `GET /api/bank/summary` を新規追加し、フロントエンドは既存 `loadTransactions()` と並列でサマリーAPIを呼び出してカード表示を更新する。スタイルは `style.css` を全面刷新し、`@media (max-width: 768px)` でモバイル対応する。

**Tech Stack:** FastAPI, SQLite3, Pydantic, Vanilla HTML/CSS/JS

---

## 対象ファイル

| ファイル | 変更内容 |
|---|---|
| `src/pinance/models.py` | `BankSummary` モデル追加 |
| `src/pinance/routers/bank.py` | `GET /api/bank/summary` エンドポイント追加 |
| `src/pinance/static/index.html` | サマリーカードHTML追加・ヘッダー変更 |
| `src/pinance/static/style.css` | 全面刷新（クリーン・ミニマル・レスポンシブ） |
| `src/pinance/static/app.js` | `loadSummary()` 追加・並列呼び出し |
| `tests/test_bank_router.py` | サマリーエンドポイントのテスト追加 |

---

### Task 1: BankSummaryモデルとAPIエンドポイントの追加

**Files:**
- Modify: `src/pinance/models.py`
- Modify: `src/pinance/routers/bank.py`
- Test: `tests/test_bank_router.py`

- [ ] **Step 1: テストを書く**

`tests/test_bank_router.py` に以下を追加（既存 `SAMPLE_BANK_CSV` を使用）:

```python
def test_get_summary_returns_totals(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_BANK_CSV.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/summary?period=all")
    assert res.status_code == 200
    data = res.json()
    assert "total_deposit" in data
    assert "total_withdrawal" in data
    assert "net" in data
    assert data["net"] == data["total_deposit"] - data["total_withdrawal"]

def test_get_summary_period_month(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_BANK_CSV.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/summary?period=month&date=2024-08")
    assert res.status_code == 200
    data = res.json()
    assert data["period_label"] == "2024年8月"
    assert data["total_withdrawal"] >= 0
    assert data["total_deposit"] >= 0

def test_get_summary_empty_period(client):
    res = client.get("/api/bank/summary?period=month&date=1900-01")
    assert res.status_code == 200
    data = res.json()
    assert data["total_deposit"] == 0
    assert data["total_withdrawal"] == 0
    assert data["net"] == 0
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/test_bank_router.py::test_get_summary_returns_totals -v
```

期待: `FAILED` (エンドポイントが存在しない)

- [ ] **Step 3: `BankSummary` モデルを `models.py` に追加**

`src/pinance/models.py` の末尾に追加:

```python
class BankSummary(BaseModel):
    period_label: str
    total_deposit: int
    total_withdrawal: int
    net: int
```

- [ ] **Step 4: `GET /api/bank/summary` エンドポイントを `bank.py` に追加**

`make_bank_router` 関数内の `return router` 直前に以下を挿入。インポート行も `BankSummary` を追加する。

```python
@router.get("/summary", response_model=BankSummary)
def get_summary(period: str = "all", date: str | None = None):
    where, params = _build_where_clause(period, date)
    query = f"""
        SELECT COALESCE(SUM(withdrawal), 0) AS total_withdrawal,
               COALESCE(SUM(deposit), 0)    AS total_deposit
        FROM bank_transactions {where}
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(query, params).fetchone()
    finally:
        conn.close()
    total_withdrawal = row["total_withdrawal"]
    total_deposit = row["total_deposit"]
    return BankSummary(
        period_label=_make_period_label(period, date),
        total_withdrawal=total_withdrawal,
        total_deposit=total_deposit,
        net=total_deposit - total_withdrawal,
    )
```

`bank.py` の先頭インポート行を更新:

```python
from pinance.models import (
    BankTransactionsResponse, BankTransaction,
    CardTransactionsResponse, CardTransaction,
    ImportResponse, BankSummary,
)
```

- [ ] **Step 5: テストが通ることを確認**

```bash
pytest tests/test_bank_router.py -v
```

期待: 既存テスト含め全て `PASSED`

---

### Task 2: index.html にサマリーカードを追加

**Files:**
- Modify: `src/pinance/static/index.html`

- [ ] **Step 1: `index.html` を以下の内容に全面置き換え**

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
    <h1 class="logo">Pinance</h1>
    <div class="import-buttons">
      <label class="btn">
        <span class="btn-full">銀行CSV読込</span>
        <span class="btn-short">銀行</span>
        <input type="file" id="bank-file-input" accept=".csv" hidden>
      </label>
      <label class="btn">
        <span class="btn-full">カードCSV読込</span>
        <span class="btn-short">カード</span>
        <input type="file" id="card-file-input" accept=".csv" hidden>
      </label>
    </div>
  </header>

  <div id="toast" class="toast hidden"></div>

  <div class="period-nav">
    <select id="period-select">
      <option value="all">全て</option>
      <option value="month" selected>月</option>
      <option value="year">年</option>
      <option value="week">週</option>
      <option value="day">日</option>
    </select>
    <button id="prev-btn">&#8249;</button>
    <span id="period-label"></span>
    <button id="next-btn">&#8250;</button>
  </div>

  <div id="summary-cards" class="summary-cards hidden">
    <div class="summary-card">
      <div class="summary-label">収入合計</div>
      <div class="summary-value deposit" id="summary-deposit">—</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">支出合計</div>
      <div class="summary-value withdrawal" id="summary-withdrawal">—</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">差引</div>
      <div class="summary-value net" id="summary-net">—</div>
    </div>
  </div>

  <div class="table-container">
    <div id="bank-panel">
      <table>
        <thead>
          <tr>
            <th>日付</th>
            <th class="col-amount text-right">引出し</th>
            <th class="col-amount text-right">預入れ</th>
            <th>内容</th>
            <th class="text-right">残高</th>
          </tr>
        </thead>
        <tbody id="bank-tbody"></tbody>
      </table>
    </div>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: ブラウザで表示確認（目視）**

`uvicorn pinance.main:app --reload` を起動し、ブラウザで http://localhost:8000 を開いてHTMLの構造が正しく反映されていることを確認。

---

### Task 3: style.css を全面刷新

**Files:**
- Modify: `src/pinance/static/style.css`

- [ ] **Step 1: `style.css` を以下の内容に全面置き換え**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
  font-size: 14px;
  color: #1e293b;
  background: #f8f9fa;
}

/* ── ヘッダー ── */
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: #0f172a;
}

.btn {
  display: inline-block;
  padding: 7px 16px;
  background: #ffffff;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  margin-left: 8px;
  transition: background 0.15s, border-color 0.15s;
}
.btn:hover { background: #f9fafb; border-color: #9ca3af; }

.btn-short { display: none; }

.import-buttons { display: flex; }

/* ── トースト ── */
.toast {
  position: fixed;
  top: 16px;
  right: 16px;
  padding: 10px 18px;
  border-radius: 6px;
  font-size: 13px;
  z-index: 100;
  background: #1e293b;
  color: white;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.toast.error { background: #ef4444; }
.hidden { display: none; }

/* ── 期間ナビ ── */
.period-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 24px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
}

.period-nav select {
  padding: 5px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  color: #374151;
}

.period-nav button {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 18px;
  color: #374151;
  transition: background 0.15s;
}
.period-nav button:hover { background: #f9fafb; border-color: #9ca3af; }

#period-label {
  font-weight: 600;
  font-size: 15px;
  min-width: 130px;
  text-align: center;
  color: #0f172a;
}

/* ── サマリーカード ── */
.summary-cards {
  display: flex;
  gap: 16px;
  padding: 20px 24px 4px;
}

.summary-card {
  flex: 1;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.summary-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
}

.summary-value.deposit { color: #16a34a; }
.summary-value.withdrawal { color: #dc2626; }
.summary-value.net.positive { color: #16a34a; }
.summary-value.net.negative { color: #dc2626; }

/* ── テーブル ── */
.table-container { padding: 20px 24px; }

table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

thead th {
  background: #f8fafc;
  padding: 10px 14px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  border-bottom: 1px solid #e2e8f0;
  position: sticky;
  top: 0;
  z-index: 1;
}

td {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
  white-space: nowrap;
}

tr:last-child td { border-bottom: none; }
tr:hover td { background: #eff6ff; }

.amount-out {
  color: #dc2626;
  font-variant-numeric: tabular-nums;
}
.amount-in {
  color: #16a34a;
  font-variant-numeric: tabular-nums;
}
.text-right { text-align: right; }

td:nth-child(5) { font-variant-numeric: tabular-nums; }

/* ── SMBC展開 ── */
.smbc-row { cursor: pointer; }
.smbc-row:hover td { background: #dbeafe; }
.expand-icon { font-size: 9px; color: #94a3b8; margin-left: 6px; }

.card-detail-row td {
  background: #f8fafc;
  padding-top: 6px;
  padding-bottom: 6px;
  font-size: 13px;
  border-bottom: 1px solid #f1f5f9;
  color: #475569;
}
.card-detail-indent { width: 32px; }
.card-detail-merchant { padding-left: 20px; }
.card-detail-empty { color: #94a3b8; padding-left: 48px; font-style: italic; }

/* ── レスポンシブ ── */
@media (max-width: 768px) {
  header { padding: 12px 16px; }
  .logo { font-size: 16px; }

  .btn-full { display: none; }
  .btn-short { display: inline; }
  .btn { padding: 7px 12px; }

  .period-nav { padding: 10px 16px; gap: 8px; }
  #period-label { min-width: 100px; font-size: 14px; }

  .summary-cards {
    flex-direction: column;
    padding: 16px 16px 4px;
    gap: 10px;
  }

  .summary-value { font-size: 20px; }

  .table-container { padding: 16px; }

  .col-amount { display: none; }

  td { white-space: normal; }
}
```

- [ ] **Step 2: ブラウザで表示確認（目視）**

デスクトップとモバイル幅（DevToolsで768px以下）の両方で表示を確認。

---

### Task 4: app.js に `loadSummary()` を追加

**Files:**
- Modify: `src/pinance/static/app.js`

- [ ] **Step 1: `loadSummary()` 関数を追加**

`app.js` の `loadTransactions()` 関数の直前に以下を挿入:

```javascript
async function loadSummary() {
  const { period, date } = state;
  const summaryCards = document.getElementById('summary-cards');

  if (period === 'all') {
    summaryCards.classList.add('hidden');
    return;
  }

  summaryCards.classList.remove('hidden');

  const params = new URLSearchParams({ period });
  if (date) params.set('date', date);

  const res = await fetch(`/api/bank/summary?${params}`);
  if (!res.ok) return;
  const data = await res.json();

  document.getElementById('summary-deposit').textContent =
    data.total_deposit === 0 ? '—' : '¥' + data.total_deposit.toLocaleString('ja-JP');
  document.getElementById('summary-withdrawal').textContent =
    data.total_withdrawal === 0 ? '—' : '¥' + data.total_withdrawal.toLocaleString('ja-JP');

  const netEl = document.getElementById('summary-net');
  netEl.textContent = data.net === 0 ? '—'
    : (data.net > 0 ? '+' : '') + '¥' + data.net.toLocaleString('ja-JP');
  netEl.className = 'summary-value net ' + (data.net >= 0 ? 'positive' : 'negative');
}
```

- [ ] **Step 2: `loadTransactions()` の呼び出し箇所を `loadSummary()` と並列化**

`loadTransactions()` 関数内の最後の行（`document.getElementById('period-label')` の更新は `loadTransactions` 側に残す）はそのまま。

各イベントリスナーおよび初期ロードで `loadTransactions()` を呼んでいる箇所を `Promise.all` に変更。まず `loadAll()` 関数を追加する:

```javascript
function loadAll() {
  return Promise.all([loadTransactions(), loadSummary()]);
}
```

次に以下の **1行だけ** を `loadAll()` に置き換える（各リスナーの他のロジックはそのまま残す）:

- `importCsv` 内138行目: `loadTransactions();` → `loadAll();`
- `period-select` changeリスナー内: `loadTransactions();` → `loadAll();`（`navBtns.forEach(...)` の visibility 切り替えロジックはそのまま残すこと）
- `prev-btn` clickリスナー内: `loadTransactions();` → `loadAll();`
- `next-btn` clickリスナー内: `loadTransactions();` → `loadAll();`
- ファイル末尾の初期ロード: `loadTransactions();` → `loadAll();`

- [ ] **Step 3: ブラウザで動作確認（目視）**

CSVをインポートして月表示に切り替え、サマリーカードに数値が表示されることを確認。「全て」に切り替えるとカードが非表示になることを確認。

---

### Task 5: 全テストが通ることを確認

- [ ] **Step 1: 全テストを実行**

```bash
pytest -v
```

期待: 既存テスト含め全て `PASSED`（Task 1 で追加したテスト3件を含む）

---

### Task 6: `.gitignore` に `.superpowers/` を追加

- [ ] **Step 1: `.gitignore` を確認・更新**

```bash
grep -q ".superpowers" c:/dev/python/pinance/.gitignore || echo ".superpowers/" >> c:/dev/python/pinance/.gitignore
```
