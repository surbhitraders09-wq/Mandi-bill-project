"""
FastAPI application entrypoint.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import automation, bills, history, logs, settings

from app.api.routes.ai import router as ai_router
from app.config import settings as app_settings
from app.database import init_db
from app.domain.audit.router import router as audit_router
from app.domain.auth.router import router as auth_router
from app.domain.commodities.router import router as commodities_router
from app.domain.farmers.router import router as farmers_router
from app.domain.search.router import router as search_router
from app.domain.stock.router import router as stock_router
from app.domain.traders.router import router as traders_router
from app.domain.villages.router import router as villages_router
from app.exceptions import AppError
from app.seed import seed_defaults

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_defaults()
    yield


app = FastAPI(
    title="Mandi Automation Assistant",
    description="Automates e-Mandi trader portal bill search, analysis and printing.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = logging.getLogger(__name__)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"message": f"Internal server error: {exc}"}},
    )


@app.get("/api/health", tags=["system"])
async def health() -> Dict[str, Any]:
    return {"status": "ok", "version": "1.0.0"}


app.include_router(automation.router)
app.include_router(ai_router)
app.include_router(bills.router)
app.include_router(settings.router)
app.include_router(history.router)
app.include_router(logs.router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(search_router)
app.include_router(villages_router)
app.include_router(commodities_router)
app.include_router(farmers_router)
app.include_router(traders_router)
app.include_router(stock_router)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _serve_frontend(path: str) -> FileResponse:
    candidate = (FRONTEND_DIST / path).resolve()
    if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
        return FileResponse(candidate)
    return FileResponse(FRONTEND_DIST / "index.html")


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def frontend_spa(request: Request, path: str) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    return _serve_frontend(path)
