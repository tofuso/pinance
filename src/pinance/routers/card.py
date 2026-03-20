import io
import re
import sqlite3
from fastapi import APIRouter, UploadFile, File, HTTPException
from pinance.models import CardTransactionsResponse, CardTransaction, ImportResponse, DeleteResponse
from pinance.parsers.vpass import parse_vpass_csv
from pinance.routers.bank import _build_where_clause, _make_period_label
from pinance.utils import decode_csv_bytes

def make_card_router(db_path: str):
    router = APIRouter(prefix="/api/card", tags=["card"])

    @router.post("/import", response_model=ImportResponse)
    async def import_card_csv(file: UploadFile = File(...)):
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="CSVファイルをアップロードしてください")
        content = await file.read()
        try:
            text = decode_csv_bytes(content)
            rows = parse_vpass_csv(io.StringIO(text))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"不正なCSV形式です: {e}")

        conn = sqlite3.connect(db_path)
        imported = 0
        skipped = 0
        try:
            for row in rows:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO card_transactions
                       (date, merchant, amount, row_index)
                       VALUES (?, ?, ?, ?)""",
                    (row["date"], row["merchant"], row["amount"], row["row_index"]),
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

    @router.get("/transactions", response_model=CardTransactionsResponse)
    def get_transactions(period: str = "all", date: str | None = None):
        where, params = _build_where_clause(period, date)
        query = f"SELECT * FROM card_transactions {where} ORDER BY date DESC, id DESC"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        transactions = [
            CardTransaction(id=r["id"], date=r["date"], merchant=r["merchant"], amount=r["amount"])
            for r in rows
        ]
        return CardTransactionsResponse(
            period_label=_make_period_label(period, date),
            transactions=transactions,
        )

    @router.get("/months", response_model=list[str])
    def get_months():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT DISTINCT substr(date, 1, 7) AS ym FROM card_transactions ORDER BY ym ASC"
            ).fetchall()
        finally:
            conn.close()
        return [row["ym"] for row in rows]

    @router.delete("/transactions", response_model=DeleteResponse)
    def delete_transactions(year_month: str | None = None):
        if year_month is not None and not re.fullmatch(r"\d{4}-\d{2}", year_month):
            raise HTTPException(status_code=400, detail="year_monthはYYYY-MM形式で指定してください")
        conn = sqlite3.connect(db_path)
        try:
            if year_month:
                cursor = conn.execute(
                    "DELETE FROM card_transactions WHERE date LIKE ?",
                    [f"{year_month}-%"],
                )
            else:
                cursor = conn.execute("DELETE FROM card_transactions")
            conn.commit()
            deleted = cursor.rowcount
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=500, detail="データベースエラー")
        finally:
            conn.close()
        return DeleteResponse(deleted=deleted)

    return router
