"""Ollamaプロバイダーの単体テスト（httpxをモック）"""
import json
import pytest
from unittest.mock import MagicMock, patch

from pinance.llm.base import ClassificationTarget
from pinance.llm.ollama import OllamaProvider


CATEGORIES = ["食費", "交通費", "娯楽", "光熱費"]


def _make_response(suggestions: list[dict]) -> MagicMock:
    """httpx.post のモックレスポンスを作成"""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"message": {"content": json.dumps(suggestions)}}
    mock.raise_for_status.return_value = None
    return mock


def _make_targets() -> list[ClassificationTarget]:
    return [
        ClassificationTarget(1, "bank", "スーパーマーケット", 3000),
        ClassificationTarget(2, "card", "JR東日本", 500),
    ]


def test_classify_returns_suggestions():
    """AIがカテゴリ名を自由提案し、キーワードは取引名から自動設定される"""
    provider = OllamaProvider(model="gemma3:4b-it-qat", base_url="http://localhost:11434")
    # AIはカテゴリ名だけ返す（keywordフィールドなし）
    raw = [
        {"transaction_id": 1, "category": "食費", "confidence": 0.9},
        {"transaction_id": 2, "category": "交通費", "confidence": 0.95},
    ]
    with patch("httpx.post", return_value=_make_response(raw)):
        results = provider.classify(_make_targets(), CATEGORIES)

    assert len(results) == 2
    assert results[0].transaction_id == 1
    assert results[0].suggested_category_name == "食費"
    # キーワードは取引名そのもの（AIによる言い換えなし）
    assert results[0].suggested_keyword == "スーパーマーケット"
    assert results[0].confidence == pytest.approx(0.9)

    assert results[1].transaction_id == 2
    assert results[1].suggested_category_name == "交通費"
    assert results[1].suggested_keyword == "JR東日本"


def test_classify_free_form_category():
    """既存カテゴリに縛られず自由なカテゴリ名を提案できる"""
    provider = OllamaProvider(model="gemma3:4b-it-qat", base_url="http://localhost:11434")
    raw = [
        {"transaction_id": 1, "category": "日用品", "confidence": 0.85},
        {"transaction_id": 2, "category": "交通費", "confidence": 0.9},
    ]
    with patch("httpx.post", return_value=_make_response(raw)):
        results = provider.classify(_make_targets(), CATEGORIES)

    # 「日用品」はCATEGORIESに存在しないが、そのまま提案として返る
    assert results[0].suggested_category_name == "日用品"
    assert results[1].suggested_category_name == "交通費"


def test_classify_handles_malformed_json():
    """LLMがJSONパースできない応答を返した場合はすべてNoneにする"""
    provider = OllamaProvider(model="gemma3:4b-it-qat", base_url="http://localhost:11434")
    bad_mock = MagicMock()
    bad_mock.status_code = 200
    bad_mock.json.return_value = {"message": {"content": "これはJSONではありません"}}
    bad_mock.raise_for_status.return_value = None

    with patch("httpx.post", return_value=bad_mock):
        results = provider.classify(_make_targets(), CATEGORIES)

    assert len(results) == 2
    for r in results:
        assert r.suggested_category_name is None
        assert r.suggested_keyword is None
        assert r.confidence == 0.0


def test_classify_handles_markdown_codeblock():
    """LLMがMarkdownコードブロックでJSONを返した場合も正しくパースする"""
    provider = OllamaProvider(model="gemma3:4b-it-qat", base_url="http://localhost:11434")
    content = "```json\n[{\"transaction_id\": 1, \"category\": \"食費\", \"confidence\": 0.9}, {\"transaction_id\": 2, \"category\": \"交通費\", \"confidence\": 0.95}]\n```\n"
    bad_mock = MagicMock()
    bad_mock.status_code = 200
    bad_mock.json.return_value = {"message": {"content": content}}
    bad_mock.raise_for_status.return_value = None

    with patch("httpx.post", return_value=bad_mock):
        results = provider.classify(_make_targets(), CATEGORIES)

    assert len(results) == 2
    assert results[0].suggested_category_name == "食費"
    assert results[1].suggested_category_name == "交通費"


def test_classify_empty_targets():
    provider = OllamaProvider(model="llama3.2", base_url="http://localhost:11434")
    with patch("httpx.post") as mock_post:
        results = provider.classify([], CATEGORIES)
    mock_post.assert_not_called()
    assert results == []
