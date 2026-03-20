# Pinance 設計ドキュメント

**日付:** 2026-03-20
**フェーズ:** フェーズ1（基盤実装）

---

## 概要

Pinanceは日本の金融機関が発行するCSVファイルを取り込み、銀行取引・クレジットカード明細をブラウザで閲覧できる家計簿ツール。

FastAPI（バックエンド） + バニラHTML/CSS/JS（フロントエンド） + SQLite（データ保存）で構成する。

---

## フェーズ1スコープ

実装する機能:
1. 三井住友銀行形式のCSV読み込み・重複除外・保存
2. Vpass形式のクレジットカードCSV読み込み・重複除外・保存
3. 銀行取引の時系列一覧表示
4. クレジットカード取引の一覧表示
5. 日・週・月・年単位の期間フィルタ＋前後ナビゲーション

フェーズ2以降（今回対象外）:
- グラフ・統計表示
- 銀行取引からクレジットカード内訳の展開表示

---

## ディレクトリ構成

```
pinance/
├── src/
│   └── pinance/
│       ├── main.py            # FastAPI アプリ・エントリポイント
│       ├── database.py        # SQLite 接続・スキーマ定義・初期化
│       ├── models.py          # Pydantic レスポンスモデル
│       ├── routers/
│       │   ├── bank.py        # 銀行取引 API エンドポイント
│       │   └── card.py        # クレジットカード API エンドポイント
│       ├── parsers/
│       │   ├── smbc.py        # 三井住友銀行 CSV パーサー
│       │   └── vpass.py       # Vpass CSV パーサー
│       └── static/
│           ├── index.html     # メイン画面（シングルページ）
│           ├── style.css
│           └── app.js         # fetch() でAPI呼び出し
├── data/
│   └── pinance.db             # SQLite DB（.gitignore で除外）
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

---

## データモデル

### `bank_transactions` テーブル（銀行取引）

```sql
CREATE TABLE IF NOT EXISTS bank_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    withdrawal  INTEGER NOT NULL DEFAULT 0,
    deposit     INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL,
    balance     INTEGER NOT NULL,
    UNIQUE(date, withdrawal, deposit, description, balance)
);
```

- `date`: ISO形式 `"2024-08-27"`
- `withdrawal`: 引出し金額。CSV空欄の場合は `0` として保存
- `deposit`: 預入れ金額。CSV空欄の場合は `0` として保存
- `description`: 取り扱い内容（半角カナのまま保存）
- `balance`: 残高
- NULLを使わず `0` で統一することで UNIQUE制約が確実に機能する。`INSERT OR IGNORE` を使用。

### `card_transactions` テーブル（クレジットカード取引）

```sql
CREATE TABLE IF NOT EXISTS card_transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    merchant     TEXT NOT NULL,
    amount       INTEGER NOT NULL,
    row_index    INTEGER NOT NULL,
    UNIQUE(date, merchant, amount, row_index)
);
```

- `date`: ISO形式 `"2026-03-16"`
- `merchant`: 加盟店名
- `amount`: 利用金額（円）
- `row_index`: CSVファイル内での行番号（0始まり、ヘッダー行除く）。同日・同店舗・同金額の複数購入を区別するために使用
- `INSERT OR IGNORE` で重複除外。同一CSVを再インポートしても重複しない

---

## APIエンドポイント

### 銀行取引

| メソッド | パス | 説明 |
|---|---|---|
| `POST` | `/api/bank/import` | SMBCのCSVファイルをアップロード・インポート |
| `GET` | `/api/bank/transactions` | 取引一覧（クエリパラメータでフィルタ） |

**`POST /api/bank/import` レスポンス:**
```json
{"imported": 5, "skipped": 2}
```
エラー時: `{"detail": "エラーメッセージ"}` (HTTP 400)

**`GET /api/bank/transactions` クエリパラメータ:**

| パラメータ | 値 | `date` フォーマット例 | 説明 |
|---|---|---|---|
| `period` | `all` | 不要 | 全件 |
| `period` | `day` | `"2024-08-27"` | 指定日 |
| `period` | `week` | `"2024-08-26"` | 指定日を含む週（月〜日） |
| `period` | `month` | `"2024-08"` | 指定年月 |
| `period` | `year` | `"2024"` | 指定年 |

`date` 省略時は現在の日付を使用。

**`GET /api/bank/transactions` レスポンス:**
```json
{
  "period_label": "2024年8月",
  "transactions": [
    {
      "id": 1,
      "date": "2024-08-27",
      "withdrawal": 34291,
      "deposit": 0,
      "description": "ﾔﾁﾝ",
      "balance": 1652809
    }
  ]
}
```

### クレジットカード

| メソッド | パス | 説明 |
|---|---|---|
| `POST` | `/api/card/import` | VpassのCSVファイルをアップロード・インポート |
| `GET` | `/api/card/transactions` | カード取引一覧（クエリパラメータでフィルタ） |

**`POST /api/card/import` レスポンス:** 銀行と同形式 `{"imported": N, "skipped": N}`

**`GET /api/card/transactions` クエリパラメータ:** 銀行と同形式

**`GET /api/card/transactions` レスポンス:**
```json
{
  "period_label": "2026年3月",
  "transactions": [
    {
      "id": 1,
      "date": "2026-03-16",
      "merchant": "ダミースーパー 世田谷店",
      "amount": 1726
    }
  ]
}
```

### フロントエンド配信

| メソッド | パス | 説明 |
|---|---|---|
| `GET` | `/` | `index.html` を返す |
| `GET` | `/static/*` | CSS・JS等の静的ファイル |

---

## フロントエンドUI

シングルページ構成。

```
┌─────────────────────────────────────────────────────┐
│  Pinance                 [銀行CSV読込] [カードCSV読込] │
├─────────────────────────────────────────────────────┤
│  [銀行取引] [カード明細]  ← タブ切り替え               │
├─────────────────────────────────────────────────────┤
│  期間: [全て▼]  [< 前へ]  2024年8月  [次へ >]         │
├──────────┬──────────┬──────────┬────────────┬───────┤
│  日付    │  引出し  │  預入れ  │  内容      │  残高 │
├──────────┼──────────┼──────────┼────────────┼───────┤
│ 2024/8/27│  34,291  │          │ ヤチン     │1,652,809│
│ ...      │          │          │            │       │
└──────────┴──────────┴──────────┴────────────┴───────┘
```

- **CSVアップロード:** ボタン → ファイル選択 → `POST /api/*/import` → 結果トースト表示（例:「5件インポート、2件スキップ」）
- **タブ:** 銀行取引 / カード明細
- **期間フィルタ:** ドロップダウン（全て・日・週・月・年）
- **ナビゲーション:** 前へ / 次へ ボタンで期間を移動

### フロントエンドの期間ナビゲーション状態管理

クライアントサイドのJavaScriptで以下の状態を保持:
- `currentTab`: `"bank"` または `"card"`
- `currentPeriod`: `"all"` / `"day"` / `"week"` / `"month"` / `"year"`
- `currentDate`: 現在表示中の基準日文字列（period形式に合わせた形式）

前へ/次へボタン押下時は `currentDate` を period に応じてインクリメント/デクリメントし、APIを再度呼び出す。

---

## CSVフォーマット仕様

### 三井住友銀行 (`meisai_*.csv`)

- エンコーディング: UTF-8 BOM付き
- 1行目: ヘッダー（スキップ）
- 2行目以降: データ行

| 列インデックス | ヘッダー | 説明 |
|---|---|---|
| 0 | 年月日 | `2024/8/27` 形式 → `2024-08-27` に変換 |
| 1 | お引出し | 空欄の場合は `0` |
| 2 | お預入れ | 空欄の場合は `0` |
| 3 | お取り扱い内容 | 半角カナ文字列 |
| 4 | 残高 | 整数 |

### Vpass (`YYYYMM_*.csv`)

- エンコーディング: UTF-8 BOM付き
- 1行目: カード会員情報（スキップ）
- 2行目以降: 取引データ

| 列インデックス | 説明 |
|---|---|
| 0 | 利用日 `2026/3/16` 形式 → `2026-03-16` に変換 |
| 1 | 加盟店名 |
| 2 | 利用金額（円） |
| 3〜 | その他（無視） |

---

## エラーハンドリング

- **CSVフォーマットエラー:** HTTP 400 `{"detail": "不正なCSV形式です: <理由>"}`
- **非CSVファイルアップロード:** HTTP 400 `{"detail": "CSVファイルをアップロードしてください"}`
- **DBエラー:** HTTP 500 `{"detail": "データベースエラー"}`（詳細はサーバーログに出力）
- フロントエンドはレスポンスのHTTPステータスを確認し、エラー時はトーストにエラーメッセージを表示する

---

## 技術スタック

| 役割 | 技術 |
|---|---|
| バックエンド | FastAPI + uvicorn |
| データベース | SQLite（Pythonの `sqlite3` 標準ライブラリ） |
| フロントエンド | バニラHTML/CSS/JavaScript |
| CSV解析 | Pythonの `csv` 標準ライブラリ |
| パッケージ管理 | uv |

---

## 起動方法（予定）

```bash
source .venv/Scripts/activate
uvicorn pinance.main:app --reload
# → http://localhost:8000 をブラウザで開く
```
