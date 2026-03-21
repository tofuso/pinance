import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app

BANK_CSV = (
    "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n"
    "2024/8/27,3000,,イオンモール,100000\n"
    "2024/8/20,2000,,松屋,98000\n"
    "2024/8/15,,300000,給料,96000\n"
    "2024/7/25,5000,,スーパー,100000\n"
)

CARD_CSV = (
    "\ufeff田中　太郎　様,4990-06**-****-****,ダミーカード,,,,,,,,\n"
    "2024/7/10,コンビニ,500,1,1,500,,,,,\n"
    "2024/7/20,イオン,1500,2,1,1500,,,,,\n"
)

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

@pytest.fixture
def client_with_data(client):
    food_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    food_id = food_res.json()["id"]
    income_res = client.post("/api/categories", json={"name": "給与", "type": "income"})
    income_id = income_res.json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": food_id, "target": "both"})
    client.post("/api/categories/rules", json={"keyword": "松屋", "category_id": food_id, "target": "bank"})
    client.post("/api/categories/rules", json={"keyword": "給料", "category_id": income_id, "target": "bank"})
    client.post("/api/bank/import", files={"file": ("b.csv", BANK_CSV.encode("utf-8-sig"), "text/csv")})
    client.post("/api/card/import", files={"file": ("c.csv", CARD_CSV.encode("utf-8-sig"), "text/csv")})
    return client

def test_breakdown_returns_expense_by_category(client_with_data):
    res = client_with_data.get("/api/analytics/breakdown?period=month&date=2024-08")
    assert res.status_code == 200
    data = res.json()
    assert data["period_label"] == "2024年8月"
    amounts = {item["category"]: item["amount"] for item in data["items"]}
    assert amounts.get("食費", 0) == 5000  # 3000(イオン) + 2000(松屋)

def test_breakdown_unclassified_count(client_with_data):
    res = client_with_data.get("/api/analytics/breakdown?period=month&date=2024-07")
    assert res.status_code == 200
    data = res.json()
    # スーパー5000 は未分類
    assert data["unclassified_count"] >= 1

def test_breakdown_empty_period(client_with_data):
    res = client_with_data.get("/api/analytics/breakdown?period=month&date=2000-01")
    assert res.status_code == 200
    assert res.json()["items"] == []

def test_balance_sheet_income_and_expense(client_with_data):
    res = client_with_data.get("/api/analytics/balance-sheet?period=month&date=2024-08")
    assert res.status_code == 200
    data = res.json()
    income_names = [i["category"] for i in data["income"]]
    assert "給与" in income_names
    total_income = sum(i["amount"] for i in data["income"])
    assert total_income == 300000
    assert data["total_income"] == 300000
    assert data["net"] == data["total_income"] - data["total_expense"]

def test_balance_sheet_excludes_card_deduction(client_with_data):
    """カード引き落としは集計から除外されること"""
    DEDUCTION_CSV = (
        "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n"
        "2024/8/10,50000,,ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ (ｶ,50000\n"
    )
    client_with_data.post("/api/bank/import",
        files={"file": ("d.csv", DEDUCTION_CSV.encode("utf-8-sig"), "text/csv")})
    res = client_with_data.get("/api/analytics/balance-sheet?period=month&date=2024-08")
    expense_names = [e["category"] for e in res.json()["expense"]]
    assert "カード引き落とし" not in expense_names

def test_trends_returns_last_n_months(client_with_data):
    res = client_with_data.get("/api/analytics/trends?months=3")
    assert res.status_code == 200
    data = res.json()
    assert len(data["months"]) == 3
    assert len(data["labels"]) == 3

def test_trends_empty_db(client):
    res = client.get("/api/analytics/trends?months=6")
    assert res.status_code == 200
    data = res.json()
    assert data["months"] == []
