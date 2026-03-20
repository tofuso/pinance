# 設計仕様：カテゴリ分類と収支分析機能

**作成日：** 2026-03-20
**対象ブランチ：** develop

---

## 概要

収入と支出のバランスシート作成と、カテゴリ別の支出可視化を実現するための機能追加。銀行取引とクレジットカード取引の両方を対象に、キーワードルールによる自動カテゴリ分類と手動補完を組み合わせる。

---

## 要件

| # | 要件 |
|---|---|
| R1 | 取引（銀行・カード両方）にカテゴリを付与できること |
| R2 | キーワードルールによりCSVインポート時に自動分類されること |
| R3 | 未分類の取引を手動でカテゴリ付与できること |
| R4 | カテゴリは `income`（収入）/ `expense`（支出）/ `exclude`（除外）の3種類を持つこと |
| R5 | `exclude` カテゴリにより、銀行のカード引き落とし行を二重計上から除外できること |
| R6 | 月別のカテゴリ別支出内訳を円グラフで表示できること（銀行＋カード統合） |
| R7 | カテゴリ別の月次推移を積み上げ棒グラフで表示できること |
| R8 | 収支バランスシート（収入カテゴリ合計・支出カテゴリ合計・差引）を表形式で表示できること |

---

## データモデル

### 新規テーブル

#### `categories`

```sql
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE,
    type TEXT    NOT NULL CHECK(type IN ('income', 'expense', 'exclude'))
);
```

| カラム | 説明 |
|---|---|
| `name` | カテゴリ名（例: "食費", "給与", "カード引き落とし"） |
| `type` | `income`: 収入 / `expense`: 支出 / `exclude`: 集計から除外 |

#### `category_rules`

```sql
CREATE TABLE IF NOT EXISTS category_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword     TEXT    NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    target      TEXT    NOT NULL DEFAULT 'both' CHECK(target IN ('bank', 'card', 'both')),
    UNIQUE(keyword, target)
);
```

| カラム | 説明 |
|---|---|
| `keyword` | 部分一致するキーワード（例: "イオン", "松屋"） |
| `category_id` | マッチ時に付与するカテゴリ |
| `target` | `bank`: 銀行取引のみ / `card`: カード取引のみ / `both`: 両方 |

`UNIQUE(keyword, target)` により同じキーワードと対象範囲の組み合わせの重複登録を防ぐ。

### 既存テーブルへの変更

```sql
ALTER TABLE bank_transactions ADD COLUMN category_id INTEGER REFERENCES categories(id);
ALTER TABLE card_transactions  ADD COLUMN category_id INTEGER REFERENCES categories(id);
```

`card_transactions` の既存カラム `row_index` はそのまま保持する。`category_id` のみを追加する。

### 外部キーと CASCADE の扱い

SQLite の外部キー制約は接続ごとに `PRAGMA foreign_keys = ON` を設定しないと有効にならない。既存の `get_connection()` にこの pragma を追加する。

カテゴリ削除時の取引 `category_id` の扱い：`ON DELETE SET NULL` は SQLite でサポートされていないため、カテゴリ削除の API エンドポイントで明示的に `UPDATE bank_transactions SET category_id = NULL WHERE category_id = ?` を実行してから DELETE する。

### 初期データ（シード）

`init_db()` 内で以下の初期カテゴリとルールを登録する。ユーザーが手動で設定する手間を省くため。

```sql
INSERT OR IGNORE INTO categories (name, type) VALUES ('カード引き落とし', 'exclude');
INSERT OR IGNORE INTO category_rules (keyword, category_id, target)
    SELECT 'ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ', id, 'bank' FROM categories WHERE name = 'カード引き落とし';
```

---

## カテゴリ分類ロジック

### インポート時の自動分類

1. CSVをパースして取引行を得る
2. `category_rules` を全件取得（リクエストスコープ内でキャッシュ）
3. 各取引の `description`（銀行）または `merchant`（カード）に対してキーワード部分一致を順番に試みる
4. `target` が一致するルールのみを対象とする（`target='bank'` は銀行取引のみ、`target='card'` はカード取引のみ）
5. 最初にマッチしたルール（`id` 昇順）の `category_id` を取引に付与する
6. どのルールにもマッチしない場合は `category_id = NULL`（未分類）

ルールの優先順位は `category_rules.id` 昇順（先に登録されたものを優先）。将来的な優先度の明示的な管理は現時点ではスコープ外。

### 二重計上の除外

- 銀行取引のうち `exclude` タイプのカテゴリに分類された行は、バランスシートおよび支出集計の合計から除外する
- 初期ルールにより「ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ」を含む description は自動的に除外される

### 手動変更

- `PATCH /api/bank/transactions/{id}/category` で `category_id` を上書きできる
- `PATCH /api/card/transactions/{id}/category` で同様に上書きできる

---

## APIエンドポイント

### カテゴリ管理 `/api/categories`

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/categories` | カテゴリ一覧取得 |
| POST | `/api/categories` | カテゴリ作成 |
| PUT | `/api/categories/{id}` | カテゴリ更新 |
| DELETE | `/api/categories/{id}` | カテゴリ削除（参照取引の category_id を NULL にしてから削除） |
| GET | `/api/categories/rules` | ルール一覧取得 |
| POST | `/api/categories/rules` | ルール作成 |
| DELETE | `/api/categories/rules/{id}` | ルール削除 |

### 既存エンドポイントの変更

- `POST /api/bank/import`：インポート時に自動分類を実行
- `POST /api/card/import`：同上
- `GET /api/bank/transactions`：レスポンスに `category_id` と `category_name`（nullable）を追加
- `GET /api/card/transactions`：同上
- `PATCH /api/bank/transactions/{id}/category`：手動カテゴリ変更（新規）
- `PATCH /api/card/transactions/{id}/category`：手動カテゴリ変更（新規）

既存の `BankTransaction` / `CardTransaction` Pydantic モデルに `category_id: int | None` と `category_name: str | None` フィールドを追加する。

### 分析 `/api/analytics`

既存の `period` + `date` パラメータパターンに合わせて統一する。

| メソッド | パス | クエリパラメータ | 説明 |
|---|---|---|---|
| GET | `/api/analytics/breakdown` | `period=month&date=2024-06` | カテゴリ別支出内訳（円グラフ用） |
| GET | `/api/analytics/trends` | `months=6` | カテゴリ別月次推移（棒グラフ用） |
| GET | `/api/analytics/balance-sheet` | `period=month&date=2024-06` または `period=year&date=2024` | 収支バランスシート |

#### `/api/analytics/breakdown` の集計対象

銀行取引（`type='expense'`）の `withdrawal` ＋ カード取引（`type='expense'`）の `amount` をカテゴリ名で統合して集計する。`type='exclude'` と `type='income'` は含めない。

レスポンス例：
```json
{
  "period_label": "2024年6月",
  "items": [
    { "category": "食費", "amount": 48000 },
    { "category": "外食", "amount": 20000 }
  ],
  "unclassified_count": 3
}
```

#### `/api/analytics/trends` の仕様

- 基準日：データベースに存在する最新月を起点として直近 `months` ヶ月分を返す
- データが存在しない月も含めてゼロ埋めで返す
- 各月のカテゴリ別金額（銀行＋カード統合）を返す
- レスポンスに `unclassified_count`（期間全体の未分類件数）を含める

#### `/api/analytics/balance-sheet` レスポンス例

```json
{
  "period_label": "2024年6月",
  "income": [
    { "category": "給与", "amount": 300000 }
  ],
  "expense": [
    { "category": "食費", "amount": 48000 },
    { "category": "外食", "amount": 20000 },
    { "category": "交通費", "amount": 12000 }
  ],
  "total_income": 300000,
  "total_expense": 80000,
  "net": 220000,
  "unclassified_count": 3
}
```

集計ロジック：
- **収入** = `bank_transactions` の `type='income'` カテゴリに分類された `deposit` 合計
- **支出** = `bank_transactions`（`type='expense'`）の `withdrawal` 合計 ＋ `card_transactions`（`type='expense'`）の `amount` 合計
- `type='exclude'` の取引はいずれの集計にも含めない
- `category_id=NULL`（未分類）の取引は集計から除外し、`unclassified_count` として件数を返す

---

## フロントエンド

### 新規タブ構成

既存の `index.html` に以下のタブを追加する（Chart.js を継続使用）。

#### ① 分析タブ

- **月選択セレクタ** — 表示対象の年月を選択
- **円グラフ** — 選択月のカテゴリ別支出内訳（`/api/analytics/breakdown`）
- **積み上げ棒グラフ** — 直近6ヶ月のカテゴリ別推移（`/api/analytics/trends`）
- **バランスシート表** — 収入・支出カテゴリ一覧と差引残高（`/api/analytics/balance-sheet`）
- 未分類件数の警告表示（「XX件が未分類です」）

#### ② カテゴリ管理タブ

- カテゴリ一覧テーブル（名前・タイプ・削除ボタン）
- カテゴリ追加フォーム（名前・タイプ選択）
- キーワードルール一覧テーブル（キーワード・対象カテゴリ・対象範囲・削除ボタン）
- ルール追加フォーム（キーワード・カテゴリ選択・対象選択）

#### ③ 既存取引一覧の変更

- 各取引行にカテゴリ名を表示（未分類の場合は「未分類」と表示）
- カテゴリ名クリックでインラインドロップダウンが開き、手動変更できる

---

## ファイル構成の変更

```
src/pinance/
├── database.py              # categories, category_rules テーブル追加・PRAGMA外部キー・初期シードデータ
├── models.py                # Category, CategoryRule, AnalyticsBreakdown 等のモデル追加
│                            # BankTransaction/CardTransaction に category_id, category_name 追加
├── routers/
│   ├── bank.py              # import に自動分類追加、PATCH エンドポイント追加
│   ├── card.py              # 同上
│   ├── categories.py        # 新規：カテゴリ・ルール CRUD
│   └── analytics.py         # 新規：分析エンドポイント
└── static/
    ├── index.html           # タブ追加
    ├── app.js               # 分析・カテゴリ管理の UI ロジック追加
    └── style.css            # スタイル追加
```

---

## 考慮事項

- **既存データの扱い**：既存のインポート済み取引は `category_id=NULL` のままとなる。ルール追加後に再インポートするか、手動分類で対応する
- **ルールの優先順位**：複数ルールがマッチした場合、`category_rules.id` 昇順（先に登録されたもの）を優先する。ユーザーによる明示的な優先度制御は将来のスコープ
- **後方互換性**：`BankTransaction` / `CardTransaction` への `category_id` / `category_name` 追加は nullable フィールドのため、既存フロントエンドは `undefined` として扱い動作を維持する
