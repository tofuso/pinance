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

# --- LLM設定モデル ---

class LlmSettings(BaseModel):
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str

class LlmSettingsPatch(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None

# --- AI分類モデル ---

class AiClassificationSuggestion(BaseModel):
    transaction_id: int
    transaction_type: str  # "bank" | "card"
    description: str
    suggested_category_id: int | None
    suggested_category_name: str | None
    suggested_keyword: str | None
    confidence: float

class AiClassificationApply(BaseModel):
    transaction_id: int
    transaction_type: str  # "bank" | "card"
    category_id: int | None = None        # 既存カテゴリのID
    category_name: str | None = None      # 新規カテゴリ名（category_id が None の場合に使用）
    category_type: str = "expense"        # 新規カテゴリの種別
    create_rule: bool = False
    keyword: str | None = None
    rule_target: str = "both"

class AiClassificationResult(BaseModel):
    applied: int
    rules_created: int
