import json
import re
import httpx

from pinance.llm.base import LlmProvider, ClassificationTarget, ClassificationSuggestion


def _parse_json_content(content: str) -> list[dict] | None:
    """LLMの応答文字列からJSON配列を抽出してパースする。
    Markdownコードブロック（```json ... ```）も処理する。
    """
    # コードブロックを取り除く
    stripped = re.sub(r"```(?:json)?\s*", "", content).strip()
    # まず全体をパース試行
    try:
        result = json.loads(stripped)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # [ ... ] の範囲を探して部分パース
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(stripped[start:end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    return None

_SYSTEM_PROMPT = """\
あなたは家計簿の取引を分類するAIアシスタントです。
各取引に対して、家計簿として適切な日本語のカテゴリ名を提案してください。

カテゴリ名の例: 食費, 外食, 交通費, 光熱費, 通信費, 娯楽, 日用品, 医療費, 保険, 給与, 副収入

必ず以下のJSON配列形式のみで回答してください（説明文・コードブロック不要）:
[
  {
    "transaction_id": <整数>,
    "category": "<カテゴリ名>",
    "confidence": <0.0〜1.0の数値>
  },
  ...
]

分類できない場合は category を null にしてください。
"""


_CHUNK_SIZE = 10  # 1リクエストあたりの最大件数


class OllamaProvider(LlmProvider):
    def __init__(self, model: str, base_url: str, timeout: float = 120.0):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def classify(
        self,
        targets: list[ClassificationTarget],
        category_names: list[str],
    ) -> list[ClassificationSuggestion]:
        if not targets:
            return []

        # チャンク分割して複数リクエストに分ける
        results: list[ClassificationSuggestion] = []
        for i in range(0, len(targets), _CHUNK_SIZE):
            chunk = targets[i:i + _CHUNK_SIZE]
            user_content = self._build_user_content(chunk, category_names)
            raw = self._call_ollama(user_content)
            if raw is None:
                results.extend(self._fallback_suggestions(chunk))
            else:
                results.extend(self._parse_suggestions(chunk, category_names, raw))
        return results

    # ------------------------------------------------------------------

    def _build_user_content(
        self,
        targets: list[ClassificationTarget],
        category_names: list[str],
    ) -> str:
        lines = ["取引リスト:"]
        for t in targets:
            lines.append(
                f"- id={t.transaction_id} description={t.description!r} amount={t.amount}"
            )
        return "\n".join(lines)

    def _call_ollama(self, user_content: str) -> list[dict] | None:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        resp = httpx.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return _parse_json_content(content)

    def _parse_suggestions(
        self,
        targets: list[ClassificationTarget],
        category_names: list[str],
        raw: list[dict],
    ) -> list[ClassificationSuggestion]:
        # id -> raw dict
        raw_by_id: dict[int, dict] = {r["transaction_id"]: r for r in raw if isinstance(r, dict)}

        results = []
        for t in targets:
            r = raw_by_id.get(t.transaction_id, {})
            category = r.get("category") or None
            # キーワードはAIに聞かず取引名をそのまま使う
            results.append(ClassificationSuggestion(
                transaction_id=t.transaction_id,
                transaction_type=t.transaction_type,
                description=t.description,
                suggested_category_name=category,
                suggested_keyword=t.description if category else None,
                confidence=float(r.get("confidence", 0.0)) if category else 0.0,
            ))
        return results

    def _fallback_suggestions(self, targets: list[ClassificationTarget]) -> list[ClassificationSuggestion]:
        return [
            ClassificationSuggestion(
                transaction_id=t.transaction_id,
                transaction_type=t.transaction_type,
                description=t.description,
                suggested_category_name=None,
                suggested_keyword=None,
                confidence=0.0,
            )
            for t in targets
        ]
