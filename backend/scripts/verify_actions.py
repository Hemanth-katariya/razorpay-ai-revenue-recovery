"""Runs the product-spec.md §4.1 capability verification spike.

Makes one real Razorpay Test Mode call for an `API_ASSUMED` action using
the exact same `app.razorpay_client` functions the Executor calls at
runtime -- not a hand-rolled request -- so "verified" means "the code
path that will actually run was exercised for real," not "we believe
the docs." Prints exactly what Razorpay returned. Only writes
`actions.status = API_VERIFIED` when you pass --promote AND the call
actually succeeded; a failed or errored call is reported and the row is
left untouched (or demoted with --demote-on-failure), never silently
marked verified. This is the only script, besides scripts/seed_actions.py,
allowed to write Action.status (architecture.md §6).

Requires RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET (Test Mode keys only --
see .env.example) to be set before running.

Usage:
    # Discovery: list a few existing Test Mode invoices to find a real
    # invoice_id to test the resend-notification action against.
    python -m scripts.verify_actions invoice --list

    # Verify "create a Payment Link + notify" end-to-end (self-contained,
    # no pre-existing Razorpay object needed).
    python -m scripts.verify_actions payment_link --amount 100 \
        --email test@example.com --contact +919999999999 --promote

    # Verify "resend an invoice reminder" against a real invoice you
    # found via --list (or created in the Razorpay Test Mode dashboard).
    python -m scripts.verify_actions invoice --invoice-id inv_XXXXXXXX --promote

    # Demote to HUMAN_REQUIRED instead of leaving API_ASSUMED if the call
    # fails -- use once you're confident the failure is a real capability
    # gap, not a bad invoice id / transient error.
    python -m scripts.verify_actions invoice --invoice-id inv_XXXXXXXX --demote-on-failure
"""
from __future__ import annotations

import argparse
import json
import sys

from app.actions import registry
from app.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from app.core.clock import now_iso
from app.db.models import Action
from app.db.session import SessionLocal, init_db
from app.razorpay_client import client as razorpay_client


def _require_keys() -> None:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        print(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set. Copy backend/.env.example "
            "to backend/.env, fill in Test Mode keys from the Razorpay Dashboard "
            "(Test Mode toggle, top-right -> Settings -> API Keys), and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)


def _print_result(label: str, result: razorpay_client.RazorpayCallResult) -> None:
    print(f"\n--- {label} ---")
    print("ok:", result.ok)
    if result.response is not None:
        print("response:", json.dumps(result.response, indent=2, default=str))
    if result.error_message:
        print("error:", result.error_message)


def _promote_or_report(
    action_id: str,
    *,
    succeeded: bool,
    notes: str,
    promote: bool,
    demote_on_failure: bool,
) -> None:
    db = SessionLocal()
    try:
        action = registry.get_action(db, action_id)
        if action is None:
            print(f"\nNo actions row with id={action_id!r} -- run `python -m scripts.seed_actions` first.")
            return

        if succeeded and promote:
            action.status = "API_VERIFIED"
            action.verified_at = now_iso()
            action.verification_notes = notes
            db.add(action)
            db.commit()
            print(f"\nPromoted {action_id!r} -> API_VERIFIED. verification_notes recorded.")
        elif succeeded:
            print(f"\nCall succeeded. Re-run with --promote to flip {action_id!r} to API_VERIFIED.")
            print(f"Would record verification_notes: {notes}")
        elif demote_on_failure:
            action.status = "HUMAN_REQUIRED"
            action.verified_at = None
            action.verification_notes = notes
            db.add(action)
            db.commit()
            print(f"\nCall failed. Demoted {action_id!r} -> HUMAN_REQUIRED (not simulated, not left as an untested assumption).")
        else:
            print(f"\nCall failed. {action_id!r} left as-is ({action.status}). Re-run with --demote-on-failure "
                  "once you're confident this is a real capability gap, not a transient/bad-input error.")
    finally:
        db.close()


def verify_payment_link(args: argparse.Namespace) -> None:
    create_result = razorpay_client.create_payment_link(
        amount=args.amount,
        currency="INR",
        description="RecoverFlow capability verification spike -- safe to ignore/expire",
        customer={"name": "Spike Test Customer", "email": args.email, "contact": args.contact},
    )
    _print_result("create_payment_link", create_result)

    notify_result = None
    if create_result.ok:
        link_id = (create_result.response or {}).get("id")
        if link_id:
            notify_result = razorpay_client.send_payment_link_notification(link_id)
            _print_result("send_payment_link_notification", notify_result)
        else:
            print("\ncreate_payment_link succeeded but no 'id' in the response -- cannot test notify.")

    succeeded = bool(create_result.ok and notify_result is not None and notify_result.ok)
    notes = (
        f"Spike run {now_iso()}: create_payment_link "
        f"{'succeeded' if create_result.ok else 'FAILED: ' + str(create_result.error_message)}; "
        f"send_payment_link_notification "
        f"{'succeeded' if (notify_result and notify_result.ok) else 'FAILED: ' + str(notify_result.error_message if notify_result else 'not attempted')}."
    )
    _promote_or_report(
        "create_payment_link_and_notify", succeeded=succeeded, notes=notes,
        promote=args.promote, demote_on_failure=args.demote_on_failure,
    )


def verify_invoice(args: argparse.Namespace) -> None:
    if args.list:
        import razorpay as razorpay_sdk

        raw_client = razorpay_sdk.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        invoices = raw_client.invoice.all({"count": args.list_count})
        print(json.dumps(invoices, indent=2, default=str))
        print(
            "\nPick an 'id' (e.g. inv_XXXXXXXX) with status 'issued'/'partially_paid' above and re-run with "
            "--invoice-id <id>. If this list is empty, create a subscription/invoice in Test Mode first "
            "(Dashboard, or POST /v1/subscriptions) -- there is nothing to resend a reminder for otherwise."
        )
        return

    if not args.invoice_id:
        print("Pass --invoice-id inv_XXXXXXXX (use --list to find one), or --list to discover one first.", file=sys.stderr)
        sys.exit(1)

    result = razorpay_client.resend_invoice_notification(args.invoice_id, medium=args.medium)
    _print_result("resend_invoice_notification", result)

    notes = (
        f"Spike run {now_iso()}: resend_invoice_notification(invoice_id={args.invoice_id!r}, medium={args.medium!r}) "
        f"{'succeeded' if result.ok else 'FAILED: ' + str(result.error_message)}."
    )
    _promote_or_report(
        "resend_invoice_reminder", succeeded=result.ok, notes=notes,
        promote=args.promote, demote_on_failure=args.demote_on_failure,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)

    pl = sub.add_parser("payment_link", help="Verify create_payment_link_and_notify")
    pl.add_argument("--amount", type=int, default=100, help="paise (default: 100 = INR 1.00)")
    pl.add_argument("--email", default="spike-test@example.com")
    pl.add_argument("--contact", default="+919999999999")
    pl.add_argument("--promote", action="store_true")
    pl.add_argument("--demote-on-failure", action="store_true")
    pl.set_defaults(func=verify_payment_link)

    inv = sub.add_parser("invoice", help="Verify resend_invoice_reminder")
    inv.add_argument("--invoice-id", default=None)
    inv.add_argument("--medium", default="email", choices=["email", "sms"])
    inv.add_argument("--list", action="store_true", help="List existing Test Mode invoices instead of calling notify")
    inv.add_argument("--list-count", type=int, default=10)
    inv.add_argument("--promote", action="store_true")
    inv.add_argument("--demote-on-failure", action="store_true")
    inv.set_defaults(func=verify_invoice)

    args = parser.parse_args()
    _require_keys()
    init_db()
    args.func(args)


if __name__ == "__main__":
    main()
