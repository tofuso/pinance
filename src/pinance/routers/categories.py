import sqlite3
from fastapi import APIRouter, HTTPException
from pinance.models import Category, CategoryCreate, CategoryRule, CategoryRuleCreate


def make_categories_router(db_path: str):
    router = APIRouter(prefix="/api/categories", tags=["categories"])

    @router.get("", response_model=list[Category])
    def list_categories():
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM categories ORDER BY id ASC").fetchall()
        finally:
            conn.close()
        return [Category(id=r["id"], name=r["name"], type=r["type"]) for r in rows]

    @router.post("", response_model=Category, status_code=201)
    def create_category(payload: CategoryCreate):
        if payload.type not in ("income", "expense", "exclude"):
            raise HTTPException(status_code=400, detail="type は income/expense/exclude のいずれかです")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            cursor = conn.execute(
                "INSERT INTO categories (name, type) VALUES (?, ?)",
                (payload.name, payload.type),
            )
            conn.commit()
            cat_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="カテゴリ名が重複しています")
        finally:
            conn.close()
        return Category(id=cat_id, name=payload.name, type=payload.type)

    @router.put("/{cat_id}", response_model=Category)
    def update_category(cat_id: int, payload: CategoryCreate):
        if payload.type not in ("income", "expense", "exclude"):
            raise HTTPException(status_code=400, detail="type は income/expense/exclude のいずれかです")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        not_found = False
        try:
            cursor = conn.execute(
                "UPDATE categories SET name = ?, type = ? WHERE id = ?",
                (payload.name, payload.type, cat_id),
            )
            if cursor.rowcount == 0:
                not_found = True
            else:
                conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="カテゴリ名が重複しています")
        finally:
            conn.close()
        if not_found:
            raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
        return Category(id=cat_id, name=payload.name, type=payload.type)

    @router.delete("/{cat_id}")
    def delete_category(cat_id: int):
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        not_found = False
        try:
            conn.execute("UPDATE bank_transactions SET category_id = NULL WHERE category_id = ?", [cat_id])
            conn.execute("UPDATE card_transactions SET category_id = NULL WHERE category_id = ?", [cat_id])
            cursor = conn.execute("DELETE FROM categories WHERE id = ?", [cat_id])
            if cursor.rowcount == 0:
                not_found = True
            else:
                conn.commit()
        finally:
            conn.close()
        if not_found:
            raise HTTPException(status_code=404, detail="カテゴリが見つかりません")
        return {"deleted": 1}

    @router.get("/rules", response_model=list[CategoryRule])
    def list_rules():
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT cr.*, c.name AS category_name
                   FROM category_rules cr
                   JOIN categories c ON cr.category_id = c.id
                   ORDER BY cr.id ASC"""
            ).fetchall()
        finally:
            conn.close()
        return [
            CategoryRule(
                id=r["id"], keyword=r["keyword"],
                category_id=r["category_id"], category_name=r["category_name"],
                target=r["target"],
            )
            for r in rows
        ]

    @router.post("/rules", response_model=CategoryRule, status_code=201)
    def create_rule(payload: CategoryRuleCreate):
        if payload.target not in ("bank", "card", "both"):
            raise HTTPException(status_code=400, detail="target は bank/card/both のいずれかです")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        rule_id = None
        category_name = None
        try:
            cat = conn.execute(
                "SELECT name FROM categories WHERE id = ?", [payload.category_id]
            ).fetchone()
            cursor = conn.execute(
                "INSERT INTO category_rules (keyword, category_id, target) VALUES (?, ?, ?)",
                (payload.keyword, payload.category_id, payload.target),
            )
            conn.commit()
            rule_id = cursor.lastrowid
            category_name = cat["name"] if cat else None
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="同じキーワードと対象の組み合わせが既に存在します")
        finally:
            conn.close()
        return CategoryRule(
            id=rule_id, keyword=payload.keyword,
            category_id=payload.category_id,
            category_name=category_name,
            target=payload.target,
        )

    @router.delete("/rules/{rule_id}")
    def delete_rule(rule_id: int):
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            cursor = conn.execute("DELETE FROM category_rules WHERE id = ?", [rule_id])
            conn.commit()
        finally:
            conn.close()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="ルールが見つかりません")
        return {"deleted": 1}

    return router
