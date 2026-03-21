def fetch_rules(conn) -> list[dict]:
    """DB から category_rules を全件取得して辞書のリストで返す"""
    rows = conn.execute(
        "SELECT id, keyword, category_id, target FROM category_rules ORDER BY id ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def classify_text(text: str, rules: list[dict], target: str) -> int | None:
    """text に最初にマッチしたルール（id昇順）の category_id を返す。マッチなしは None"""
    for rule in rules:
        if rule["target"] in (target, "both") and rule["keyword"] in text:
            return rule["category_id"]
    return None
