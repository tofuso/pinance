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

def _generate_buckets(period: str, date: str | None) -> list[tuple[str, str]]:
    """(bucket_key, label) のリストを返す。
    period="all" は DB 問い合わせ結果に依存するため呼び出し元で処理する。"""
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
    return []

def make_bank_router(db_path: str):
    router = APIRouter(prefix="/api/bank", tags=["bank"])

    @router.post("/import", response_model=ImportResponse)
    async def import_bank_csv(file: UploadFile = File(...)):
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="CSVファイルをアップロードしてください")
        content = await file.read()
        try:
            text = decode_csv_bytes(content)
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

        if period == "all":
            if not rows:
                return ChartData(labels=[], deposits=[], withdrawals=[], nets=[], balances=[])
            months = sorted(set(r["date"][:7] for r in rows))
            def _month_label(ym: str) -> str:
                y, mo = ym.split("-")
                return f"{y}年{int(mo)}月"
            buckets = [(m, _month_label(m)) for m in months]
        else:
            buckets = _generate_buckets(period, date)

        if not buckets:
            return ChartData(labels=[], deposits=[], withdrawals=[], nets=[], balances=[])

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

    @router.get("/transactions/{transaction_id}/card-details", response_model=CardTransactionsResponse)
    def get_card_details(transaction_id: int):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT date FROM bank_transactions WHERE id = ?", [transaction_id]
            ).fetchone()
        finally:
            conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="取引が見つかりません")

        # カードは使用月の翌月に引き落とされるため、1ヶ月前の明細を検索する
        debit_year, debit_month = map(int, row["date"][:7].split("-"))
        if debit_month == 1:
            year_month = f"{debit_year - 1}-12"
        else:
            year_month = f"{debit_year}-{debit_month - 1:02d}"

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            card_rows = conn.execute(
                "SELECT * FROM card_transactions WHERE date LIKE ? ORDER BY date ASC, id ASC",
                [f"{year_month}-%"],
            ).fetchall()
        finally:
            conn.close()

        transactions = [
            CardTransaction(id=r["id"], date=r["date"], merchant=r["merchant"], amount=r["amount"])
            for r in card_rows
        ]
        return CardTransactionsResponse(
            period_label=_make_period_label("month", year_month),
            transactions=transactions,
        )

    return router
