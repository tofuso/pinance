# チャート機能 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 期間ナビに連動した3種類の収支グラフ（収入・支出棒グラフ、収支差額折れ線、残高推移折れ線）をトグル切り替えで表示する。

**Architecture:** バックエンドに `GET /api/bank/chart-data` を追加し、期間ごとのバケット集計データを返す。フロントエンドは ECharts 5（CDN）でグラフを描画し、トグルボタンでグラフ種別を切り替える（APIコールは期間変更時のみ、切り替え時はキャッシュ済みデータで再描画）。

**Tech Stack:** FastAPI, SQLite3, Pydantic, Vanilla JS, ECharts 5（CDN）

---

## 対象ファイル

| ファイル | 変更内容 |
|---|---|
| `src/pinance/models.py` | `ChartData` モデル追加 |
| `src/pinance/routers/bank.py` | `_generate_buckets()` ヘルパー + `GET /api/bank/chart-data` エンドポイント追加 |
| `tests/test_bank_router.py` | チャートエンドポイントのテスト4件追加 |
| `src/pinance/static/index.html` | チャートセクション（トグルボタン + コンテナ）追加・ECharts CDN追加 |
| `src/pinance/static/style.css` | チャートエリアのスタイル追加 |
| `src/pinance/static/app.js` | `loadChart()`・`renderChart()`・トグルロジック追加、`loadAll()` 更新 |

---

### Task 1: ChartData モデルと chart-data エンドポイント

**Files:**
- Modify: `src/pinance/models.py`
- Modify: `src/pinance/routers/bank.py`
- Test: `tests/test_bank_router.py`

- [ ] **Step 1: テストを書く（失敗状態で追加）**

`tests/test_bank_router.py` の末尾に追加。`SAMPLE_CSV` は既存変数（2024/8/23 預入 229673、2024/8/27 引出 34291）:

```python
def test_get_chart_data_year(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/chart-data?period=year&date=2024")
    assert res.status_code == 200
    data = res.json()
    assert len(data["labels"]) == 12
    assert data["labels"][0] == "1月"
    assert data["labels"][7] == "8月"
    assert data["deposits"][7] == 229673
    assert data["withdrawals"][7] == 34291
    assert data["nets"][7] == 195382

def test_get_chart_data_month(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/chart-data?period=month&date=2024-08")
    assert res.status_code == 200
    data = res.json()
    assert len(data["labels"]) == 31
    assert data["labels"][0] == "1日"
    assert data["labels"][22] == "23日"
    assert data["deposits"][22] == 229673

def test_get_chart_data_empty(client):
    res = client.get("/api/bank/chart-data?period=year&date=1900")
    assert res.status_code == 200
    data = res.json()
    assert len(data["labels"]) == 12
    assert all(v == 0 for v in data["deposits"])
    assert all(v == 0 for v in data["withdrawals"])
    assert all(v == 0 for v in data["balances"])

def test_get_chart_data_balance_forward_fill(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/chart-data?period=year&date=2024")
    assert res.status_code == 200
    data = res.json()
    august_balance = data["balances"][7]
    assert august_balance > 0
    # 9月以降（データなし）は8月の残高を引き継ぐ
    assert data["balances"][8] == august_balance
    assert data["balances"][11] == august_balance
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd c:/dev/python/pinance && source .venv/Scripts/activate && pytest tests/test_bank_router.py::test_get_chart_data_year -v
```

期待: `FAILED` (エンドポイントが存在しない)

- [ ] **Step 3: `ChartData` モデルを `models.py` に追加**

`src/pinance/models.py` の末尾（`BankSummary` の後）に追加:

```python
class ChartData(BaseModel):
    labels: list[str]
    deposits: list[int]
    withdrawals: list[int]
    nets: list[int]
    balances: list[int]
```

- [ ] **Step 4: `bank.py` に `_generate_buckets()` と `chart-data` エンドポイントを追加**

`bank.py` の先頭インポートに `calendar` を追加し、`ChartData` をインポートに追加:

```python
import io
import sqlite3
import calendar
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, HTTPException
from pinance.models import (
    BankTransactionsResponse, BankTransaction,
    CardTransactionsResponse, CardTransaction,
    ImportResponse, BankSummary, ChartData,
)
from pinance.parsers.smbc import parse_smbc_csv
from pinance.utils import decode_csv_bytes
```

`_build_where_clause` の直後（`make_bank_router` の前）に `_generate_buckets` を追加:

```python
def _generate_buckets(period: str, date: str | None) -> list[tuple[str, str]]:
    """(bucket_key, label) のリストを返す。bucket_key は DB の date カラムとの比較に使う。"""
    if period == "year" and date:
        year = int(date)
        return [(f"{year}-{m:02d}", f"{m}月") for m in range(1, 13)]
    if period == "month" and date:
        year, month = map(int, date.split("-"))
        days_in_month = calendar.monthrange(year, month)[1]
        return [
            (f"{year}-{month:02d}-{d:02d}", f"{d}日")
            for d in range(1, days_in_month + 1)
        ]
    if period == "week" and date:
        d = datetime.strptime(date, "%Y-%m-%d")
        monday = d - timedelta(days=d.weekday())
        weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]
        return [
            ((monday + timedelta(days=i)).strftime("%Y-%m-%d"), weekday_labels[i])
            for i in range(7)
        ]
    if period == "day" and date:
        parts = date.split("-")
        return [(date, f"{int(parts[1])}/{int(parts[2])}")]
    return []  # all: DB から動的に生成
```

`make_bank_router` 内の `@router.get("/summary", ...)` の直前に以下を挿入:

```python
    @router.get("/chart-data", response_model=ChartData)
    def get_chart_data(period: str = "all", date: str | None = None):
        where, params = _build_where_clause(period, date)
        query = f"SELECT * FROM bank_transactions {where} ORDER BY date ASC, id ASC"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        # period=all のときはDBのデータから月バケットを動的生成
        if period == "all":
            if not rows:
                return ChartData(labels=[], deposits=[], withdrawals=[], nets=[], balances=[])
            months = sorted(set(r["date"][:7] for r in rows))
            buckets = [(m, m) for m in months]
        else:
            buckets = _generate_buckets(period, date)

        if not buckets:
            return ChartData(labels=[], deposits=[], withdrawals=[], nets=[], balances=[])

        # バケットキー抽出関数（year/all は YYYY-MM、その他は YYYY-MM-DD）
        use_month_key = period in ("year", "all")

        by_bucket: dict[str, list] = {key: [] for key, _ in buckets}
        for row in rows:
            key = row["date"][:7] if use_month_key else row["date"]
            if key in by_bucket:
                by_bucket[key].append(row)

        labels, deposits, withdrawals, nets, balances = [], [], [], [], []
        last_balance = 0
        for key, label in buckets:
            bucket_rows = by_bucket[key]
            total_deposit = sum(r["deposit"] for r in bucket_rows)
            total_withdrawal = sum(r["withdrawal"] for r in bucket_rows)
            if bucket_rows:
                last_balance = bucket_rows[-1]["balance"]
            labels.append(label)
            deposits.append(total_deposit)
            withdrawals.append(total_withdrawal)
            nets.append(total_deposit - total_withdrawal)
            balances.append(last_balance)

        return ChartData(
            labels=labels,
            deposits=deposits,
            withdrawals=withdrawals,
            nets=nets,
            balances=balances,
        )
```

- [ ] **Step 5: テストが通ることを確認**

```bash
pytest tests/test_bank_router.py -v
```

期待: 既存テスト含め全て `PASSED`（新規4件を含む計31件）

---

### Task 2: index.html にチャートセクションを追加

**Files:**
- Modify: `src/pinance/static/index.html`

- [ ] **Step 1: チャートセクションを `.period-nav` と `#summary-cards` の間に挿入**

`src/pinance/static/index.html` の `</div>` (`period-nav` 終了) と `<div id="summary-cards"` の間に追加:

```html
  <div id="chart-section" class="chart-section">
    <div class="chart-toggle">
      <button class="chart-btn active" data-chart="bar">収入・支出</button>
      <button class="chart-btn" data-chart="net">収支差額</button>
      <button class="chart-btn" data-chart="balance">残高推移</button>
    </div>
    <div id="chart-container"></div>
  </div>
```

- [ ] **Step 2: ECharts CDN を `</body>` 直前に追加**

既存の `<script src="/static/app.js"></script>` の直前に追加:

```html
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

最終的な `</body>` 付近:
```html
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <script src="/static/app.js"></script>
</body>
```

- [ ] **Step 3: ファイルの最終形を確認**

`src/pinance/static/index.html` を読んで、chart-section の位置と script タグの順序が正しいことを確認。

---

### Task 3: style.css にチャートスタイルを追加

**Files:**
- Modify: `src/pinance/static/style.css`

- [ ] **Step 1: チャートスタイルをファイル末尾の `@media` ブロックの直前に追加**

`/* ── レスポンシブ ── */` の直前に挿入:

```css
/* ── チャート ── */
.chart-section {
  padding: 16px 24px 0;
}

.chart-toggle {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.chart-btn {
  padding: 5px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.chart-btn:hover { background: #f9fafb; border-color: #9ca3af; }
.chart-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }

#chart-container {
  height: 280px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
```

`@media (max-width: 768px)` ブロック内の末尾（`td { white-space: normal; }` の後）に追加:

```css
  .chart-section { padding: 12px 16px 0; }
  #chart-container { height: 220px; }
```

- [ ] **Step 2: スタイルが正しく挿入されていることを確認**

`src/pinance/static/style.css` を読んで `.chart-btn.active` と `#chart-container` が存在することを確認。

---

### Task 4: app.js に loadChart() とトグルロジックを追加

**Files:**
- Modify: `src/pinance/static/app.js`

- [ ] **Step 1: モジュールレベル変数を追加**

`app.js` の先頭（`const state = ...` の直前）に追加:

```javascript
let chartData = null;
let chartInstance = null;
let activeChartType = 'bar';
```

- [ ] **Step 2: `renderChart()` 関数を追加**

`loadSummary()` の直前に追加:

```javascript
function renderChart(type) {
  const container = document.getElementById('chart-container');
  if (!container) return;

  if (!chartData || chartData.labels.length === 0) {
    if (chartInstance) { chartInstance.dispose(); chartInstance = null; }
    container.style.visibility = 'hidden';
    return;
  }
  container.style.visibility = '';

  if (chartInstance) { chartInstance.dispose(); }
  chartInstance = echarts.init(container);

  const axisLabelFormatter = v => '¥' + v.toLocaleString('ja-JP');
  const tooltip = { trigger: 'axis', valueFormatter: v => '¥' + (v || 0).toLocaleString('ja-JP') };

  let option;
  if (type === 'bar') {
    option = {
      tooltip,
      legend: { data: ['収入', '支出'], bottom: 0 },
      xAxis: { type: 'category', data: chartData.labels },
      yAxis: { type: 'value', axisLabel: { formatter: axisLabelFormatter } },
      series: [
        { name: '収入', type: 'bar', data: chartData.deposits, itemStyle: { color: '#16a34a' } },
        { name: '支出', type: 'bar', data: chartData.withdrawals, itemStyle: { color: '#dc2626' } },
      ],
    };
  } else if (type === 'net') {
    option = {
      tooltip,
      xAxis: { type: 'category', data: chartData.labels },
      yAxis: { type: 'value', axisLabel: { formatter: axisLabelFormatter } },
      series: [{
        name: '収支差額',
        type: 'line',
        data: chartData.nets.map(v => ({
          value: v,
          itemStyle: { color: v >= 0 ? '#16a34a' : '#dc2626' },
        })),
        lineStyle: { color: '#3b82f6' },
        symbol: 'circle',
      }],
    };
  } else {
    option = {
      tooltip,
      xAxis: { type: 'category', data: chartData.labels },
      yAxis: { type: 'value', axisLabel: { formatter: axisLabelFormatter } },
      series: [{
        name: '残高',
        type: 'line',
        data: chartData.balances,
        itemStyle: { color: '#3b82f6' },
        lineStyle: { color: '#3b82f6' },
        areaStyle: { color: 'rgba(59, 130, 246, 0.1)' },
        symbol: 'none',
      }],
    };
  }
  chartInstance.setOption(option);
}
```

- [ ] **Step 3: `loadChart()` 関数を追加**

`renderChart()` の直後に追加:

```javascript
async function loadChart() {
  const { period, date } = state;
  const params = new URLSearchParams({ period });
  if (date) params.set('date', date);

  const res = await fetch(`/api/bank/chart-data?${params}`);
  if (!res.ok) return;
  chartData = await res.json();
  renderChart(activeChartType);
}
```

- [ ] **Step 4: `loadAll()` を更新**

現在の `loadAll()`:
```javascript
function loadAll() {
  return Promise.all([loadTransactions(), loadSummary()]);
}
```

以下に変更:
```javascript
function loadAll() {
  return Promise.all([loadTransactions(), loadSummary(), loadChart()]);
}
```

- [ ] **Step 5: トグルボタンのイベントリスナーを追加**

ファイル末尾の `// 初期ロード` の直前に追加:

```javascript
document.querySelectorAll('.chart-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeChartType = btn.dataset.chart;
    renderChart(activeChartType);
  });
});

window.addEventListener('resize', () => {
  if (chartInstance) chartInstance.resize();
});
```

- [ ] **Step 6: 最終ファイルを確認**

`src/pinance/static/app.js` を読んで以下を確認:
- `chartData`, `chartInstance`, `activeChartType` が先頭近くに宣言されている
- `renderChart()` → `loadChart()` → `loadAll()` の順で定義されている
- `loadAll()` が `loadChart()` を含む `Promise.all` を返している
- トグルボタンリスナーと `window.resize` リスナーが追加されている

---

### Task 5: 全テストが通ることを確認

- [ ] **Step 1: 全テストを実行**

```bash
cd c:/dev/python/pinance && source .venv/Scripts/activate && pytest -v
```

期待: 全て `PASSED`（31件）

---

### Task 6: 動作確認

- [ ] **Step 1: サーバーを起動**

```bash
cd c:/dev/python/pinance && source .venv/Scripts/activate && uvicorn pinance.main:app --reload
```

- [ ] **Step 2: ブラウザで確認**

http://localhost:8000 を開き以下を確認:
1. 銀行CSVをインポートする
2. 期間を「年」に切り替えると棒グラフが表示される
3. 「収支差額」ボタンをクリックすると折れ線グラフに切り替わる
4. 「残高推移」ボタンで残高グラフが表示される
5. 「月」「週」「日」に切り替えるとグラフが更新される
6. 「全て」に切り替えても月別グラフが表示される
7. ブラウザ幅を768px以下に縮小してもグラフが正しく表示される
