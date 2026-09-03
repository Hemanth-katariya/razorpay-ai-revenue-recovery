"""Posts a synthetic_data file through /webhooks in order (architecture.md §13).

Signs each event with RAZORPAY_WEBHOOK_SECRET exactly as Razorpay signs a
real webhook (HMAC-SHA256 over the raw body) -- this is a real signature
check on the receiving end, not a bypassed one, even though the sender
here is our own replay tool.

Usage:
    python -m scripts.replay_batch synthetic_data/events_batch_01.json \
        --label "demo batch 1" --exposure-cap 100000000
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys

import requests

from app.config import RAZORPAY_WEBHOOK_SECRET


def sign(body: bytes) -> str:
    return hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def replay(events_path: str, base_url: str, label: str, exposure_cap: int) -> None:
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)

    batch_resp = requests.post(
        f"{base_url}/batches",
        json={"label": label, "exposure_cap_total": exposure_cap},
        timeout=30,
    )
    batch_resp.raise_for_status()
    batch_run_id = batch_resp.json()["id"]
    print(f"created batch_run_id={batch_run_id}")

    last_simulated_at = None
    for event in events:
        body = json.dumps(event).encode("utf-8")
        signature = sign(body)
        resp = requests.post(
            f"{base_url}/webhooks/razorpay",
            params={"batch_run_id": batch_run_id},
            data=body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
            # Longer than the other calls in this script -- each webhook may
            # block on a real Gemini call, which can be slow under upstream
            # rate limiting/high demand (observed 503s taking 60s+ to
            # surface from the SDK's own internal retries).
            timeout=120,
        )
        last_simulated_at = event.get("created_at", last_simulated_at)
        print(f"POST id={event['id']} event={event['event']} -> {resp.status_code} {resp.json()}")

    close_resp = requests.post(
        f"{base_url}/batches/{batch_run_id}/close",
        json={"simulated_at": last_simulated_at},
        timeout=30,
    )
    close_resp.raise_for_status()
    print("batch closed:", close_resp.json())

    metrics_resp = requests.get(f"{base_url}/batches/{batch_run_id}/metrics", timeout=30)
    metrics_resp.raise_for_status()
    print(json.dumps(metrics_resp.json(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events_file")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--label", default="synthetic batch")
    parser.add_argument("--exposure-cap", type=int, default=100_000_000, help="paise")
    args = parser.parse_args()

    try:
        replay(args.events_file, args.base_url, args.label, args.exposure_cap)
    except requests.ConnectionError:
        print(f"could not reach {args.base_url} -- is `uvicorn app.main:app` running?", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
