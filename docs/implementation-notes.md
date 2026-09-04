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

## 7. `scripts/verify_actions.py` runs the §4.1 spike through app code, not ad hoc requests

`product-spec.md` §4.1 requires the spike to make "one real Test Mode
call" and record what happened before an action may become
`API_VERIFIED`, but doesn't specify how that call should be made.
Writing a one-off script that hits Razorpay directly (bypassing
`app.razorpay_client`) would verify Razorpay's API, not this codebase's
integration with it — a subtle difference, since a wrong parameter name
in `razorpay_client.py` itself would then pass the spike anyway.

**Decision:** `scripts/verify_actions.py` calls the exact same
`app.razorpay_client.create_payment_link` /
`send_payment_link_notification` / `resend_invoice_notification`
functions the Executor calls at runtime. "Verified" therefore means
"the code path that will actually execute was exercised for real,"
not just "the endpoint exists." The script never writes
`actions.status = API_VERIFIED` unless the real call it just made
returned `ok=True` (`--promote` is a separate, explicit flag on top of
that) — matching `registry.py`'s existing rule that only a human,
after a real success, may promote a row. Discovery (`invoice --list`)
uses a raw `razorpay.Client` directly since listing invoices generally
isn't a method the running app needs — adding it to
`app.razorpay_client` would violate architecture.md §7's "no
general-purpose SDK wrapper with unused methods."

## 8. LLM provider is Gemini, not Claude as architecture.md originally specified

`architecture.md`'s dependency-choices section named "LLM: Claude,
structured/tool-call output" for the Diagnosis Service. During the §4.1
verification pass, the Anthropic API key available for this project
turned out to be an identity-linked key requiring an
`anthropic-workspace-id` header (a multi-workspace-org key type, fixed
by adding `ANTHROPIC_WORKSPACE_ID` support in `app/config.py` /
`app/ai/diagnosis.py`) -- but once that was resolved, the Anthropic
account had $0 API credit and no free trial credit, and adding paid
credit wasn't an option for this project.

**Decision:** switched the Diagnosis Service to Gemini
(`google-genai` SDK, `gemini-2.5-flash` by default), using a free
Google AI Studio API key (no billing account required). This changes
only `app/ai/diagnosis.py`'s model-call mechanics and `app/config.py`'s
env vars (`GEMINI_API_KEY` / `GEMINI_MODEL` replace `ANTHROPIC_*`) --
every other part of architecture.md §4 is unchanged: the model still
receives the allow-listed action set injected per-request (not baked
into a static prompt), still must call a single named tool
(`emit_diagnosis`) via forced function-calling rather than respond in
prose, and its output still passes through the same
`app/ai/schemas.py::DiagnosisOutput` Pydantic validation before the
Policy Engine ever sees it. `docs/architecture.md`'s dependency-choices
line was updated in place to say Gemini and point back here, rather
than left to describe a provider the code no longer calls.

The abandoned Anthropic-specific code (identity-linked-key handling,
Anthropic tool-use response parsing) was removed rather than kept
behind a fallback/feature-flag — there was no requirement driving a
dual-provider design, and an unused code path is a liability per
CLAUDE.md's "no backwards-compatibility shims" guidance, not a safety
net.

Model selection within Gemini went through several iterations before
landing on `gemini-flash-lite-latest` as the default: `gemini-2.5-flash`
(the initial pick) turned out to be deprecated for new accounts
(404, "no longer available to new users"); the `gemini-flash-latest`
alias and the pinned `gemini-3.6-flash` both hit real upstream 503s
under high demand and a 20-requests/day free-tier cap respectively
during testing. `gemini-flash-lite-latest` was chosen because Lite-tier
models get a materially larger free daily quota, it's an alias (won't
go stale the way a pinned version number did), and manual testing
showed it classifies this task's failure payloads correctly at full
confidence -- reliability across a whole demo mattered more here than
a marginal quality gain from a heavier model.

## 9. `action_executions` unique constraint omitted `attempt_no` -- a real bug, not a design gap

This one wasn't a documentation ambiguity like the others in this file
-- it was a genuine contradiction between architecture.md's own
sections, only surfaced once a real webhook replay actually reached a
failing `EXECUTING` state for the first time (which required the §4.1
spike to have promoted an action to `API_VERIFIED`, which in turn
required the Gemini switch above to get a working Diagnosis Service at
all).

architecture.md §3 documents `action_executions.attempt_no` as "1 or 2
(one retry only)" and §11's error table says a second Executor failure
means "both attempts recorded in `action_executions`" -- both describing
two rows per (subscription_id, event_id). But §8 gave
`action_executions(subscription_id, event_id)` a unique constraint with
no `attempt_no`, and `tests/test_idempotency.py` had a test asserting
that inserting a second attempt for the same pair *must* be rejected by
the DB -- actively locking in the contradiction. `app/actions/executor.py`
was written correctly per §3/§11 (it writes one row per attempt,
1 then 2, on retry) but had never been exercised end-to-end through a
real webhook before now: every prior run escalated at diagnosis before
ever reaching the Executor, first because no action was `API_VERIFIED`
yet (see §2 above), then because the Anthropic key never worked (see
§8 above). The first real two-attempt failure (a synthetic event
referencing a fake `invoice_id` that doesn't exist in Razorpay Test
Mode, so both attempts genuinely failed) hit the constraint and crashed
with an `IntegrityError` instead of recording the second attempt and
escalating cleanly.

**Decision:** added `attempt_no` to the unique constraint
(`uq_action_exec_sub_event_attempt`), matching what §3/§11 always said
should be possible. `app/core/idempotency.py::action_already_executed`
was also fixed -- it used `scalar_one_or_none()`, which raises
`MultipleResultsFound` once two legitimate rows exist for the same
pair; changed to a plain existence check, since "does at least one
attempt exist" (not "does exactly one exist") is what the idempotency
gate (product-spec §5) actually needs. `tests/test_idempotency.py` was
corrected to assert the real invariant: a second *attempt_no* for the
same pair succeeds (and `action_already_executed` still reports True
without crashing), while a duplicate of the *same* attempt_no is what
the DB constraint actually rejects. architecture.md §8's wording was
updated to state the constraint is per-attempt, not per-pair, and to
clarify that preventing a second full execution *sequence* for an
already-executed event is the read-side idempotency gate's job, not
something the DB constraint alone guarantees.

## 10. `app.razorpay_client.send_payment_link_notification` called a method that doesn't exist

Found by the §4.1 spike's first real run against Razorpay Test Mode,
not by code review. `create_payment_link` succeeded (real Payment Link
created), but the notify step raised `AttributeError: 'PaymentLink'
object has no attribute 'notify_by'`.

The installed `razorpay` SDK names this action inconsistently across
resources: `Invoice.notify_by` (snake_case) but
`PaymentLink.notifyBy` (camelCase) — same signature
(`(id, medium, **kwargs)`), different name, an inconsistency in the SDK
itself rather than a version mismatch. `resend_invoice_notification`
(which calls `Invoice.notify_by`) was correct; only the Payment Link
side was wrong.

**Decision:** fixed the one call site
(`client.payment_link.notify_by` → `client.payment_link.notifyBy`) and
re-ran the spike for real, which then succeeded and promoted
`create_payment_link_and_notify` to `API_VERIFIED`. No test caught this
beforehand because nothing in the test suite calls the real SDK method
names — `app/razorpay_client/client.py` is explicitly the one module
allowed to touch the network (module docstring), so its correctness
against the actual installed SDK can only be confirmed by a real call,
which is exactly what the §4.1 spike is for.
