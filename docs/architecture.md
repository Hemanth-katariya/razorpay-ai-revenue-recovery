# Architecture: AI Revenue Recovery Orchestrator

Status: Draft for review. No code written.

Source of truth: `docs/product-spec.md`. This document does not
revisit the product decision, the AI/deterministic boundary, the
policy gates, or the metrics definitions — it only decides how to
build what `product-spec.md` already specified.

Nothing here assumes an action classified `UNCERTAIN` or
`NOT_SUPPORTED` in `docs/recovery-feasibility.md` is available. The
action registry (§6) is built so that no `API_ASSUMED` action can
run until the §4.1 capability spike promotes it to `API_VERIFIED`.

---

## 1. System Components and Responsibilities

A single modular backend service. No microservices, no message
queue, no separate workers — the batch sizes in the spec (a
synthetic demo batch, not production traffic) don't justify that
complexity, and it would work against "explainable and auditable"
by adding places for state to hide.

| Component | Responsibility | AI or deterministic |
|---|---|---|
| **Ingestion API** | Receives webhook events (real or replayed), verifies signature, enforces idempotency, persists the raw event | Deterministic |
| **State Machine** | Owns the single legal transition table from `product-spec.md` §2; every transition goes through here | Deterministic |
| **Diagnosis Service** | Calls the LLM with the event payload, validates the response against a strict schema, attaches a confidence score | AI, schema-gated |
| **Policy Engine** | Runs the ordered gate checks from §5 against the diagnosis + subscription history; short-circuits on first failure | Deterministic |
| **Action Registry** | Static, human-reviewed table of actions and their verification status; the single place `API_VERIFIED` is decided | Deterministic (data, not code, changes when a status changes) |
| **Executor** | Calls the real Razorpay Test Mode API for a verified action; owns the one-retry-then-escalate rule | Deterministic |
| **Outcome Observer** | Reads later webhooks (`payment.captured` / `invoice.paid` / `subscription.charged`) and matches them back to an open subscription to mark `RECOVERED` | Deterministic |
| **Audit Logger** | Single write path for the append-only audit trail; every other component calls into this, never writes audit rows itself | Deterministic |
| **Batch Runner** | Replays a synthetic event file through the ingestion path in order, then closes the batch window | Deterministic |
| **Metrics Aggregator** | Computes the §6 metrics from persisted state on demand; not a streaming/real-time pipeline | Deterministic |
| **Demo API** | Read endpoints the 5-minute demo drives: subscription list, audit trail, escalation queue, metrics report | Deterministic |

The only component that calls an LLM is the Diagnosis Service. The
only component that calls Razorpay is the Executor (and, for `GET`
state checks, the Outcome Observer). Nothing else touches an
external system.

---

## 2. Request / Event Flow

```
Webhook (real or replayed)
        │
        ▼
 [Ingestion API]
   - verify signature            (fail -> reject, log, stop)
   - dedupe by event_id          (dup -> drop, log, stop)
        │
        ▼
 subscription upserted, state -> DETECTED   (audit row written)
        │
        ▼
 [Diagnosis Service] -> calls LLM with event payload
   - validate JSON against schema
   - confidence >= threshold?
        │ pass                              │ fail (malformed or low confidence)
        ▼                                   ▼
 state -> DIAGNOSED (audit row)      state -> ESCALATED, reason=ai_failure (audit row)
        │                                   │
        ▼                                   └──────────────► [Escalation Queue]
 [Policy Engine] runs gates in order:
   1. allow-list (action must be API_VERIFIED)
   2. attempt cap
   3. cooldown
   4. exposure cap (per-sub + per-batch)
   5. idempotency (subscription, event) pair
 state -> GATED (audit row, gate_results attached)
        │
   ┌────┴─────────────────┬───────────────────────────┐
   ▼ all pass              ▼ allow-list/idempotency fail  ▼ cap/cooldown fail
 [Executor]              state -> ESCALATED             state -> STOPPED
 call Razorpay API       (audit row, reason)            (audit row, reason)
   │        │                    │                            │
   │ ok      │ error x2          ▼                            ▼
   ▼        ▼            [Escalation Queue]            (terminal, no action)
 state ->  state ->
 EXECUTING ESCALATED
   │        (audit row,
   │         reason=executor_failure)
   ▼
 [Escalation Queue] also receives EXECUTING failures
        │
        ▼
 later webhook observed by [Outcome Observer]
   matches (subscription_id, still-open) ──► state -> RECOVERED (audit row)
   batch window closes, no match          ──► state -> NOT_RECOVERED (audit row)
```

Every arrow into a new box on the left is one call into the Audit
Logger. `GATED` always gets its own audit row even though the
engine immediately continues into the next state in the same
request — the transition table has no state that is inferred rather
than recorded (product-spec §2, "no state is skipped").

---

## 3. Database Schema / Entities

SQLite for the MVP (single file, zero ops, trivial to ship inside
the repo and reset between demo runs). Schema is written so moving
to Postgres later is a connection-string change, not a redesign.

```
batch_runs
  id (pk)
  label
  started_at
  window_closes_at        -- batch-level "no outcome observed" boundary
  exposure_cap_total       -- max amount this batch will act on
  exposure_running_total    -- updated transactionally as EXECUTING is entered
  status                     -- open | closed

subscriptions
  id (pk)                    -- Razorpay subscription_id
  batch_run_id (fk)
  customer_ref
  outstanding_amount
  current_state               -- DETECTED..NOT_RECOVERED (product-spec §2)
  attempt_count                -- across the batch, for the attempt cap
  last_attempt_at               -- logical timestamp, see §8
  cooldown_until                  -- logical timestamp
  created_at / updated_at

events
  id (pk)                          -- Razorpay event_id (unique -> idempotency)
  batch_run_id (fk)
  subscription_id (fk, nullable)    -- null until matched
  event_type                         -- payment.failed | subscription.pending |
                                      -- subscription.halted | payment.captured | ...
  payload_json                        -- raw event, kept verbatim for audit
  received_at                          -- logical timestamp
  signature_valid                       -- bool

diagnoses
  id (pk)
  event_id (fk)
  subscription_id (fk)
  category                                -- fixed enum, see §4
  confidence                               -- 0..1
  recommended_action_id (fk -> actions, nullable)
  rationale                                 -- one sentence, from AI
  message_draft                              -- nullable, for notification actions
  raw_model_output                            -- verbatim, for audit
  model_name / prompt_version
  created_at

actions
  id (pk)                                      -- e.g. "resend_invoice_reminder"
  display_name
  status                                         -- API_VERIFIED | API_ASSUMED |
                                                  -- NOT_SUPPORTED | HUMAN_REQUIRED
  verified_at                                     -- set only when §4.1 spike passes
  verification_notes                               -- endpoint/params found by the spike

gate_results
  id (pk)
  event_id (fk)
  subscription_id (fk)
  gate_name                                         -- allow_list | attempt_cap |
                                                      -- cooldown | exposure_cap | idempotency
  passed
  reason
  evaluated_at (logical)

action_executions
  id (pk)
  subscription_id (fk)
  event_id (fk)
  action_id (fk)
  attempt_no                                          -- 1 or 2 (one retry only)
  status                                                -- success | error | timeout
  request_payload / response_payload                     -- verbatim, for audit
  error_message
  executed_at (logical)
  UNIQUE(subscription_id, event_id)                       -- idempotency gate, enforced in DB

escalations
  id (pk)
  subscription_id (fk)
  event_id (fk)
  reason                                                    -- unverified_action |
                                                              -- low_confidence | schema_invalid |
                                                              -- executor_failure | human_required
  status                                                      -- open | resolved
  opened_at (logical)
  resolved_at (logical, nullable)
  resolution                                                   -- recovered | not_recovered, nullable
  resolver_note

audit_log
  id (pk)
  batch_run_id (fk)
  event_id (fk, nullable)
  subscription_id (fk)
  ts (logical)
  prior_state
  new_state
  actor                                                          -- deterministic | ai
  detail_json      -- denormalized snapshot: diagnosis summary, gate
                    -- results, action + verification status at execution
                    -- time, outcome — enough to reconstruct the decision
                    -- without joining into tables that may later change
```

`audit_log` is insert-only: no `UPDATE`/`DELETE` path exists in the
application code for this table.

---

## 4. AI Diagnosis + Structured Output Flow

1. Diagnosis Service builds a prompt from `events.payload_json`
   (error code/description, event type, subscription context) —
   deterministic prompt template, no free-form user input reaches
   the model.
2. Model is called with a **strict output schema** (fixed category
   enum, confidence float, recommended action drawn only from the
   currently `API_VERIFIED` subset of `actions`, one-sentence
   rationale, optional message draft). The allow-listed action set
   is injected into the prompt/schema at call time — the model picks
   from a closed list, it does not free-text an action name.
3. Response is parsed and validated against a schema (Pydantic or
   equivalent). Any of the following routes straight to `ESCALATED`
   with `reason=schema_invalid` or `reason=low_confidence`, and is
   **not retried with a looser prompt** (product-spec §3):
   - JSON doesn't parse / doesn't match the schema
   - `category` not in the fixed enum
   - `recommended_action` not in the injected allow-list
   - `confidence` below the configured threshold
4. On success, the full raw model output is stored in
   `diagnoses.raw_model_output` — the audit trail needs to show
   exactly what the model said, not a paraphrase.
5. The Diagnosis Service never calls Razorpay and never writes to
   `action_executions` — it only produces a recommendation that the
   Policy Engine and Executor independently gate and act on.

Fixed category enum (from product-spec §3): `insufficient_funds`,
`card_expired`, `bank_issuer_decline`, `mandate_issue`, `unknown`.

---

## 5. Deterministic Policy Engine

Gates run in a fixed order, each as an independent, pure function of
`(subscription, event, diagnosis, batch_run)` returning `passed` +
`reason`. The engine stops at the first failure — no gate runs on
optimistic state left by a gate that already failed.

1. **Allow-list gate** — `actions[recommended_action_id].status ==
   API_VERIFIED`.
2. **Attempt cap** — `subscription.attempt_count < MAX_ATTEMPTS`
   (default 3).
3. **Cooldown** — `logical_now >= subscription.cooldown_until`.
4. **Exposure cap** — `subscription.outstanding_amount <=
   PER_SUB_CAP` **and** `batch_run.exposure_running_total +
   outstanding_amount <= batch_run.exposure_cap_total`.
5. **Idempotency gate** — no existing `action_executions` row for
   `(subscription_id, event_id)`. Enforced twice: once here (fast
   fail with a clear reason) and once as a DB unique constraint
   (§8) so a race can never double-execute.

Every gate's `passed`/`reason` is written to `gate_results`
regardless of outcome (product-spec §5, "every gate decision is
logged, not just the final outcome"), then the engine derives the
next state:

- All pass → `EXECUTING`
- Gate 1 or 5 fails → `ESCALATED` (unverified action / duplicate is
  not a stopping condition, it's routed to a human or silently
  dropped per the idempotency case)
- Gate 2, 3, or 4 fails → `STOPPED`

The Policy Engine is pure and has no side effects beyond the
`gate_results` + audit writes — it never calls Razorpay or the LLM.

---

## 6. Capability Verification / Action Registry

The `actions` table (§3) is the **single source of truth** the
Executor and the allow-list gate both read. It is seeded, not
computed at runtime, and only a human edits `status`:

- At architecture time, every row starts as either `API_ASSUMED`
  (the two notification actions), `NOT_SUPPORTED` (force retry,
  change mandate), or `HUMAN_REQUIRED` (attempt-charge-now).
- The implementation phase's §4.1 spike makes one real Test Mode
  call per `API_ASSUMED` action, records the exact endpoint,
  params, and observability outcome in `verification_notes`, and
  only then flips `status` to `API_VERIFIED` with `verified_at`
  set.
- An action that fails the spike is set to `HUMAN_REQUIRED`, not
  left as `API_ASSUMED` and not silently treated as verified.
- The Executor refuses to run any action whose current `status` is
  not `API_VERIFIED`, independent of what the allow-list gate
  already checked — this is the defense-in-depth referenced in
  acceptance criterion #8 ("verifiable by inspecting the allow-list
  used by the executor").

This means the system is buildable and demoable *before* the spike
finishes: every event for an `API_ASSUMED`/`NOT_SUPPORTED` action
correctly routes to `ESCALATED`/`STOPPED`, which is itself one of
the demo's required beats (§9 step 4). The spike only ever *adds*
capability, never something the state machine depends on existing.

---

## 7. Razorpay Integration Boundary

One module (`razorpay_client`) is the only code allowed to make an
HTTP call to Razorpay. It exposes exactly the methods the action
registry can reference — no general-purpose Razorpay SDK wrapper
with methods nothing in the registry uses:

- `get_subscription(subscription_id)` — used by the Outcome
  Observer / demo read endpoints, not the execution path
- `get_invoices_for_subscription(subscription_id)` — same
- `resend_invoice_notification(invoice_id)` — only callable once its
  registry row is `API_VERIFIED`
- `create_payment_link(...)` / `send_payment_link_notification(...)`
  — same condition

Every call is made against Test Mode keys only. There is no
production credential path in this codebase. The client does not
catch-and-fake a success response under any circumstance — a failed
or unverified call is a failed or unverified call, surfaced to the
Executor as such (per product-spec §4.1: "not simulated and
reported as if real").

Inbound direction (webhooks) is handled entirely by the Ingestion
API (§1); the `razorpay_client` module is outbound-only.

---

## 8. Idempotency and State Management

**Idempotency, two layers:**
- `events.id` (the Razorpay `event_id`) is the primary key —
  `INSERT ... ON CONFLICT DO NOTHING` at the DB layer means a
  replayed webhook cannot be processed twice, atomically, even under
  concurrent delivery.
- `action_executions(subscription_id, event_id)` has a unique
  constraint — even if application logic were ever wrong, the DB
  itself refuses a second action for the same pair (acceptance
  criterion #3).

**State management:**
- `subscriptions.current_state` holds exactly one of the states in
  product-spec §2. The only writer is the State Machine module,
  which holds the legal-transition table and rejects any transition
  not in it (fail loudly rather than silently accept an
  inconsistent state).
- Each transition is a single DB transaction: update
  `subscriptions.current_state` (+ `attempt_count` /
  `cooldown_until` / `batch_runs.exposure_running_total` where
  relevant) and insert the corresponding `audit_log` row together,
  so the audit trail can never drift from the actual state.

**Logical clock, not wall-clock:** the product spec's cooldown is
"24h simulated time in demo data" — a live 5-minute demo cannot wait
24 real hours. Every timestamp comparison (`cooldown_until`,
`window_closes_at`) is computed against a **logical time** carried
on the event payload (a `simulated_at` field the synthetic batch
generator sets), not `system.now()`. This keeps the batch
deterministic and reproducible, and is the only way the cooldown
gate is demoable at all — it is not a shortcut, it's required by the
demo format itself.

---

## 9. Audit Trail Design

Already specified at the schema level in §3 (`audit_log`). Design
principles:

- **Append-only.** No update or delete path in the application.
- **One row per transition, not per event.** A single incoming
  webhook can produce several rows (`DETECTED` → `DIAGNOSED` →
  `GATED` → `EXECUTING`, say) — that's intentional; each is a
  distinct, independently-reasoned decision.
- **Self-contained rows.** `detail_json` denormalizes the diagnosis
  summary, gate results, and action/verification status *at the
  time of the transition* directly into the row, so reconstructing
  "why" for one subscription is one filtered query
  (`WHERE subscription_id = ?`), not a multi-table join against
  data that may have changed since (acceptance criterion #2:
  "reconstructable from logs alone, without re-running code").
- **Actor field is mandatory.** Every row says `deterministic` or
  `ai` — a reviewer should never have to guess which one made a
  given call.

---

## 10. Batch Metrics Pipeline

Not a streaming system — the batch sizes here don't need one, and a
separate pipeline is another place to lose auditability. Metrics are
plain read-only SQL aggregates over `subscriptions`, `audit_log`,
`gate_results`, and `action_executions`, filtered by `batch_run_id`,
computed on demand by the Metrics Aggregator:

| Metric (product-spec §6) | Computed as |
|---|---|
| Revenue at risk detected | `COUNT`/`SUM(outstanding_amount)` of subscriptions that ever entered `DETECTED` |
| Revenue recovered | `COUNT`/`SUM` of subscriptions whose `current_state = RECOVERED` |
| Recovery rate | recovered / detected, recovered / (count that reached `EXECUTING`) |
| Escalation rate (by reason) | `GROUP BY escalations.reason` |
| Stop rate (by reason) | `GROUP BY` the `STOPPED` audit rows' `detail_json.reason` |
| Time-to-recovery | `RECOVERED` audit row's `ts` minus that subscription's `DETECTED` audit row's `ts` (logical time) |
| Diagnosis confidence distribution | histogram over `diagnoses.confidence` for the batch |

The report always sums the full batch denominator (acceptance
criterion #7: recovered + escalated-terminal + stopped = batch
size), never a filtered subset — there is exactly one query path for
this, used by both the demo endpoint and the batch-runner's
end-of-run printout, so there's no way for the demo to show a
different number than what the data actually contains.

---

## 11. Failure Handling

| Failure (product-spec §7) | Where it's handled | Mechanism |
|---|---|---|
| Duplicate/replayed webhook | Ingestion API | `events.id` PK conflict → drop, log, stop (§8) |
| Invalid signature | Ingestion API | Reject before any DB write except a rejection log |
| Malformed/off-schema AI output | Diagnosis Service | Schema validation → `ESCALATED`, no retry-with-looser-prompt (§4) |
| Low AI confidence | Diagnosis Service | Threshold check → `ESCALATED` |
| Executor call errors/times out | Executor | One deterministic retry with backoff; second failure → `ESCALATED` with `reason=executor_failure`, both attempts recorded in `action_executions` |
| Action not yet `API_VERIFIED` at runtime | Allow-list gate + Executor (defense-in-depth) | Never reaches a Razorpay call (§6) |
| Attempt cap / exposure cap reached | Policy Engine | `STOPPED`, reason recorded (§5) |
| No outcome before batch window closes | Batch Runner's close step | Any subscription still in `EXECUTING`/`ESCALATED` when `window_closes_at` passes is transitioned to `NOT_RECOVERED`, audited — never left open (acceptance criterion #1) |

The batch-close step is a component in its own right (part of the
Batch Runner, §1): after replaying all events in a batch file, it
runs one pass over subscriptions still non-terminal and forces the
`NOT_RECOVERED` transition, so "every event reaches a terminal
state" is a guarantee of the runner, not an assumption about
incoming data.

---

## 12. API Endpoints

All under one FastAPI app. Endpoints are grouped by who calls them:
Razorpay/replayer calls ingestion; the demo UI/CLI calls the read
endpoints.

**Ingestion**
- `POST /webhooks/razorpay` — receives one event (real or replayed);
  drives the full flow in §2 synchronously and returns the resulting
  state.

**Batch control** (used by the Batch Runner / demo script)
- `POST /batches` — create a `batch_run` (sets `exposure_cap_total`,
  `window_closes_at`)
- `POST /batches/{id}/close` — run the batch-close step (§11)
- `GET /batches/{id}/metrics` — the §10 metrics report

**Demo / read endpoints**
- `GET /subscriptions?batch_run_id=` — list with current state, for
  the demo's batch overview
- `GET /subscriptions/{id}/audit` — full ordered audit trail for one
  subscription (the "walk one subscription end-to-end" demo beat)
- `GET /escalations?status=open` — the escalation queue
- `POST /escalations/{id}/resolve` — human closes the loop
  (`{resolution: recovered|not_recovered, note}`); writes the
  corresponding terminal-state transition and audit row

No endpoint allows a client to set `subscriptions.current_state`,
`actions.status`, or write directly to `audit_log` — those are only
ever mutated by the State Machine and Action Registry seed step.

---

## 13. Project Folder Structure

```
backend/
  app/
    main.py                    # FastAPI app + route registration
    config.py                  # thresholds, caps, retry policy (env-driven)
    api/
      webhooks.py               # POST /webhooks/razorpay
      batches.py                 # POST /batches, /batches/{id}/close, GET metrics
      subscriptions.py            # GET /subscriptions, /subscriptions/{id}/audit
      escalations.py               # GET/POST /escalations
    core/
      state_machine.py              # legal transitions, single writer of current_state
      clock.py                       # logical-time provider (§8)
      idempotency.py                  # event_id / (sub,event) dedupe helpers
    ai/
      diagnosis.py                     # prompt build, model call, schema validation
      schemas.py                        # diagnosis output schema
    policy/
      gates.py                           # one function per gate (§5)
      engine.py                           # runs gates in order, writes gate_results
    actions/
      registry.py                          # loads/queries the actions table
      executor.py                           # calls razorpay_client, retry-once rule
    razorpay_client/
      client.py                              # the outbound Razorpay boundary (§7)
    audit/
      logger.py                                # single write path for audit_log
    metrics/
      aggregator.py                             # §10 queries
    db/
      models.py                                  # SQLAlchemy models (§3)
      session.py
  scripts/
    seed_actions.py                                # writes/updates the actions table
    replay_batch.py                                 # posts a synthetic_data file through /webhooks in order
  synthetic_data/
    events_batch_01.json                             # includes duplicates, cap-exceeding cases (§9 demo step 2)
  tests/
    test_state_machine.py
    test_policy_gates.py
    test_idempotency.py
    test_diagnosis_schema.py
    test_batch_metrics.py
  pyproject.toml
```

---

## 14. Technology Choices

Only where the choice affects how the MVP is built:

- **Python 3.11+ / FastAPI** — one process, synchronous request
  handling is fine at demo batch scale; no async worker pool needed.
- **SQLite via SQLAlchemy** — zero-ops, file-based, ships in the
  repo, trivially reset between demo runs (`rm` the file). Schema
  (§3) is plain relational, no reason to reach for anything heavier.
- **Pydantic** — schema validation for AI output (§4) and API
  request/response models; the same validation mechanism serves
  both "reject malformed AI output" and "reject malformed webhook
  payloads."
- **LLM: Gemini, structured/tool-call output** — used only by the
  Diagnosis Service (§4), called with the allow-listed action set
  injected per-request rather than baked into a static prompt, so
  the registry (§6) stays the single source of truth for what the
  model is even allowed to recommend. Originally specified as Claude;
  switched to Gemini during implementation for cost reasons (no
  Anthropic API credit available) — see docs/implementation-notes.md
  §8. Only the provider changed; forced function-calling still
  produces the same structured, schema-validated output this line
  originally required.
- **No task queue / no Celery / no Redis** — the Batch Runner
  processes a synthetic file sequentially through the same
  synchronous ingestion path a real webhook would hit; introducing
  async infrastructure here would add failure modes the spec never
  asks the system to handle.
- **No ORM migrations tool for MVP** — `db.models.create_all()` at
  startup is sufficient for a demo database that's reseeded per run;
  Alembic would be over-engineering at this scope.
