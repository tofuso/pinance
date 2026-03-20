# チャート機能 設計書

## 概要

Pinanceに期間別収支グラフ機能を追加する。現在の期間ナビ（日・週・月・年・全て）に連動し、3種類のグラフをトグルで切り替えて表示する。

**対象機能（README.md）:**
> 収支の期間ごとの統計 — これまで入力した取引と残高をグラフで閲覧できること。

---

## アーキテクチャ

### バックエンド

新規エンドポイント: `GET /api/bank/chart-data`

- クエリパラメータ: `period`（year/month/week/day/all）、`date`（省略可）
- 既存の `_build_where_clause` / `_make_period_label` を活用
- 集計クエリで各バケットの `SUM(deposit)`, `SUM(withdrawal)`, 最終残高を算出
- 新規 Pydantic モデル `ChartData` を `models.py` に追加

### フロントエンド

- ECharts 5 を CDN（`jsdelivr.net`）で読み込み
- `index.html` にグラフエリア（トグルボタン＋チャート div）を追加
- `app.js` に `loadChart()` 関数を追加し、`loadAll()` から並列呼び出し
- `style.css` にグラフエリアのスタイルを追加

---

## バックエンド詳細

### エンドポイント

```
GET /api/bank/chart-data?period=year&date=2024
```

### レスポンス（`ChartData` モデル）

```json
{
  "labels":      ["1月", "2月", ..., "12月"],
  "deposits":    [229673, 0, 0, ...],
  "withdrawals": [34291, 0, 0, ...],
  "nets":        [195382, 0, 0, ...],
  "balances":    [1652809, 1652809, ...]
}
```

### 集計単位

| period | バケット単位 | labels 形式 |
|---|---|---|
| year | 月別（12本） | "1月"〜"12月" |
| month | 日別（月の日数分） | "1日"〜"31日" |
| week | 日別（7日） | "月"〜"日"（曜日） |
| day | 1本 | "M/D" |
| all | 月別（全データ期間） | "YYYY-MM" |

### 残高の扱い

- 各バケット内の**最後の取引の残高**を使用
- データが存在しないバケットは直前バケットの残高を引き継ぐ（前方補完）
- データが全くない場合は `0`

### ファイル変更

| ファイル | 変更内容 |
|---|---|
| `src/pinance/models.py` | `ChartData` モデル追加 |
| `src/pinance/routers/bank.py` | `GET /api/bank/chart-data` エンドポイント追加 |
| `tests/test_bank_router.py` | チャートエンドポイントのテスト追加 |

---

## フロントエンド詳細

### index.html 変更

トグルボタン＋グラフコンテナを `.period-nav` と `.summary-cards` の間に挿入:

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

ECharts CDN を `</body>` 直前に追加:
```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

### app.js 変更

`loadChart()` 関数を追加:
- `/api/bank/chart-data` をフェッチ
- アクティブなトグルに応じて3種類のグラフを切り替え
- `echarts.init(container)` でグラフを初期化（再呼び出し時は `dispose()` してから再初期化）
- `window.addEventListener('resize', () => chart.resize())` でレスポンシブ対応

**3種類のグラフ設定:**

| トグル | type | 系列 |
|---|---|---|
| 収入・支出 (`bar`) | bar（2系列） | 収入（#16a34a）・支出（#dc2626） |
| 収支差額 (`net`) | line（1系列） | net値を折れ線で描画。各データ点の `itemStyle.color` を net≥0 なら `#16a34a`、net<0 なら `#dc2626` で個別指定 |
| 残高推移 (`balance`) | line（1系列） | 残高（#3b82f6） |

`loadAll()` を更新し `loadChart()` も並列実行:
```javascript
function loadAll() {
  return Promise.all([loadTransactions(), loadSummary(), loadChart()]);
}
```

トグルボタンクリック時は API 再呼び出しなし（取得済みデータで再描画）。

`loadChart()` は `loadTransactions()` / `loadSummary()` と同様に `state.period` と `state.date` を参照してパラメータを構築する。

### style.css 変更

```css
.chart-section { padding: 16px 24px 0; }
.chart-toggle { display: flex; gap: 8px; margin-bottom: 12px; }
.chart-btn {
  padding: 5px 14px; border: 1px solid #d1d5db; border-radius: 6px;
  background: #fff; color: #374151; font-size: 13px; cursor: pointer;
}
.chart-btn.active {
  background: #3b82f6; color: #fff; border-color: #3b82f6;
}
#chart-container { height: 280px; }
```

### ファイル変更

| ファイル | 変更内容 |
|---|---|
| `src/pinance/static/index.html` | チャートセクション追加・ECharts CDN追加 |
| `src/pinance/static/app.js` | `loadChart()`・トグルロジック追加 |
| `src/pinance/static/style.css` | チャートエリアスタイル追加 |

---

## テスト方針

- `test_get_chart_data_year`: year/date=2024 で 12 本のラベルと数値配列を返すことを確認
- `test_get_chart_data_month`: month/date=2024-08 で日数分のラベルを返すことを確認
- `test_get_chart_data_empty`: データなしで全配列が 0 埋めされることを確認
- `test_get_chart_data_balance_forward_fill`: 残高が前方補完されることを確認

---

## 制約・除外事項

- グラフのアニメーション設定はEChartsデフォルトのまま（カスタム不要）
- `period === 'day'` は1本のバーのみ表示（折れ線は点で表示）
- カードCSVの支出はグラフ集計に含めない（口座取引のみ）
