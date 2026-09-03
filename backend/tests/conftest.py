import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch):
    """Tests must never depend on whether the developer's local .env has a
    real GEMINI_API_KEY -- that's environment state, not test setup. Forcing
    it unset here makes app.ai.diagnosis._get_client() fail fast (the same
    behavior as a missing key), which diagnose()'s try/except turns into a
    graceful schema_invalid escalation, never a real network call.

    Both the module-level name (read at diagnosis.py import time) and the
    actual OS env var must be cleared -- google-genai's Client falls back to
    reading GEMINI_API_KEY/GOOGLE_API_KEY from os.environ directly when no
    api_key is passed, so clearing only the Python-level name still let a
    real call through when a real key was present in .env."""
    monkeypatch.setattr("app.ai.diagnosis.GEMINI_API_KEY", None, raising=False)
    monkeypatch.setattr("app.ai.diagnosis._client", None, raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
