"""FastAPI app + route registration (architecture.md §12, §13)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import batches, escalations, subscriptions, webhooks
from app.db.session import init_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # Idempotent: only inserts actions rows that don't exist yet. A human
    # re-runs `python -m scripts.seed_actions` after the §4.1 verification
    # spike to promote a row's status -- this call never overwrites that.
    from scripts.seed_actions import seed

    seed()
    yield


app = FastAPI(title="RecoverFlow -- AI Revenue Recovery Orchestrator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(batches.router)
app.include_router(subscriptions.router)
app.include_router(escalations.router)


@app.get("/health")
def health():
    return {"status": "ok"}
