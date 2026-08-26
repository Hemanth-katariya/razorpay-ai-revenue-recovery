"""Thresholds, caps, and retry policy. All env-driven with documented
defaults so a demo run is reproducible without a .env file.

Amounts are in paise (Razorpay's native unit), matching what the
razorpay_client module sends/receives.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Policy gate defaults (product-spec.md §5) ---
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "3"))
COOLDOWN_HOURS = float(os.environ.get("COOLDOWN_HOURS", "24"))
PER_SUB_EXPOSURE_CAP = int(os.environ.get("PER_SUB_EXPOSURE_CAP", "10000000"))  # paise = INR 1,00,000

# --- AI diagnosis (product-spec.md §3, architecture.md §4) ---
DIAGNOSIS_CONFIDENCE_THRESHOLD = float(os.environ.get("DIAGNOSIS_CONFIDENCE_THRESHOLD", "0.6"))
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# --- Executor retry policy (architecture.md §11) ---
EXECUTOR_MAX_ATTEMPTS = 2  # one deterministic retry, per product-spec §7
EXECUTOR_RETRY_BACKOFF_SECONDS = float(os.environ.get("EXECUTOR_RETRY_BACKOFF_SECONDS", "1.0"))

# --- Razorpay Test Mode credentials (architecture.md §7) ---
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

# Webhook signature secret (Razorpay's documented HMAC-SHA256 scheme --
# confirmed mechanism, not one of the UNCERTAIN actions). The replay
# script signs synthetic events with this same secret, exactly as a real
# Razorpay Test Mode webhook integration would be tested before going
# live.
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "dev-webhook-secret-change-me")

# --- Database ---
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./recoverflow.db")
