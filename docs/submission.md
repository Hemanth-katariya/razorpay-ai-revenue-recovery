# Application Submission Draft

Status: draft text for the Razorpay AI Buildathon application form
(`docs/hackathon.md`). Fill in the personal fields (name, college,
graduation year, availability, resume) yourself — everything below is
project-specific content you can copy in directly or lightly edit.

---

## Project name

**RecoverFlow**

## Selected track

**Track 03 — AI Revenue Recovery**

## Problem being solved

Razorpay retries a failed subscription charge automatically on its own
schedule, but there is no API to force that retry, no confirmed API to
change a customer's payment method or re-authorize their mandate, and
the one manual "charge now" override is a Dashboard button, not
something software can call. Left alone, a halted subscription is
silent revenue loss — the merchant only finds out when a human happens
to notice, and nobody is systematically measuring how much of that loss
was actually recoverable.

RecoverFlow closes that gap for the one part of it that's genuinely
API-executable: for every failed-subscription webhook, it uses an LLM to
diagnose *why* the charge failed and pick the best-fit recovery action
from a fixed, human-reviewed allow-list; a deterministic policy engine
gates that action against attempt caps, cooldowns, and exposure limits
before anything runs; a verified action is executed against Razorpay
directly; anything unverified, low-confidence, or requiring a human
(e.g. no API exists for it) is routed to an escalation queue instead of
being faked; and a later webhook — never "we sent a message" — is what
actually marks a subscription recovered. Every decision writes one
append-only audit row, and the batch report is honest about how much
was recovered, escalated, and stopped, not just the wins.

*(One line worth saying out loud in the application: we researched
which recovery actions Razorpay Test Mode can actually execute before
writing a line of product spec — see `docs/recovery-feasibility.md` —
and scoped the product to what that research actually supports, rather
than assuming "retry with backoff" or "force a mandate re-auth" were
available and finding out later they weren't.)*

## What broke, and how it was fixed

While building the escalation-resolution flow, resolving an open
escalation for a subscription that had *already* been force-closed by
the batch-close sweep (any subscription still non-terminal when a
batch's window closes is automatically transitioned to
`NOT_RECOVERED` — see `docs/architecture.md` §11) crashed the API with
an unhandled `500` — the resolve endpoint tried to write a
`RECOVERED`/`NOT_RECOVERED` transition on a subscription that was
already terminal, and `state_machine.py`'s `assert_legal()` correctly
raised `IllegalTransition`, but nothing in the API layer caught it.

This was caught by writing an integration test for the race
(`backend/tests/test_api_integration.py::test_batch_close_reconciles_open_escalations_and_resolve_returns_409`)
*before* it was hit manually — deliberately testing the batch-close
sweep's interaction with a still-open escalation, since that's exactly
the kind of "two components both think they own this subscription's
next transition" bug that's easy to miss when each component is tested
in isolation. The fix: `POST /escalations/{id}/resolve` now catches
`IllegalTransition` and returns a clean `409 Conflict` — "this
subscription is already terminal, your escalation is stale" — instead
of an opaque crash. The batch-close step was also made to
auto-resolve any escalations it sweeps, so a human never sees an "open"
escalation against a subscription that's actually already closed.

The broader lesson that shaped the rest of the build: every terminal
state has to be reachable from more than one code path in this system
(a subscription can be closed by the batch window *or* by a human
resolving an escalation *or* by an observed webhook), and every one of
those paths needs to agree, atomically, on what "already terminal"
means — which is why the State Machine module is the single writer of
`current_state` and every other component asks it, rather than each
component tracking its own notion of "done."

## Architecture explanation (for the pitch video / write-up)

See `docs/architecture.md` for the full document. One-paragraph version:
one FastAPI service, no queues or workers (the batch scale here doesn't
need them and it would work against auditability). A single state
machine (`DETECTED → DIAGNOSED → GATED → {EXECUTING|ESCALATED|STOPPED}
→ {RECOVERED|NOT_RECOVERED}`) is the only writer of subscription state,
and every transition writes one append-only audit row. The only module
that calls an LLM is the Diagnosis Service; the only module that calls
Razorpay is `razorpay_client`. A static, human-reviewed `actions` table
is the single source of truth for which recovery actions are safe to
run unattended; the AI recommends from that table, a deterministic
policy engine (allow-list, attempt cap, cooldown, exposure cap,
idempotency — each an independent pure function) gates it, and the
Executor independently refuses to run anything not marked
`API_VERIFIED`, even if the gate were ever wrong.

## Honest metrics (fill in after the final demo batch run)

Report the actual output of `GET /batches/{id}/metrics` after running
`python -m scripts.replay_batch synthetic_data/events_batch_01.json` —
do not hand-adjust these numbers. Suggested fields to quote:

- Revenue at risk detected: `<amount>` across `<count>` subscriptions
- Revenue recovered: `<amount>` across `<count>` subscriptions (observed
  via confirming webhook, never inferred from "action sent")
- Recovery rate: `<recovered/detected>` of detected, `<recovered/attempted>` of attempted
- Escalation rate: `<count>` (`<share>` of batch), broken down by reason
- Stop rate: `<count>` (`<share>` of batch), broken down by reason
- Batch size reconciliation: recovered + stopped + not_recovered + still_open = total batch size

If the §4.1 capability spike (see README) has not been run before the
demo is recorded, say so plainly rather than letting the numbers imply
otherwise: escalation rate will be 100% of detected failures, and
"recovered" will only reflect subscriptions whose payment was later
observed independent of any action this system took. That's still an
honest, defensible number — it's just a different claim than "the agent
recovered revenue," and the application should say which one it's
making.
