import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pinance.database import init_db, DEFAULT_DB_PATH
from pinance.routers.bank import make_bank_router
from pinance.routers.card import make_card_router
from pinance.routers.categories import make_categories_router
from pinance.routers.analytics import make_analytics_router


def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    init_db(db_path)
    app = FastAPI(title="Pinance")
    app.include_router(make_bank_router(db_path))
    app.include_router(make_card_router(db_path))
    app.include_router(make_categories_router(db_path))
    app.include_router(make_analytics_router(db_path))

    static_dir = os.path.join(os.path.dirname(__file__), "static")

    @app.get("/static/{filename:path}")
    def static_files(filename: str):
        file_path = os.path.join(static_dir, filename)
        if not os.path.isfile(file_path):
            return Response(status_code=404)
        resp = FileResponse(file_path)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.get("/")
    def root():
        resp = FileResponse(os.path.join(static_dir, "index.html"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    return app


app = create_app()
