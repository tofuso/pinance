import pytest
import io
from fastapi.testclient import TestClient
from pinance.main import create_app

SAMPLE_CSV = """\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高
2024/8/27,34291,,ﾔﾁﾝ,1652809
2024/8/23,,229673,給料振込　ｲｯﾊﾟﾝ(ｶ,1813703
"""

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

def test_import_bank_csv(client):
    response = client.post(
        "/api/bank/import",
        files={"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0

def test_import_bank_csv_deduplicates(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    response = client.post("/api/bank/import", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert data["skipped"] == 2

def test_get_bank_transactions_all(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    response = client.get("/api/bank/transactions?period=all")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 2

def test_get_bank_transactions_by_month(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    response = client.get("/api/bank/transactions?period=month&date=2024-08")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 2
    assert data["period_label"] == "2024年8月"

def test_get_bank_transactions_wrong_month_returns_empty(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    response = client.get("/api/bank/transactions?period=month&date=2024-07")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 0

def test_import_bank_non_csv_returns_400(client):
    response = client.post(
        "/api/bank/import",
        files={"file": ("data.txt", b"not a csv", "text/plain")},
    )
    assert response.status_code == 400

def test_import_bank_csv_cp932(client):
    csv_text = "年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,34291,,ヤチン,1652809\n"
    response = client.post(
        "/api/bank/import",
        files={"file": ("test.csv", csv_text.encode("cp932"), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1

SAMPLE_BANK_CSV_WITH_CARD = """\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高
2024/8/27,34291,,ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ (ｶ,1652809
"""

SAMPLE_CARD_CSV = """\ufeff田中　太郎　様,4990-06**-****-****,ダミーカード,,,,,,,,
2024/7/10,スーパー,3000,1,1,3000,,,,,
2024/7/20,コンビニ,500,1,1,500,,,,,
"""

def test_get_card_details_returns_matching_month(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_BANK_CSV_WITH_CARD.encode("utf-8-sig"), "text/csv")})
    client.post("/api/card/import",
        files={"file": ("card.csv", SAMPLE_CARD_CSV.encode("utf-8-sig"), "text/csv")})

    bank_res = client.get("/api/bank/transactions?period=all")
    bank_id = bank_res.json()["transactions"][0]["id"]

    res = client.get(f"/api/bank/transactions/{bank_id}/card-details")
    assert res.status_code == 200
    data = res.json()
    assert len(data["transactions"]) == 2
    assert data["period_label"] == "2024年7月"
    # category フィールドが含まれること
    assert "category_id" in data["transactions"][0]
    assert "category_name" in data["transactions"][0]

def test_get_card_details_returns_404_for_missing_transaction(client):
    res = client.get("/api/bank/transactions/999/card-details")
    assert res.status_code == 404

SAMPLE_BANK_CSV = """\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高
2024/8/27,34291,,ﾔﾁﾝ,1652809
2024/8/23,,229673,給料振込　ｲｯﾊﾟﾝ(ｶ,1813703
"""

def test_get_summary_returns_totals(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_BANK_CSV.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/summary?period=all")
    assert res.status_code == 200
    data = res.json()
    assert "total_deposit" in data
    assert "total_withdrawal" in data
    assert "net" in data
    assert data["net"] == data["total_deposit"] - data["total_withdrawal"]

def test_get_summary_period_month(client):
    client.post("/api/bank/import",
        files={"file": ("bank.csv", SAMPLE_BANK_CSV.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/summary?period=month&date=2024-08")
    assert res.status_code == 200
    data = res.json()
    assert data["period_label"] == "2024年8月"
    assert data["total_withdrawal"] >= 0
    assert data["total_deposit"] >= 0

def test_get_summary_empty_period(client):
    res = client.get("/api/bank/summary?period=month&date=1900-01")
    assert res.status_code == 200
    data = res.json()
    assert data["total_deposit"] == 0
    assert data["total_withdrawal"] == 0
    assert data["net"] == 0

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
    assert data["balances"][8] == august_balance
    assert data["balances"][11] == august_balance

# 複数月データ（2024-07 と 2024-08 が混在）
SAMPLE_CSV_TWO_MONTHS = (
    "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n"
    "2024/8/27,34291,,ﾔﾁﾝ,1652809\n"
    "2024/7/15,,100000,給料振込,1500000\n"
)

def test_get_bank_months_empty(client):
    res = client.get("/api/bank/months")
    assert res.status_code == 200
    assert res.json() == []

def test_get_bank_months_returns_unique_months(client):
    files = {"file": ("test.csv", SAMPLE_CSV_TWO_MONTHS.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.get("/api/bank/months")
    assert res.status_code == 200
    data = res.json()
    assert data == ["2024-07", "2024-08"]  # 昇順・重複なし

def test_delete_bank_transactions_all(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    # 削除後は空になっていること
    res2 = client.get("/api/bank/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_bank_transactions_all_when_empty(client):
    res = client.delete("/api/bank/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_bank_transactions_by_month(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions?year_month=2024-08")
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    res2 = client.get("/api/bank/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_bank_transactions_by_month_only_deletes_target(client):
    files = {"file": ("test.csv", SAMPLE_CSV_TWO_MONTHS.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions?year_month=2024-08")
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    # 2024-07のデータはDBに残っていること
    res2 = client.get("/api/bank/transactions?period=all")
    assert len(res2.json()["transactions"]) == 1
    assert res2.json()["transactions"][0]["date"] == "2024-07-15"

def test_delete_bank_transactions_by_month_when_no_match(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    res = client.delete("/api/bank/transactions?year_month=2023-01")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_bank_transactions_invalid_year_month_returns_400(client):
    res = client.delete("/api/bank/transactions?year_month=invalid")
    assert res.status_code == 400

def test_delete_bank_and_reimport(client):
    """削除後に同じCSVを再インポートできること"""
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/bank/import", files=files)
    client.delete("/api/bank/transactions")
    res = client.post("/api/bank/import",
        files={"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    assert res.status_code == 200
    assert res.json()["imported"] == 2

SAMPLE_BANK_FOR_CLASSIFY = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,イオンモール,100000\n"

def test_import_auto_classifies_by_rule(client):
    """インポート時にルールでカテゴリが付与されること"""
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "bank"})
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE_BANK_FOR_CLASSIFY.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/transactions?period=all")
    tx = res.json()["transactions"][0]
    assert tx["category_id"] == cat_id
    assert tx["category_name"] == "食費"

def test_import_unmatched_transaction_has_no_category(client):
    """マッチするルールがない取引は category_id が None であること"""
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE_BANK_FOR_CLASSIFY.encode("utf-8-sig"), "text/csv")})
    res = client.get("/api/bank/transactions?period=all")
    assert res.json()["transactions"][0]["category_id"] is None

def test_patch_bank_transaction_category(client):
    """PATCH で手動カテゴリ変更できること"""
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    SAMPLE = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,スーパー,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE.encode("utf-8-sig"), "text/csv")})
    tx_id = client.get("/api/bank/transactions?period=all").json()["transactions"][0]["id"]
    res = client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": cat_id})
    assert res.status_code == 200
    tx = client.get("/api/bank/transactions?period=all").json()["transactions"][0]
    assert tx["category_id"] == cat_id
    assert tx["category_name"] == "食費"

def test_patch_bank_transaction_category_clear(client):
    """category_id: null で分類をクリアできること"""
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    SAMPLE = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,スーパー,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE.encode("utf-8-sig"), "text/csv")})
    tx_id = client.get("/api/bank/transactions?period=all").json()["transactions"][0]["id"]
    client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": cat_id})
    res = client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": None})
    assert res.status_code == 200
    assert client.get("/api/bank/transactions?period=all").json()["transactions"][0]["category_id"] is None

def test_patch_bank_transaction_category_not_found(client):
    res = client.patch("/api/bank/transactions/9999/category", json={"category_id": None})
    assert res.status_code == 404

def test_bank_import_card_deduction_auto_excluded(client):
    """カード引き落とし行がシードルールで自動的に exclude カテゴリに分類されること"""
    CARD_CSV = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,50000,,ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ (ｶ,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", CARD_CSV.encode("utf-8-sig"), "text/csv")})
    tx = client.get("/api/bank/transactions?period=all").json()["transactions"][0]
    assert tx["category_name"] == "カード引き落とし"
