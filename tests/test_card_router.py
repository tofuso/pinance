import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app

SAMPLE_CSV = """\ufeff田中　太郎　様,4990-06**-****-****,ダミー銀行カードＶＩＳＡ（EEEE）,,,,,,,,
2026/3/16,ダミースーパー 世田谷店,1726,1,1,1726,,,,,
2026/3/15,ダミースーパー 世田谷店,2242,1,1,2242,,,,,
2026/3/15,ＮｅｗＤａｙｓ・ＫＩＯＳＫ  世田谷店,291,1,1,291,,,,,
"""

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
