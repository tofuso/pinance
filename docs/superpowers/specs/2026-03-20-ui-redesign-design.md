# Pinance UIリッチ化 設計仕様

## 概要

Pinance のフロントエンドUIをクリーン・ミニマルデザインに刷新し、期間別サマリーカードを追加する。レスポンシブ対応も行う。

---

## 目標

- 全体デザインを白ベース・余白多め・モノクロ基調のクリーン・ミニマルスタイルに統一する
- 期間別の収入合計・支出合計・差引を3枚のサマリーカードで表示する
- テーブルの可読性を改善する（等幅フォント・列固定・ホバー色など）
- 768px 未満のモバイルでもレスポンシブに動作する

---

## アーキテクチャ

### バックエンド追加

**新エンドポイント:** `GET /api/bank/summary`

- クエリパラメータ: `period`, `date`（既存 `/api/bank/transactions` と同様）
- 既存の `_build_where_clause` を再利用して期間フィルタを構築
- `SUM(withdrawal)`, `SUM(deposit)` を集計して返す

**レスポンス:**
```json
{
  "period_label": "2024年8月",
  "total_deposit": 120000,
  "total_withdrawal": 80000,
  "net": 40000
}
```

**モデル追加:** `BankSummary` を `models.py` に追加

### フロントエンド変更

**index.html:**
- ヘッダーを白背景・下ボーダーに変更（現在の青ヘッダーを廃止）
- 期間ナビを中央寄せに変更
- サマリーカード3枚（収入合計・支出合計・差引）をテーブル上部に追加
- `<div id="summary-cards">` をテーブルコンテナの直前に配置

**style.css:**
- 全面刷新
- 背景: `#f8f9fa`
- アクセントカラー: `#3b82f6`（最小限）
- カード: 白・角丸8px・薄いシャドウ
- テーブル: 金額列に `font-variant-numeric: tabular-nums`
- ヘッダー固定: `thead th { position: sticky; top: 0; }`
- レスポンシブ: `@media (max-width: 768px)` で引出し・預入れ列を非表示

**app.js:**
- `loadSummary()` 関数を追加（`/api/bank/summary` を fetch してカード更新）
- `loadTransactions()` と並列で呼び出す
- `period === 'all'` のときはサマリーカードを非表示にする

---

## レスポンシブ仕様

| 幅 | サマリーカード | テーブル列 |
|---|---|---|
| ≥768px | 3枚横並び（flex） | 全5列表示 |
| <768px | 縦積み | 日付・内容・残高の3列（引出し・預入れを `display:none`） |

モバイルでは引出し・預入れ列（`.col-amount`クラス）を非表示。

---

## スタイル変更詳細

| 要素 | 現在 | 変更後 |
|---|---|---|
| ヘッダー背景 | `#2c6fad`（青） | `#ffffff`（白） + 下ボーダー |
| body背景 | `#f5f5f5` | `#f8f9fa` |
| フォント | `sans-serif` | `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` |
| インポートボタン | 白背景・青文字 | グレーボーダー・ダークテキスト |
| 引出し色 | `#c0392b` | `#ef4444` |
| 預入れ色 | `#27ae60` | `#22c55e` |
| テーブルヘッダー | `#f0f4f8` | `#f8fafc`（sticky） |
| 行ホバー | `#fafbfc` | `#eff6ff` |

---

## テスト方針

- `GET /api/bank/summary` のユニットテストを `tests/test_bank_router.py` に追加
  - 取引データをインポートして期間指定でサマリーを取得し、合計値を検証
  - `period=all` での全期間集計も検証
- フロントエンドのJavaScript変更はE2Eテストなし（既存方針踏襲）

---

## 対象ファイル

| ファイル | 変更種別 |
|---|---|
| `src/pinance/models.py` | `BankSummary` モデル追加 |
| `src/pinance/routers/bank.py` | `GET /api/bank/summary` エンドポイント追加 |
| `src/pinance/static/index.html` | サマリーカード追加・ヘッダー変更 |
| `src/pinance/static/style.css` | 全面刷新 |
| `src/pinance/static/app.js` | `loadSummary()` 追加・並列呼び出し |
| `tests/test_bank_router.py` | サマリーエンドポイントのテスト追加 |
