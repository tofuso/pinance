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
