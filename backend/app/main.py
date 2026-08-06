from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.database import create_db_and_tables, seed_demo_data
from app.core.storage import ensure_storage_dirs


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Self-hostable LC-MS/MS processing and annotation platform MVP.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    # Ensure tables exist at import/app creation so module-level TestClient
    # usage and fresh deployments both have a ready schema.
    ensure_storage_dirs()
    create_db_and_tables()

    @app.on_event("startup")
    def startup() -> None:
        seed_demo_data()

    return app


app = create_app()
