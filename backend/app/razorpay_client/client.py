"""The outbound Razorpay boundary (architecture.md §7).

This is the ONLY module in the codebase allowed to make an HTTP call to
Razorpay. It exposes exactly the methods the action registry references
-- no general-purpose SDK wrapper with unused methods. Every call runs
against Test Mode keys only; there is no production credential path
here.

CRITICAL: per docs/recovery-feasibility.md, the exact endpoint/params for
resend_invoice_notification and the payment-link notify call are marked
UNCERTAIN (the dedicated Razorpay doc pages 404'd during that research).
The implementations below are a best-effort call shape based on
Razorpay's documented notify-by-medium pattern used elsewhere in their
API, but they are NOT confirmed. They must not be treated as
API_VERIFIED until the product-spec.md §4.1 capability spike makes a
real Test Mode call and records the observed behavior in
actions.verification_notes (see scripts/seed_actions.py). This module
never catches an error and reports a fake success -- a failed or
unverified call surfaces to the Executor as such.
"""
from __future__ import annotations

from dataclasses import dataclass

import razorpay

from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET


class RazorpayNotConfigured(Exception):
    """Raised when Test Mode credentials are missing. Never silently
    proceeds -- a missing credential is a hard failure, not a fake
    success."""


@dataclass
class RazorpayCallResult:
    ok: bool
    response: dict | None = None
    error_message: str | None = None


_client: razorpay.Client | None = None


def _get_client() -> razorpay.Client:
    global _client
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise RazorpayNotConfigured(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set. Set Test Mode keys before "
            "calling any razorpay_client method."
        )
    if _client is None:
        _client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    return _client


def _safe_call(fn) -> RazorpayCallResult:
    try:
        result = fn()
        return RazorpayCallResult(ok=True, response=result)
    except RazorpayNotConfigured:
        raise
    except Exception as exc:  # razorpay.errors.* or network errors
        return RazorpayCallResult(ok=False, error_message=str(exc))


def get_subscription(subscription_id: str) -> RazorpayCallResult:
    """GET Subscription by ID. Documented endpoint (recovery-feasibility.md,
    API_EXECUTABLE); used by the Outcome Observer / demo read endpoints,
    never by the execution path."""
    client = _get_client()
    return _safe_call(lambda: client.subscription.fetch(subscription_id))


def get_invoices_for_subscription(subscription_id: str) -> RazorpayCallResult:
    """GET invoices filtered by subscription_id. Documented endpoint
    existence (recovery-feasibility.md); parameter-level detail was
    UNCERTAIN in that research, this uses the standard Invoice API list
    filter."""
    client = _get_client()
    return _safe_call(lambda: client.invoice.all({"subscription_id": subscription_id}))


def resend_invoice_notification(invoice_id: str, medium: str = "email") -> RazorpayCallResult:
    """UNVERIFIED (API_ASSUMED, see module docstring). Best-effort shape:
    Razorpay's Invoice API 'Send Notifications' action, called by analogy
    to the documented notify-by-medium pattern. Requires the §4.1 spike
    before actions.status may become API_VERIFIED for this action."""
    client = _get_client()
    return _safe_call(lambda: client.invoice.notify_by(invoice_id, medium))


def create_payment_link(*, amount: int, currency: str, description: str, customer: dict) -> RazorpayCallResult:
    """Create Standard Payment Link (POST) -- HTTP method confirmed in
    recovery-feasibility.md; exact required params UNCERTAIN, this uses
    the SDK's documented standard fields (amount in paise, currency,
    description, customer)."""
    client = _get_client()
    payload = {
        "amount": amount,
        "currency": currency,
        "description": description,
        "customer": customer,
        "notify": {"sms": True, "email": True},
        "reminder_enable": True,
    }
    return _safe_call(lambda: client.payment_link.create(payload))


def send_payment_link_notification(payment_link_id: str, medium: str = "email") -> RazorpayCallResult:
    """UNVERIFIED (API_ASSUMED, see module docstring). Best-effort shape:
    Payment Links 'Send or Resend Notifications' action, called by
    analogy to the invoice notify-by-medium pattern."""
    client = _get_client()
    return _safe_call(lambda: client.payment_link.notifyBy(payment_link_id, medium))
