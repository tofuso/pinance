import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pinance.database import init_db, DEFAULT_DB_PATH
from pinance.routers.bank import make_bank_router
from pinance.routers.card import make_card_router
from pinance.routers.categories import make_categories_router


def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    init_db(db_path)
    app = FastAPI(title="Pinance")
    app.include_router(make_bank_router(db_path))
    app.include_router(make_card_router(db_path))
    app.include_router(make_categories_router(db_path))

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(static_dir, "index.html"))

    return app


app = create_app()
