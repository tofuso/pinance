"""AI分類エンドポイントのテスト（LLMをモック）"""
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from pinance.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def client_with_data(tmp_path):
    """カテゴリと未分類トランザクション入りのクライアント"""
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    # カテゴリ作成
    client.post("/api/categories", json={"name": "食費", "type": "expense"})
    client.post("/api/categories", json={"name": "交通費", "type": "expense"})

    # 銀行取引を登録（直接SQLで）
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bank_transactions (date, withdrawal, deposit, description, balance) "
        "VALUES ('2024-06-01', 3000, 0, 'スーパーマーケット', 100000)"
    )
    conn.execute(
        "INSERT INTO bank_transactions (date, withdrawal, deposit, description, balance) "
        "VALUES ('2024-06-02', 500, 0, 'JR東日本', 99500)"
    )
    conn.commit()
    conn.close()
    return client


def _make_llm_response(suggestions: list[dict]) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"message": {"content": json.dumps(suggestions)}}
    mock.raise_for_status.return_value = None
    return mock


def test_suggest_returns_suggestions(client_with_data):
    # AIはカテゴリ名のみ返す（keywordなし）
    raw = [
        {"transaction_id": 1, "category": "食費", "confidence": 0.9},
        {"transaction_id": 2, "category": "交通費", "confidence": 0.95},
    ]
    with patch("httpx.post", return_value=_make_llm_response(raw)):
        resp = client_with_data.post("/api/ai/suggest")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["suggested_category_name"] == "食費"
    assert data[0]["suggested_category_id"] is not None
    # キーワードは取引名そのもの
    assert data[0]["suggested_keyword"] == "スーパーマーケット"


def test_suggest_no_unclassified(client):
    """未分類トランザクションがない場合は空リスト"""
    with patch("httpx.post") as mock_post:
        resp = client.post("/api/ai/suggest")
    mock_post.assert_not_called()
    assert resp.status_code == 200
    assert resp.json() == []


def test_apply_classification(client_with_data):
    """分類を適用してトランザクションのcategory_idを更新する"""
    # カテゴリIDを取得
    cats = client_with_data.get("/api/categories").json()
    food_id = next(c["id"] for c in cats if c["name"] == "食費")

    resp = client_with_data.post("/api/ai/apply", json=[
        {"transaction_id": 1, "transaction_type": "bank", "category_id": food_id, "create_rule": False}
    ])
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"] == 1
    assert data["rules_created"] == 0


def test_apply_creates_rule(client_with_data):
    """create_rule=TrueでキーワードルールとcategoryIDの更新を行う"""
    cats = client_with_data.get("/api/categories").json()
    food_id = next(c["id"] for c in cats if c["name"] == "食費")

    resp = client_with_data.post("/api/ai/apply", json=[
        {
            "transaction_id": 1,
            "transaction_type": "bank",
            "category_id": food_id,
            "create_rule": True,
            "keyword": "スーパーマーケット",
            "rule_target": "both",
        }
    ])
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"] == 1
    assert data["rules_created"] == 1

    rules = client_with_data.get("/api/categories/rules").json()
    assert any(r["keyword"] == "スーパーマーケット" for r in rules)


def test_apply_creates_new_category(client_with_data):
    """category_id=Noneでcategory_nameを渡すと新規カテゴリが作成される"""
    resp = client_with_data.post("/api/ai/apply", json=[
        {
            "transaction_id": 1,
            "transaction_type": "bank",
            "category_id": None,
            "category_name": "日用品",
            "category_type": "expense",
            "create_rule": False,
        }
    ])
    assert resp.status_code == 200
    assert resp.json()["applied"] == 1

    # 新カテゴリが作成されていること
    cats = client_with_data.get("/api/categories").json()
    assert any(c["name"] == "日用品" for c in cats)
