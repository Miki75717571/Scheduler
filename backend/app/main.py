import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import (
    assignments,
    auth,
    availability,
    health,
    invitations,
    periods,
    rules,
    scores,
    shift_types,
    users,
)
from app.core.config import describe_database, settings
from app.db.session import engine

# Without this, logger.info(...) calls anywhere in the app (e.g. the console
# email provider printing invite links - app/services/email_service.py) are
# silently dropped: Python's root logger defaults to WARNING with no handler,
# and neither FastAPI nor Uvicorn configures one for anything outside its own
# "uvicorn.*" loggers.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    target = describe_database(settings.async_database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"[startup] FAILED to connect to database ({target}): {exc}", file=sys.stderr)
        raise
    print(f"[startup] connected to database: {target}")
    yield


app = FastAPI(title="Cafeteria Scheduler API", lifespan=lifespan)

# Phone/LAN access goes through the Vite dev proxy (frontend/vite.config.ts),
# not directly to this process - uvicorn stays bound to 127.0.0.1 (see
# start.ps1). The browser's requests are same-origin as far as it's
# concerned, so CORS is never actually exercised in that path; this list only
# matters for a browser hitting the API directly (e.g. a separately-deployed
# frontend in production, or manual testing against :8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "message_key": "validation.error",
                "params": {"errors": jsonable_encoder(exc.errors())},
            }
        },
    )


API_V1_PREFIX = "/api/v1"
app.include_router(health.router, prefix=API_V1_PREFIX)
app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(users.router, prefix=API_V1_PREFIX)
app.include_router(invitations.router, prefix=API_V1_PREFIX)
app.include_router(shift_types.router, prefix=API_V1_PREFIX)
app.include_router(periods.router, prefix=API_V1_PREFIX)
app.include_router(availability.router, prefix=API_V1_PREFIX)
app.include_router(rules.router, prefix=API_V1_PREFIX)
app.include_router(assignments.router, prefix=API_V1_PREFIX)
app.include_router(scores.router, prefix=API_V1_PREFIX)
