from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import admin as admin_api
from .api import audit as audit_api
from .api import auth as auth_api
from .api import demo as demo_api
from .api import privacy as privacy_api
from .api import reveals as reveals_api
from .core.logging_filter import install_redaction

install_redaction()

app = FastAPI(title="APAAR Sathi", version="2.0")

# CORS: localhost for dev + any origins from CORS_ORIGINS (comma-separated) for the deployed frontend.
import os

_origins = ["http://localhost:5173", "http://localhost:4173"]
_origins += [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
_origin_regex = os.environ.get("CORS_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(detail), "details": {}}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "Invalid request", "details": {"errors": exc.errors()}}},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_api.router)
app.include_router(audit_api.router)
app.include_router(reveals_api.router)
app.include_router(privacy_api.router)
app.include_router(demo_api.router)
app.include_router(admin_api.router)
