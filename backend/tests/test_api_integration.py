"""Integration-level regression tests for the FastAPI app, covering a bug
found during manual smoke testing: resolving an escalation whose
subscription had already been force-closed by batch-close used to crash
with an unhandled 500 (state_machine.IllegalTransition), instead of a
clean conflict response.
"""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import RAZORPAY_WEBHOOK_SECRET
from app.db.models import Base
from app.db.session import get_db
from app.main import app
from scripts.seed_actions import SEED_ACTIONS
from app.db.models import Action


@pytest.fixture()
def client():
    # StaticPool: FastAPI runs sync routes in a thread pool, so a plain
    # SQLite in-memory engine (SingletonThreadPool, one connection per
    # thread) would hand different requests different, empty databases.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    seed_db = TestSession()
    for row in SEED_ACTIONS:
        seed_db.add(Action(**row, verified_at=None, verification_notes=None))
    seed_db.commit()
    seed_db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _sign(body: bytes) -> str:
    return hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _post_webhook(client, batch_run_id, event):
    body = json.dumps(event).encode()
    return client.post(
        "/webhooks/razorpay",
        params={"batch_run_id": batch_run_id},
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )


def _failure_event(event_id, sub_id):
    return {
        "id": event_id,
        "event": "payment.failed",
        "created_at": "2026-01-01T00:00:00",
        "payload": {
            "subscription": {"id": sub_id, "customer_ref": "c", "outstanding_amount": 1000, "invoice_id": "inv_1"},
            "payment": {"error_code": "X", "error_description": "some failure"},
        },
    }


def test_invalid_signature_rejected(client):
    batch = client.post("/batches", json={"label": "b", "exposure_cap_total": 1_000_000}).json()
    body = json.dumps(_failure_event("evt_1", "sub_1")).encode()
    resp = client.post(
        "/webhooks/razorpay", params={"batch_run_id": batch["id"]}, content=body,
        headers={"X-Razorpay-Signature": "deadbeef"},
    )
    assert resp.status_code == 400


def test_duplicate_event_dropped(client):
    batch = client.post("/batches", json={"label": "b", "exposure_cap_total": 1_000_000}).json()
    r1 = _post_webhook(client, batch["id"], _failure_event("evt_1", "sub_1"))
    assert r1.status_code == 200
    assert r1.json()["status"] == "processed"
    r2 = _post_webhook(client, batch["id"], _failure_event("evt_1", "sub_1"))
    assert r2.json()["status"] == "duplicate_dropped"


def test_diagnosis_failure_escalates_not_crashes(client):
    """No ANTHROPIC_API_KEY is configured in the test environment, so the
    Diagnosis Service call fails -- this must escalate gracefully, never
    crash the request (product-spec.md §7)."""
    batch = client.post("/batches", json={"label": "b", "exposure_cap_total": 1_000_000}).json()
    resp = _post_webhook(client, batch["id"], _failure_event("evt_1", "sub_1"))
    assert resp.status_code == 200
    assert resp.json()["resulting_state"] == "ESCALATED"


def test_batch_close_reconciles_open_escalations_and_resolve_returns_409(client):
    batch = client.post("/batches", json={"label": "b", "exposure_cap_total": 1_000_000}).json()
    batch_id = batch["id"]
    _post_webhook(client, batch_id, _failure_event("evt_1", "sub_1"))

    open_escalations = client.get("/escalations", params={"status": "open"}).json()
    assert len(open_escalations) == 1
    escalation_id = open_escalations[0]["id"]

    close_resp = client.post(f"/batches/{batch_id}/close", json={})
    assert close_resp.status_code == 200
    assert close_resp.json()["subscriptions_force_closed"] == 1

    # The escalation must now be auto-resolved, not left dangling as "open"
    # against an already-terminal subscription.
    still_open = client.get("/escalations", params={"status": "open"}).json()
    assert still_open == []

    resolved = client.get("/escalations", params={"status": "resolved"}).json()
    assert len(resolved) == 1
    assert resolved[0]["id"] == escalation_id

    # Attempting to resolve it anyway (e.g. a human was mid-action when the
    # window closed) must be a clean 409, not a 500.
    resolve_resp = client.post(
        f"/escalations/{escalation_id}/resolve", json={"resolution": "recovered"}
    )
    assert resolve_resp.status_code == 409


def test_metrics_reconciliation_sums_to_batch_size(client):
    batch = client.post("/batches", json={"label": "b", "exposure_cap_total": 1_000_000}).json()
    batch_id = batch["id"]
    for i in range(3):
        _post_webhook(client, batch_id, _failure_event(f"evt_{i}", f"sub_{i}"))
    client.post(f"/batches/{batch_id}/close", json={})

    metrics = client.get(f"/batches/{batch_id}/metrics").json()
    recon = metrics["batch_size_reconciliation"]
    assert recon["total"] == 3
    assert recon["total"] == recon["recovered"] + recon["stopped"] + recon["not_recovered"] + recon["still_open"]
