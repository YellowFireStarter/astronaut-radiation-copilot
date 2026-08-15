"""Radiation Copilot — FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name,
        version=s.version,
        description="AI copilot for astronaut radiation exposure — sense, assess, advise.",
    )
    origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get(s.route_root)
    async def root():
        return {"app": s.app_name, "docs": "/docs", "health": s.route_health}

    return app


app = create_app()
