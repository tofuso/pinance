import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app

@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    return TestClient(app)

# --- カテゴリ CRUD ---

def test_list_categories_includes_seed(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    names = [c["name"] for c in res.json()]
    assert "カード引き落とし" in names

def test_create_category(client):
    res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "食費"
    assert data["type"] == "expense"
    assert "id" in data

def test_create_category_duplicate_returns_409(client):
    client.post("/api/categories", json={"name": "食費", "type": "expense"})
    res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    assert res.status_code == 409

def test_create_category_invalid_type_returns_400(client):
    res = client.post("/api/categories", json={"name": "テスト", "type": "invalid"})
    assert res.status_code in (422, 400)

def test_update_category(client):
    create_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = create_res.json()["id"]
    res = client.put(f"/api/categories/{cat_id}", json={"name": "食費・日用品", "type": "expense"})
    assert res.status_code == 200
    assert res.json()["name"] == "食費・日用品"

def test_delete_category(client):
    create_res = client.post("/api/categories", json={"name": "テスト", "type": "expense"})
    cat_id = create_res.json()["id"]
    res = client.delete(f"/api/categories/{cat_id}")
    assert res.status_code == 200
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert "テスト" not in names

def test_delete_category_nullifies_transaction_category(client):
    """カテゴリ削除時に取引の category_id が NULL になること"""
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    SAMPLE_CSV = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,スーパー,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE_CSV.encode("utf-8-sig"), "text/csv")})
    tx_res = client.get("/api/bank/transactions?period=all")
    tx_id = tx_res.json()["transactions"][0]["id"]
    client.patch(f"/api/bank/transactions/{tx_id}/category", json={"category_id": cat_id})
    client.delete(f"/api/categories/{cat_id}")
    tx_res2 = client.get("/api/bank/transactions?period=all")
    assert tx_res2.json()["transactions"][0]["category_id"] is None

# --- ルール CRUD ---

def test_list_rules_includes_seed(client):
    res = client.get("/api/categories/rules")
    assert res.status_code == 200
    keywords = [r["keyword"] for r in res.json()]
    assert "ﾐﾂｲｽﾐﾄﾓｶ-ﾄﾞ" in keywords

def test_create_rule(client):
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    res = client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    assert res.status_code == 201
    data = res.json()
    assert data["keyword"] == "イオン"
    assert data["category_id"] == cat_id

def test_create_rule_duplicate_keyword_target_returns_409(client):
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    res = client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    assert res.status_code == 409

def test_delete_rule(client):
    cat_res = client.post("/api/categories", json={"name": "食費", "type": "expense"})
    cat_id = cat_res.json()["id"]
    rule_res = client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "both"})
    rule_id = rule_res.json()["id"]
    res = client.delete(f"/api/categories/rules/{rule_id}")
    assert res.status_code == 200
    keywords = [r["keyword"] for r in client.get("/api/categories/rules").json()]
    assert "イオン" not in keywords

def test_create_rule_retroactively_classifies_bank(client):
    """ルール追加後、既存の未分類銀行取引が遡及分類されること"""
    SAMPLE = "\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高\n2024/8/27,1000,,イオンモール,100000\n"
    client.post("/api/bank/import", files={"file": ("b.csv", SAMPLE.encode("utf-8-sig"), "text/csv")})
    tx = client.get("/api/bank/transactions?period=all").json()["transactions"][0]
    assert tx["category_id"] is None  # インポート時は未分類

    cat_id = client.post("/api/categories", json={"name": "食費", "type": "expense"}).json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "bank"})

    tx2 = client.get("/api/bank/transactions?period=all").json()["transactions"][0]
    assert tx2["category_id"] == cat_id

def test_create_rule_retroactively_classifies_card(client):
    """ルール追加後、既存の未分類カード取引が遡及分類されること"""
    CARD_CSV = (
        "\ufeff田中　太郎　様,4990-06**-****-****,ダミーカード,,,,,,,,\n"
        "2024/7/10,イオン,1500,1,1,1500,,,,,\n"
    )
    client.post("/api/card/import", files={"file": ("c.csv", CARD_CSV.encode("utf-8-sig"), "text/csv")})
    tx = client.get("/api/card/transactions?period=all").json()["transactions"][0]
    assert tx["category_id"] is None

    cat_id = client.post("/api/categories", json={"name": "食費", "type": "expense"}).json()["id"]
    client.post("/api/categories/rules", json={"keyword": "イオン", "category_id": cat_id, "target": "card"})

    tx2 = client.get("/api/card/transactions?period=all").json()["transactions"][0]
    assert tx2["category_id"] == cat_id
