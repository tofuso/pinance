import traceback
from fastapi import APIRouter, HTTPException
from pinance.database import get_connection
from pinance.llm.base import ClassificationTarget
from pinance.llm.factory import create_provider
from pinance.models import AiClassificationSuggestion, AiClassificationApply, AiClassificationResult


def make_ai_router(db_path: str) -> APIRouter:
    router = APIRouter(prefix="/api/ai", tags=["ai"])

    def _get_llm_settings(conn) -> dict:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    @router.post("/suggest", response_model=list[AiClassificationSuggestion])
    def suggest():
        """未分類のトランザクションをLLMで分類提案する"""
        conn = get_connection(db_path)

        # 設定読み込み
        settings = _get_llm_settings(conn)

        # 既存カテゴリ（name→id のマップ、提案後の照合用）
        cat_rows = conn.execute(
            "SELECT id, name FROM categories WHERE type != 'exclude'"
        ).fetchall()
        categories = {r["name"]: r["id"] for r in cat_rows}
        category_names = list(categories.keys())

        # 未分類の銀行取引
        bank_rows = conn.execute(
            "SELECT id, description, withdrawal FROM bank_transactions WHERE category_id IS NULL"
        ).fetchall()
        # 未分類のカード取引
        card_rows = conn.execute(
            "SELECT id, merchant, amount FROM card_transactions WHERE category_id IS NULL"
        ).fetchall()

        targets: list[ClassificationTarget] = []
        for r in bank_rows:
            targets.append(ClassificationTarget(
                transaction_id=r["id"],
                transaction_type="bank",
                description=r["description"],
                amount=r["withdrawal"],
            ))
        for r in card_rows:
            targets.append(ClassificationTarget(
                transaction_id=r["id"],
                transaction_type="card",
                description=r["merchant"],
                amount=r["amount"],
            ))

        if not targets:
            return []

        # 件数が多い場合は上位50件のみ処理（タイムアウト防止）
        MAX_BATCH = 50
        targets = targets[:MAX_BATCH]

        provider = create_provider(
            provider=settings.get("llm_provider", "ollama"),
            model=settings.get("llm_model", "gemma3:4b-it-qat"),
            base_url=settings.get("llm_base_url", "http://localhost:11434"),
            api_key=settings.get("llm_api_key", ""),
        )
        try:
            suggestions = provider.classify(targets, category_names)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM呼び出しエラー: {e}\n{traceback.format_exc()}")

        result = []
        for s in suggestions:
            # 既存カテゴリと名前が一致すれば ID を付与、なければ None（新規作成候補）
            cat_id = categories.get(s.suggested_category_name) if s.suggested_category_name else None
            result.append(AiClassificationSuggestion(
                transaction_id=s.transaction_id,
                transaction_type=s.transaction_type,
                description=s.description,
                suggested_category_id=cat_id,
                suggested_category_name=s.suggested_category_name,
                suggested_keyword=s.suggested_keyword,
                confidence=s.confidence,
            ))
        return result

    @router.post("/apply", response_model=AiClassificationResult)
    def apply_classification(payload: list[AiClassificationApply]):
        """提案された分類を適用する（カテゴリ未存在なら自動作成、オプションでキーワードルールも作成）"""
        conn = get_connection(db_path)
        applied = 0
        rules_created = 0
        # カテゴリ名→ID のキャッシュ（このリクエスト内で再利用）
        cat_cache: dict[str, int] = {}

        for item in payload:
            cat_id = item.category_id

            # category_id が未指定の場合は category_name から取得または作成
            if cat_id is None and item.category_name:
                name = item.category_name.strip()
                if name in cat_cache:
                    cat_id = cat_cache[name]
                else:
                    row = conn.execute(
                        "SELECT id FROM categories WHERE name = ?", [name]
                    ).fetchone()
                    if row:
                        cat_id = row["id"]
                    else:
                        cur = conn.execute(
                            "INSERT INTO categories (name, type) VALUES (?, ?)",
                            [name, item.category_type],
                        )
                        cat_id = cur.lastrowid
                    cat_cache[name] = cat_id

            if cat_id is None:
                continue  # カテゴリが特定できない場合はスキップ

            table = "bank_transactions" if item.transaction_type == "bank" else "card_transactions"
            conn.execute(
                f"UPDATE {table} SET category_id = ? WHERE id = ?",
                [cat_id, item.transaction_id],
            )
            applied += 1

            if item.create_rule and item.keyword:
                try:
                    conn.execute(
                        "INSERT INTO category_rules (keyword, category_id, target) VALUES (?, ?, ?)",
                        [item.keyword, cat_id, item.rule_target],
                    )
                    rules_created += 1
                except Exception:
                    pass  # UNIQUE制約違反などは無視

        conn.commit()
        return AiClassificationResult(applied=applied, rules_created=rules_created)

    return router
