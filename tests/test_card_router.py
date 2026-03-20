import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app

SAMPLE_CSV = """\ufeff田中　太郎　様,4990-06**-****-****,ダミー銀行カードＶＩＳＡ（EEEE）,,,,,,,,
2026/3/16,ダミースーパー 世田谷店,1726,1,1,1726,,,,,
2026/3/15,ダミースーパー 世田谷店,2242,1,1,2242,,,,,
2026/3/15,ＮｅｗＤａｙｓ・ＫＩＯＳＫ  世田谷店,291,1,1,291,,,,,
"""

SAMPLE_CSV_TWO_MONTHS = (
    "\ufeff田中　太郎　様,4990-06**-****-****,ダミー銀行カードＶＩＳＡ（EEEE）,,,,,,,,\n"
    "2026/3/16,ダミースーパー 世田谷店,1726,1,1,1726,,,,,\n"
    "2026/2/10,コンビニ 渋谷店,500,1,1,500,,,,,\n"
)

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

def test_import_card_csv(client):
    response = client.post(
        "/api/card/import",
        files={"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 3
    assert data["skipped"] == 0

def test_import_card_csv_deduplicates(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    response = client.post("/api/card/import", files=files)
    assert response.json()["skipped"] == 3

def test_get_card_transactions_all(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    response = client.get("/api/card/transactions?period=all")
    assert response.status_code == 200
    assert len(response.json()["transactions"]) == 3

def test_get_card_transactions_by_month(client):
    files = {"file": ("test.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    response = client.get("/api/card/transactions?period=month&date=2026-03")
    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 3
    assert data["period_label"] == "2026年3月"

def test_get_card_months_empty(client):
    res = client.get("/api/card/months")
    assert res.status_code == 200
    assert res.json() == []

def test_get_card_months_returns_unique_months(client):
    files = {"file": ("card.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.get("/api/card/months")
    assert res.status_code == 200
    data = res.json()
    assert "2026-03" in data
    assert data == sorted(data)  # 昇順

def test_delete_card_transactions_all(client):
    files = {"file": ("card.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.delete("/api/card/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 3
    res2 = client.get("/api/card/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_card_transactions_all_when_empty(client):
    res = client.delete("/api/card/transactions")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_card_transactions_by_month(client):
    files = {"file": ("card.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.delete("/api/card/transactions?year_month=2026-03")
    assert res.status_code == 200
    assert res.json()["deleted"] == 3
    res2 = client.get("/api/card/transactions?period=all")
    assert len(res2.json()["transactions"]) == 0

def test_delete_card_transactions_by_month_when_no_match(client):
    files = {"file": ("card.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.delete("/api/card/transactions?year_month=2023-01")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0

def test_delete_card_transactions_invalid_year_month_returns_400(client):
    res = client.delete("/api/card/transactions?year_month=invalid")
    assert res.status_code == 400

def test_delete_card_and_reimport(client):
    """削除後に同じCSVを再インポートできること"""
    files = {"file": ("card.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    client.delete("/api/card/transactions")
    res = client.post("/api/card/import",
        files={"file": ("card.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    assert res.status_code == 200
    assert res.json()["imported"] == 3

def test_delete_card_transactions_by_month_only_deletes_target(client):
    files = {"file": ("card.csv", SAMPLE_CSV_TWO_MONTHS.encode("utf-8-sig"), "text/csv")}
    client.post("/api/card/import", files=files)
    res = client.delete("/api/card/transactions?year_month=2026-03")
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    # 2026-02のデータはDBに残っていること
    res2 = client.get("/api/card/transactions?period=all")
    assert len(res2.json()["transactions"]) == 1
    assert res2.json()["transactions"][0]["date"] == "2026-02-10"
