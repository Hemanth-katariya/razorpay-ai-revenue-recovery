# Implementation Notes

Status: living document, implementation phase. Records decisions made
*while coding* that `docs/architecture.md` and `docs/product-spec.md`
left underspecified. It does not revisit anything those documents
already decided -- see `docs/decision.md` for the locked product/track
decision. Update this file whenever a gap like this comes up again.

## 1. AI action menu is not restricted to `API_VERIFIED` only

`architecture.md` §4 point 2 literally says the recommended action is
"drawn only from the currently API_VERIFIED subset of actions." Taken
literally, the AI's selectable menu would be *empty* before the §4.1
verification spike runs (every action starts `API_ASSUMED` or
`HUMAN_REQUIRED`), which makes it impossible for the AI to ever recommend
the `HUMAN_REQUIRED` action -- yet `escalations.reason` includes
`human_required` as a named reason (architecture.md §3), and product-spec
acceptance criterion #4 explicitly describes a scenario where "the only
applicable action is NOT_SUPPORTED or HUMAN_REQUIRED," implying the AI
did identify that action as the best fit.

**Decision:** the menu injected into the AI's tool schema
(`app/actions/registry.py::list_selectable_for_ai`) is every action whose
status is *not* `NOT_SUPPORTED` -- i.e. `API_VERIFIED`, `API_ASSUMED`, and
`HUMAN_REQUIRED` are all selectable. `NOT_SUPPORTED` rows are excluded
because no escalation reason models "AI recommended a documented gap";
those rows exist purely as an audit record of a known limitation
(`force_retry`, `change_mandate`).

The deterministic allow-list gate (`app/policy/gates.py::allow_list_gate`)
is still the sole decider of whether a recommended action may execute
right now -- the AI never decides verification status, per product-spec
§3. This preserves the intent of §4 ("the model picks from a closed
list") while making the `human_required` / `unverified_action`
escalation reasons actually reachable.

## 2. `attempt_count` increments only on entering `EXECUTING`

Gate order is fixed (`allow_list` first, `attempt_cap` second, per
architecture.md §5) and the engine stops at the first failing gate. That
means `attempt_cap`, `cooldown`, and `exposure_cap` are only ever
evaluated for a subscription whose recommended action already passed the
allow-list gate. Incrementing `attempt_count` any earlier (e.g. on every
`GATED` cycle) would not change when `STOPPED` becomes reachable, since
`allow_list` always intercepts first regardless of `attempt_count`.

**Decision:** `attempt_count` increments, and `cooldown_until` is set,
only when a subscription actually enters `EXECUTING` (see
`app/api/webhooks.py::_run_recovery_pipeline`). "Attempt" means "we
actually took a recovery action," matching the plain-English product-spec
wording ("max N recovery attempts").

**Consequence, stated plainly:** before the §4.1 capability spike
promotes at least one action to `API_VERIFIED`, no subscription can ever
reach `EXECUTING`, so `STOPPED` (via attempt cap, cooldown, or exposure
cap) cannot be demonstrated through the live webhook pipeline either --
every failure event routes to `ESCALATED` at the allow-list gate. This is
the correct, honest behavior per architecture.md §6, not a bug. The
`attempt_cap` / `cooldown` / `exposure_cap` gates are exercised directly
in `tests/test_policy_gates.py` against a test DB with a manually-promoted
`API_VERIFIED` action, independent of whether the real spike has run.

## 3. `EXECUTING`/`ESCALATED` can transition back to `DETECTED`

`product-spec.md` §2's diagram doesn't show a subscription receiving a
*second* failure event before its first cycle reached a terminal state --
but the synthetic batch is specified to send several failures per
subscription to exercise the attempt cap (acceptance criterion #5), and
processing is synchronous per event (architecture.md §2), so a
subscription is always resting in `EXECUTING`, `ESCALATED`, or a terminal
state between requests, never mid-flow.

**Decision:** added `EXECUTING -> DETECTED` and `ESCALATED -> DETECTED` as
legal edges in `app/core/state_machine.py::TRANSITIONS` for a new failure
event arriving on a non-terminal subscription. `STOPPED` / `RECOVERED` /
`NOT_RECOVERED` remain strictly terminal: a repeat failure event on an
already-terminal subscription is dropped and logged, not reopened, for
this submission's batch-scoped scope.

## 4. Outcome Observer is its own module

`architecture.md` §13's folder sketch doesn't list a file for the
"Outcome Observer" component, even though §1's component table names it
as a distinct responsibility from the Ingestion API. Added
`app/core/outcome_observer.py` rather than inlining the match-and-mark-
`RECOVERED` logic into `app/api/webhooks.py`, to keep that boundary
explicit and independently testable.

## 5. Synthetic webhook envelope shape is our own, not Razorpay's exact wire format

Real Razorpay webhook payloads nest an `entity`/`contains`/`payload.<resource>.entity`
structure specific to each event type. Reproducing that exactly added
complexity with no observable benefit for a self-contained replay tool
(we generate and consume the same file). The synthetic envelope instead
is:

```json
{
  "id": "evt_...",
  "event": "payment.failed",
  "created_at": "<ISO 8601 logical timestamp>",
  "payload": {
    "subscription": { "id": "...", "customer_ref": "...", "customer_email": "...",
                       "customer_contact": "...", "outstanding_amount": <paise>,
                       "invoice_id": "..." },
    "payment": { "error_code": "...", "error_description": "..." }
  }
}
```

Signature verification is still real: `X-Razorpay-Signature` is an
HMAC-SHA256 of the raw request body using `RAZORPAY_WEBHOOK_SECRET`,
exactly Razorpay's documented (confirmed, not UNCERTAIN) webhook signing
scheme -- `scripts/replay_batch.py` signs each event with the same
secret the server verifies against, which is exactly how a real
integration tests its webhook handler before going live.

## 6. Batch-run association is an explicit query parameter

Real Razorpay webhooks carry no concept of our internal `batch_run_id`.
`POST /webhooks/razorpay` takes `batch_run_id` as a required query
parameter, set by whatever is replaying/relaying events (the replay
script, or a demo harness). This keeps the ingestion endpoint stateless
about "which batch is currently open" rather than guessing.
