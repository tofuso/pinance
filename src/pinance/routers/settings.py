from fastapi import APIRouter
from pinance.database import get_connection
from pinance.models import LlmSettings, LlmSettingsPatch


def make_settings_router(db_path: str) -> APIRouter:
    router = APIRouter(prefix="/api/settings", tags=["settings"])

    def _read_settings(conn) -> LlmSettings:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        data = {r["key"]: r["value"] for r in rows}
        return LlmSettings(
            llm_provider=data.get("llm_provider", "ollama"),
            llm_model=data.get("llm_model", "gemma3:4b-it-qat"),
            llm_base_url=data.get("llm_base_url", "http://localhost:11434"),
            llm_api_key=data.get("llm_api_key", ""),
        )

    @router.get("", response_model=LlmSettings)
    def get_settings():
        conn = get_connection(db_path)
        return _read_settings(conn)

    @router.patch("", response_model=LlmSettings)
    def patch_settings(payload: LlmSettingsPatch):
        updates = payload.model_dump(exclude_none=True)
        conn = get_connection(db_path)
        for key, value in updates.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [key, value],
            )
        conn.commit()
        return _read_settings(conn)

    return router
