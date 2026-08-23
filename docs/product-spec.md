# Product Specification: AI Revenue Recovery Orchestrator

Track: 03 — AI Revenue Recovery (LOCKED)
Candidate: Failed-Subscription Recovery Agent (LOCKED, per `docs/recovery-feasibility.md`)
Status: Draft for review. No code written.

Sources of truth: `docs/hackathon.md` (official requirements),
`docs/recovery-feasibility.md` (what our backend can actually execute
against Razorpay Test Mode APIs). Anything below marked UNCERTAIN in
the feasibility check remains UNCERTAIN here — it is not assumed
available.

---

## 1. Problem

A merchant's recurring-subscription customers experience failed
charges (`payment.failed`, `subscription.pending`, `subscription.halted`).
Razorpay retries these automatically on its own schedule, but there is
no API to force a retry, no confirmed API to change the customer's
payment method or re-authorize a mandate, and the one manual
"charge now" mechanism found is a Dashboard button, not an API call.

Left alone, a halted subscription is silent revenue loss: the merchant
finds out only when a human notices, and no one has systematically
nudged the customer or measured how much of that loss was recoverable.

The orchestrator's job is narrow and honest given that constraint: for
every failed-subscription event, decide — deterministically-gated,
AI-diagnosed — whether an *actually executable* recovery action exists,
take it if verified, escalate to a human if not, and report, across a
batch, how much revenue was recovered.

## 2. Workflow / State Machine

```
DETECTED --> DIAGNOSED --> GATED --> {EXECUTING | ESCALATED | STOPPED}
EXECUTING --> {RECOVERED | NOT_RECOVERED}
ESCALATED --> {RECOVERED | NOT_RECOVERED}  (human closes the loop)
```

| State | Entered when | Owner |
|---|---|---|
| `DETECTED` | A `payment.failed` / `subscription.pending` / `subscription.halted` webhook is received and passes signature + idempotency checks | Deterministic |
| `DIAGNOSED` | AI classifies the failure reason from the event payload (error code/description) into a fixed category set, with a confidence score | AI |
| `GATED` | Deterministic policy engine evaluates eligibility (attempt cap, cooldown, amount cap, allow-listed action only) | Deterministic |
| `EXECUTING` | Gate passed AND the AI-recommended action is on the **verified-executable** action list | Deterministic executor, AI-selected action |
| `ESCALATED` | Gate passed but the only applicable action is `HUMAN_REQUIRED`, or AI confidence is below threshold, or the executor call fails after retry | Human queue |
| `STOPPED` | Attempt cap reached, cooldown never resolves, or merchant/customer opts out | Deterministic |
| `RECOVERED` | A subsequent webhook shows the subscription/invoice paid | Deterministic (observed, not claimed) |
| `NOT_RECOVERED` | Terminal without payment observed (batch window closes, or `STOPPED`) | Deterministic |

Every transition writes one audit record (see §8). No state is
skipped; `ESCALATED` and `STOPPED` are first-class terminal-capable
states, not error paths bolted on afterward.

## 3. AI vs. Deterministic Boundaries

**Deterministic (no AI):**
- Webhook signature verification and idempotency (dedupe by event ID)
- State machine transitions and persistence
- Policy gates: attempt cap, cooldown window, per-subscription and
  per-batch monetary exposure cap, action allow-list enforcement
- Stopping rules
- Execution of the actual API call for a verified action
- Outcome observation (did a later webhook confirm payment?)
- Metrics aggregation and audit logging

**AI (justified because it requires judgment, not lookup):**
- **Diagnosis**: classify the failure into a category (e.g.
  insufficient funds, card expired, bank/issuer decline, mandate
  issue, unknown) from the free-text/error-code payload, with a
  confidence score.
- **Action recommendation**: given the diagnosis and the *allow-listed*
  action set (never a free choice — see §5), pick the single best
  action and produce a one-sentence rationale for the audit trail.
- **Message drafting**: for a notification-based action, draft the
  short reminder copy sent to the customer.

The AI never selects an action outside the deterministic allow-list,
never sets policy thresholds, and never decides whether an action is
"verified" — that is a static, human-reviewed classification (§5). If
AI output fails schema validation or confidence is below threshold,
the event is routed to `ESCALATED`, not retried with a looser prompt.

## 4. Recovery Actions

Per `docs/recovery-feasibility.md`, action executability is not
uniform. Each action carries an explicit status; only `API_VERIFIED`
actions may run unattended.

| Action | Status | Notes |
|---|---|---|
| Resend invoice/payment reminder notification | `API_ASSUMED` — existence and POST method-level confirmed at overview level; exact path/params/Test-Mode behavior UNCERTAIN | Must pass the implementation-phase capability spike (§4.1) before it can become `API_VERIFIED` |
| Create a Payment Link for the outstanding amount + send notification | `API_ASSUMED` — same caveat as above | Same |
| Force an automatic retry | `NOT_SUPPORTED` | Documented gap: no API to trigger the scheduled retry |
| "Attempt Charge now" on a halted subscription's invoice | `HUMAN_REQUIRED` | Confirmed as a Dashboard-only action, not an API call |
| Change payment method / re-authorize mandate | `NOT_SUPPORTED` | Documented gap; closest lead (Subscription Link) is unconfirmed, treated as not available for MVP |

### 4.1 Capability verification spike (required before §6 build starts)

Before any action is wired into the executor, the implementation
phase must make one real Test Mode call for each `API_ASSUMED` action
and record: exact endpoint, required params, Test Mode availability,
and whether the resulting state change is observable (webhook or
GET). An action is promoted to `API_VERIFIED` only after this. An
action that fails verification is demoted to `HUMAN_REQUIRED` for
this submission — it is not simulated and reported as if real.

## 5. Policy Gates (deterministic, pre-execution)

All of the following must pass before `EXECUTING` is entered; any
failure routes to `ESCALATED` or `STOPPED` with the failing gate
named in the audit record.

1. **Allow-list gate** — action must be `API_VERIFIED`. Anything else
   (`API_ASSUMED` still unverified, `NOT_SUPPORTED`, `HUMAN_REQUIRED`)
   never reaches the executor.
2. **Attempt cap** — max N recovery attempts per subscription
   (default 3) across the whole batch.
3. **Cooldown** — minimum interval between attempts on the same
   subscription (default 24h simulated time in demo data).
4. **Exposure cap** — max total outstanding amount the batch will act
   on, and a per-subscription amount ceiling, to bound blast radius.
5. **Idempotency gate** — a given (subscription, event) pair triggers
   at most one action; replays are dropped, not re-executed.

Every gate decision (pass/fail + reason) is logged, not just the
final outcome.

## 6. Metrics (measured across a batch, not cherry-picked)

- **Revenue at risk detected** — count and total amount of
  subscriptions entering `DETECTED`.
- **Revenue recovered** — count and total amount reaching `RECOVERED`,
  attributed only when a later webhook confirms payment (never
  inferred from "action sent").
- **Recovery rate** — recovered / detected, and recovered / attempted.
- **Escalation rate** — share routed to `ESCALATED`, broken down by
  reason (unverified action, low AI confidence, executor failure).
- **Stop rate** — share reaching `STOPPED`, by stopping reason.
- **Time-to-recovery** — detection to confirmed payment, for recovered
  cases.
- **Diagnosis confidence distribution** — to make AI honesty visible,
  not just accuracy on a cherry-picked sample.

All metrics are reported for the full synthetic batch, including
failures and escalations, per the hackathon's "report failures
honestly" requirement.

## 7. Failure Cases (explicit handling required)

| Failure | Handling |
|---|---|
| Duplicate/replayed webhook | Idempotency gate drops it; logged, no re-action |
| Webhook signature invalid | Rejected, logged, not processed |
| AI returns malformed/off-schema output | Schema validation fails → `ESCALATED`, reason recorded |
| AI diagnosis confidence below threshold | `ESCALATED`, reason recorded |
| Executor API call times out or errors | One deterministic retry with backoff; second failure → `ESCALATED` |
| Action not yet `API_VERIFIED` at runtime | Routed to `ESCALATED`/`HUMAN_REQUIRED`, never attempted |
| Attempt cap / exposure cap reached | `STOPPED`, reason recorded, no further action |
| No outcome observed before batch window closes | `NOT_RECOVERED`, not silently dropped |

## 8. Audit Trail

One append-only record per state transition, containing: event ID,
subscription ID, timestamp, prior state, new state, actor
(`deterministic` or `ai`), AI diagnosis + confidence (if applicable),
gate results, action taken (if any) with its verification status at
execution time, and outcome. The audit trail must let a reviewer
reconstruct, for any single subscription, exactly why each decision
was made — this is the "explainable and auditable" requirement from
`docs/hackathon.md`, not a log dump.

## 9. 5-Minute Demo

1. (30s) Problem statement: failed subscriptions are silent revenue
   loss; show the feasibility constraint (no forced retry, no mandate
   change API) as the reason the design is deliberately narrow.
2. (60s) Feed a batch of synthetic failed-subscription events
   (mix of categories, some duplicates, some exceeding caps).
3. (90s) Walk one subscription end-to-end through the state machine:
   detection → AI diagnosis + confidence → gate decisions → verified
   action executed → later webhook confirms recovery. Show the audit
   record for it.
4. (60s) Show one failure handled gracefully live: an AI-malformed
   output or an executor timeout routing to `ESCALATED` instead of
   crashing or silently retrying forever.
5. (60s) Show the batch metrics report: detected, recovered,
   escalated, stopped, recovery rate — including the honest, non-zero
   escalation/stop numbers.

## 10. MVP and Non-Goals

**MVP (in scope):**
- Webhook ingestion (simulated/replayed in Test Mode) for
  `payment.failed` / `subscription.pending` / `subscription.halted`
- AI diagnosis + action recommendation (from allow-list only)
- Deterministic policy gate engine (§5)
- Executor for whichever `API_ASSUMED` actions pass the §4.1
  verification spike (expected: invoice reminder resend and/or
  Payment Link creation + notify)
- Escalation queue for `HUMAN_REQUIRED` / unverified / low-confidence
  cases
- Batch metrics report and full audit trail

**Non-goals (explicitly out of scope for this submission):**
- Any real production payment execution — Test Mode / synthetic data
  only
- Forcing automatic retries or changing payment method/mandate
  (confirmed `NOT_SUPPORTED`)
- Checkout abandonment, B2B receivables chasing, voice/Hinglish
  recovery, promise-to-pay tracking — other Track 03 directions, not
  this candidate
- Multi-channel notification orchestration (one channel for MVP)
- A merchant-facing UI beyond what's needed to show the audit trail
  and metrics report in the demo

## 11. Acceptance Criteria (testable)

1. Given a batch of N synthetic failed-subscription events, every
   event reaches a terminal state (`RECOVERED`, `NOT_RECOVERED`, or
   `STOPPED`) with zero events left permanently stuck.
2. Every processed event has a complete audit trail: detection →
   diagnosis (with confidence) → gate results → action/escalation →
   outcome — reconstructable from logs alone, without re-running code.
3. Replaying an identical webhook event never produces a second
   action for the same (subscription, event) pair.
4. Injecting an event whose only applicable action is
   `NOT_SUPPORTED` or `HUMAN_REQUIRED` never results in an executor
   call — it is provably routed to `ESCALATED`.
5. Injecting more failure events for one subscription than the
   attempt cap allows results in `STOPPED` after the cap, with no
   action beyond it.
6. Injecting a malformed AI response (schema-invalid or
   below-confidence) results in `ESCALATED`, not a crash and not a
   silent default action.
7. The batch metrics report's recovered/escalated/stopped counts sum
   to the total batch size, and "recovered" is only ever set from an
   observed confirming webhook, never from "action was sent."
8. No action is executed unless its status is `API_VERIFIED` at
   execution time, per the §4.1 spike outcome — verifiable by
   inspecting the allow-list used by the executor.
