import sqlite3
from datetime import datetime, timedelta
from fastapi import APIRouter
from pinance.models import (
    AnalyticsBreakdown, AnalyticsBreakdownItem,
    AnalyticsTrends,
    BalanceSheet, BalanceSheetItem,
)
from pinance.routers.bank import _make_period_label


def _date_filter(period: str, date_str: str | None, alias: str) -> tuple[str, list]:
    """テーブルエイリアス付きの日付フィルタ句を返す"""
    col = f"{alias}.date"
    if period == "all" or not date_str:
        return "", []
    if period == "day":
        return f"{col} = ?", [date_str]
    if period == "week":
        d = datetime.strptime(date_str, "%Y-%m-%d")
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        return f"{col} BETWEEN ? AND ?", [
            monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d"),
        ]
    if period in ("month", "year"):
        return f"{col} LIKE ?", [f"{date_str}-%"]
    return "", []


def make_analytics_router(db_path: str):
    router = APIRouter(prefix="/api/analytics", tags=["analytics"])

    @router.get("/breakdown", response_model=AnalyticsBreakdown)
    def get_breakdown(period: str = "month", date: str | None = None):
        bk_f, bk_p = _date_filter(period, date, "bt")
        cd_f, cd_p = _date_filter(period, date, "ct")
        bk_where = "WHERE c.type = 'expense'" + (f" AND {bk_f}" if bk_f else "")
        cd_where = "WHERE c.type = 'expense'" + (f" AND {cd_f}" if cd_f else "")
        bk_null = "WHERE bt.category_id IS NULL" + (f" AND {bk_f}" if bk_f else "")
        cd_null = "WHERE ct.category_id IS NULL" + (f" AND {cd_f}" if cd_f else "")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            bank_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(bt.withdrawal), 0) AS amount
                    FROM bank_transactions bt
                    JOIN categories c ON bt.category_id = c.id
                    {bk_where} GROUP BY c.id""",
                bk_p,
            ).fetchall()
            card_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(ct.amount), 0) AS amount
                    FROM card_transactions ct
                    JOIN categories c ON ct.category_id = c.id
                    {cd_where} GROUP BY c.id""",
                cd_p,
            ).fetchall()
            bank_null_count = conn.execute(
                f"SELECT COUNT(*) FROM bank_transactions bt {bk_null}", bk_p
            ).fetchone()[0]
            card_null_count = conn.execute(
                f"SELECT COUNT(*) FROM card_transactions ct {cd_null}", cd_p
            ).fetchone()[0]
            bank_null_amount = conn.execute(
                f"SELECT COALESCE(SUM(bt.withdrawal), 0) FROM bank_transactions bt {bk_null}", bk_p
            ).fetchone()[0]
            card_null_amount = conn.execute(
                f"SELECT COALESCE(SUM(ct.amount), 0) FROM card_transactions ct {cd_null}", cd_p
            ).fetchone()[0]
        finally:
            conn.close()

        totals: dict[str, int] = {}
        for r in list(bank_rows) + list(card_rows):
            totals[r["category"]] = totals.get(r["category"], 0) + r["amount"]

        items = sorted(
            [AnalyticsBreakdownItem(category=k, amount=v) for k, v in totals.items()],
            key=lambda x: -x.amount,
        )
        null_amount = bank_null_amount + card_null_amount
        if null_amount > 0:
            items.append(AnalyticsBreakdownItem(category="未分類", amount=null_amount))
        return AnalyticsBreakdown(
            period_label=_make_period_label(period, date),
            items=items,
            unclassified_count=bank_null_count + card_null_count,
        )

    @router.get("/trends", response_model=AnalyticsTrends)
    def get_trends(months: int = 6):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            latest_bk = conn.execute(
                "SELECT MAX(substr(date,1,7)) AS ym FROM bank_transactions"
            ).fetchone()["ym"]
            latest_cd = conn.execute(
                "SELECT MAX(substr(date,1,7)) AS ym FROM card_transactions"
            ).fetchone()["ym"]
        finally:
            conn.close()

        candidates = [ym for ym in [latest_bk, latest_cd] if ym]
        if not candidates:
            return AnalyticsTrends(months=[], labels=[], category_names=[], data={}, unclassified_count=0)

        latest_ym = max(candidates)
        year, month = map(int, latest_ym.split("-"))

        month_list: list[str] = []
        for i in range(months - 1, -1, -1):
            m = month - i
            y = year
            while m <= 0:
                m += 12
                y -= 1
            month_list.append(f"{y}-{m:02d}")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cat_rows = conn.execute(
                "SELECT id, name FROM categories WHERE type = 'expense' ORDER BY name ASC"
            ).fetchall()
            category_names = [r["name"] for r in cat_rows] + ["未分類"]

            data: dict[str, list[int]] = {name: [0] * months for name in category_names}
            unclassified_count = 0

            for i, ym in enumerate(month_list):
                bk_rows = conn.execute(
                    """SELECT c.name AS category, COALESCE(SUM(bt.withdrawal),0) AS amount
                       FROM bank_transactions bt
                       JOIN categories c ON bt.category_id = c.id
                       WHERE c.type = 'expense' AND bt.date LIKE ?
                       GROUP BY c.id""",
                    [f"{ym}-%"],
                ).fetchall()
                cd_rows = conn.execute(
                    """SELECT c.name AS category, COALESCE(SUM(ct.amount),0) AS amount
                       FROM card_transactions ct
                       JOIN categories c ON ct.category_id = c.id
                       WHERE c.type = 'expense' AND ct.date LIKE ?
                       GROUP BY c.id""",
                    [f"{ym}-%"],
                ).fetchall()
                for r in list(bk_rows) + list(cd_rows):
                    if r["category"] in data:
                        data[r["category"]][i] += r["amount"]

                null_bk_count = conn.execute(
                    "SELECT COUNT(*) FROM bank_transactions WHERE category_id IS NULL AND date LIKE ?",
                    [f"{ym}-%"],
                ).fetchone()[0]
                null_cd_count = conn.execute(
                    "SELECT COUNT(*) FROM card_transactions WHERE category_id IS NULL AND date LIKE ?",
                    [f"{ym}-%"],
                ).fetchone()[0]
                unclassified_count += null_bk_count + null_cd_count

                null_bk_amount = conn.execute(
                    "SELECT COALESCE(SUM(withdrawal), 0) FROM bank_transactions WHERE category_id IS NULL AND date LIKE ?",
                    [f"{ym}-%"],
                ).fetchone()[0]
                null_cd_amount = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM card_transactions WHERE category_id IS NULL AND date LIKE ?",
                    [f"{ym}-%"],
                ).fetchone()[0]
                data["未分類"][i] += null_bk_amount + null_cd_amount
        finally:
            conn.close()

        def label(ym: str) -> str:
            y, m = ym.split("-")
            return f"{y}年{int(m)}月"

        return AnalyticsTrends(
            months=month_list,
            labels=[label(ym) for ym in month_list],
            category_names=category_names,
            data=data,
            unclassified_count=unclassified_count,
        )

    @router.get("/balance-sheet", response_model=BalanceSheet)
    def get_balance_sheet(period: str = "month", date: str | None = None):
        bk_f, bk_p = _date_filter(period, date, "bt")
        cd_f, cd_p = _date_filter(period, date, "ct")
        bk_income_where = "WHERE c.type = 'income'" + (f" AND {bk_f}" if bk_f else "")
        bk_expense_where = "WHERE c.type = 'expense'" + (f" AND {bk_f}" if bk_f else "")
        cd_expense_where = "WHERE c.type = 'expense'" + (f" AND {cd_f}" if cd_f else "")
        bk_null = "WHERE bt.category_id IS NULL" + (f" AND {bk_f}" if bk_f else "")
        cd_null = "WHERE ct.category_id IS NULL" + (f" AND {cd_f}" if cd_f else "")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            income_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(bt.deposit),0) AS amount
                    FROM bank_transactions bt
                    JOIN categories c ON bt.category_id = c.id
                    {bk_income_where} GROUP BY c.id""",
                bk_p,
            ).fetchall()
            bk_expense_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(bt.withdrawal),0) AS amount
                    FROM bank_transactions bt
                    JOIN categories c ON bt.category_id = c.id
                    {bk_expense_where} GROUP BY c.id""",
                bk_p,
            ).fetchall()
            cd_expense_rows = conn.execute(
                f"""SELECT c.name AS category, COALESCE(SUM(ct.amount),0) AS amount
                    FROM card_transactions ct
                    JOIN categories c ON ct.category_id = c.id
                    {cd_expense_where} GROUP BY c.id""",
                cd_p,
            ).fetchall()
            bank_null_count = conn.execute(
                f"SELECT COUNT(*) FROM bank_transactions bt {bk_null}", bk_p
            ).fetchone()[0]
            card_null_count = conn.execute(
                f"SELECT COUNT(*) FROM card_transactions ct {cd_null}", cd_p
            ).fetchone()[0]
            null_income_amount = conn.execute(
                f"SELECT COALESCE(SUM(bt.deposit), 0) FROM bank_transactions bt {bk_null}", bk_p
            ).fetchone()[0]
            null_bk_expense_amount = conn.execute(
                f"SELECT COALESCE(SUM(bt.withdrawal), 0) FROM bank_transactions bt {bk_null}", bk_p
            ).fetchone()[0]
            null_cd_expense_amount = conn.execute(
                f"SELECT COALESCE(SUM(ct.amount), 0) FROM card_transactions ct {cd_null}", cd_p
            ).fetchone()[0]
        finally:
            conn.close()

        expense_totals: dict[str, int] = {}
        for r in list(bk_expense_rows) + list(cd_expense_rows):
            expense_totals[r["category"]] = expense_totals.get(r["category"], 0) + r["amount"]

        income = sorted(
            [BalanceSheetItem(category=r["category"], amount=r["amount"]) for r in income_rows],
            key=lambda x: -x.amount,
        )
        if null_income_amount > 0:
            income.append(BalanceSheetItem(category="未分類", amount=null_income_amount))

        expense = sorted(
            [BalanceSheetItem(category=k, amount=v) for k, v in expense_totals.items()],
            key=lambda x: -x.amount,
        )
        null_expense_amount = null_bk_expense_amount + null_cd_expense_amount
        if null_expense_amount > 0:
            expense.append(BalanceSheetItem(category="未分類", amount=null_expense_amount))

        total_income = sum(i.amount for i in income)
        total_expense = sum(e.amount for e in expense)
        return BalanceSheet(
            period_label=_make_period_label(period, date),
            income=income,
            expense=expense,
            total_income=total_income,
            total_expense=total_expense,
            net=total_income - total_expense,
            unclassified_count=bank_null_count + card_null_count,
        )

    return router
