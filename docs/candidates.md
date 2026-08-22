# Candidate Product Directions

Status: Idea generation phase. No track selected. No product chosen. No
application code written.

This document evaluates the four predefined tracks (Track 05 / Open Track
is out of scope for this pass, since it has no forced evaluation bar and
per `docs/research.md` should only be considered if nothing here is
materially stronger). For each track, exactly one candidate direction is
proposed — the one that appears strongest given the evidence already
gathered in `docs/hackathon.md`, `docs/competition-analysis.md`, and
`docs/research.md`. No track winner is chosen here.

Sourcing key used throughout:

- **[Official]** — directly traceable to `docs/hackathon.md`.
- **[Verified research]** — directly traceable to `docs/research.md`
  (external, source-cited there).
- **[Assumption]** — not established by either document; something we
  would need to validate before implementation.

Where a candidate's viability depends on an unverified API capability,
that is flagged explicitly rather than assumed away.

---

## Track 01 — AI Growth & Agentic Commerce

### Candidate: Agent-Readable Storefront + Bounded Shopping Agent

1. **Product name (working):** StoreFront-Agent (placeholder — not final)

2. **Problem being solved:** A merchant's catalog and checkout are built
   for human browsing (web UI, clicks, visual layout). An AI buying agent
   cannot transact against that merchant today without either screen-
   scraping or a custom one-off integration. There is no structured,
   policy-safe way for an autonomous agent to browse, decide, and pay.

3. **Target user:** A merchant who wants to be reachable by AI shopping
   agents (the emerging "agentic commerce" buyer channel), represented in
   the demo by our own reference AI buyer agent.

4. **Core end-to-end workflow:** Merchant catalog exposed as a structured,
   machine-readable schema (items, price, stock, constraints) → buyer
   agent receives a natural-language goal (e.g. "restock office coffee
   under ₹2,000") → agent reasons over the catalog and proposes a
   purchase → deterministic policy gate checks budget cap, allowed
   category, quantity limits → if approved, order is created and paid via
   Razorpay test-mode APIs → outcome (success/decline/out-of-stock) is
   logged → audit trail entry produced for every attempted purchase,
   approved or blocked.

5. **Where AI genuinely adds value:** Interpreting an ambiguous natural-
   language buying goal against an unstructured-ish catalog, choosing
   among substitutable items, and deciding *whether and what* to buy under
   incomplete information (e.g. partial stock, price close to budget
   limit). This is a judgment/reasoning task, not a lookup.

6. **Where deterministic logic should be used:** The purchase policy gate
   (budget cap, category allow-list, max order count, duplicate-order
   prevention), payment execution itself, idempotency handling on order
   creation, and all audit logging. The agent should never be able to
   directly call an unbounded "pay" action — per **[Verified research]**
   (`docs/research.md` §2, §10), AI reasoning must sit behind a
   deterministic policy/authorization layer before any Razorpay operation.

7. **Razorpay/test-mode dependency:** Order creation and payment capture
   in Razorpay Test Mode **[Official]**; exact mechanics of order/payment-
   link creation suitable for an agent-driven (non-human-clicking) flow
   are **[Assumption — needs validation]**, since `docs/research.md` §5
   explicitly flags that no ready-made Razorpay sandbox integration for
   any agentic-commerce protocol (ACP/AP2/x402) should be assumed.

8. **Measurable success metric:** Over a batch of N simulated buying goals
   (e.g. 50+), report: % resulting in a correctly bounded purchase decision
   (approved when it should be, blocked when it should be), average
   decision latency, and $ value transacted vs. policy limit never
   exceeded (0 violations required).

9. **Demonstrable failure mode:** Agent attempts a purchase exceeding the
   budget cap or a duplicate purchase attempt (e.g. webhook/retry causing
   a second order) — system must reject/dedupe and log why, without
   silently failing or double-charging.

10. **Biggest technical risk:** There is no verified, ready-made Razorpay
    mechanism for an *agent-initiated* (as opposed to human-in-checkout)
    purchase flow. We would likely have to build our own thin
    "agent-readable" layer on top of standard Order/Payment APIs, and the
    line between "genuine Razorpay integration" and "our own wrapper
    protocol" must be stated honestly — overclaiming protocol conformance
    (ACP/AP2/x402) would be a credibility risk.

11. **Why it could stand out:** Per `docs/competition-analysis.md` §2
    (Track 01 analysis), this category has the highest novelty ceiling
    and is explicitly named as an area of active Razorpay interest. "An AI
    agent buys something, under an enforced budget, and we can prove it
    never overspent" is a strong, visual 5-minute story that also directly
    answers the track's stated objective ("make a merchant transactable by
    an AI buyer end-to-end").

12. **Why it might fail to stand out:** Track 01 has the weakest forced
    quantitative bar of the four tracks (`docs/competition-analysis.md`
    §2 cross-track observation) — only an audit trail and one graceful
    failure are officially required. Without our own imposed rigorous
    metric, a reviewer could reasonably read this as "a demo," not "a
    measured system," which undercuts Problem Taste and Measurable Value
    even if the engineering is solid. There is also real risk of sliding
    into "an LLM calling a checkout API" if the policy layer is not
    clearly the thing doing the heavy lifting.

---

## Track 02 — AI Risk Manager

### Candidate: Chargeback/Dispute Evidence Assistant

1. **Product name (working):** DisputeGuard (placeholder)

2. **Problem being solved:** Merchants receiving a payment dispute
   (chargeback) must decide whether to contest it and, if so, assemble
   supporting evidence quickly — a slow or weak response forfeits
   otherwise-winnable disputes.

3. **Target user:** A merchant's operations/finance staff who currently
   triage disputes manually.

4. **Core end-to-end workflow:** New dispute event ingested (fetched via
   Razorpay Disputes API) → classifier scores dispute as winnable /
   not-winnable with a confidence level, using transaction + customer
   history features → for disputes above a confidence threshold, an AI
   drafts a structured evidence response (delivery proof, communication
   log, matching transaction record) → human-legible recommendation +
   draft is surfaced for a gate (never auto-submitted) → on approval, the
   contest is submitted via the Disputes API in test mode → outcome and
   reasoning are logged to an audit trail.

5. **Where AI genuinely adds value:** Scoring dispute winnability from
   noisy, partial signals (transaction metadata, prior customer behavior,
   dispute reason code) and drafting a coherent, evidence-specific written
   response — both require judgment/generation, not lookup.

6. **Where deterministic logic should be used:** Confidence thresholding,
   the human-approval gate before any contest is filed, evidence-document
   assembly/validation (required fields present before submission), and
   all audit logging. The classifier's precision/recall must be computed
   deterministically over a genuinely held-out split, not inferred by the
   model itself.

7. **Razorpay/test-mode dependency:** Disputes API — fetch disputes, fetch
   individual dispute, accept dispute, contest dispute with evidence —
   is **[Verified research]** (`docs/research.md` §6, sourced to Razorpay
   API docs). This is the most concretely API-verified candidate among
   all four tracks.

8. **Measurable success metric:** Precision and recall of the
   winnable/not-winnable classifier on a held-out synthetic dispute set
   (this is an **[Official]** requirement for this track, not optional),
   plus false-positive cost (cost of contesting a dispute that was never
   winnable — wasted effort/fees).

9. **Demonstrable failure mode:** A dispute with ambiguous or
   contradictory signals (e.g. conflicting delivery records) should
   produce a low-confidence "escalate to human, do not auto-recommend
   contest" outcome rather than a false-confident wrong call — this is
   the failure mode to deliberately construct and show being handled.

10. **Biggest technical risk:** Track 02's own evaluation bar is the
    hardest to fake honestly (`docs/competition-analysis.md` §2, Track 02
    weaknesses): synthetic dispute data is easy to make unintentionally
    separable (data leakage, unrealistic class balance), which would
    produce impressive-looking precision/recall that collapses under
    scrutiny. Constructing a *credible*, non-trivially-separable synthetic
    dataset is real, non-trivial work, not a formality.

11. **Why it could stand out:** Strongest, least ambiguous tie to a
    verified Razorpay API of any candidate here (Disputes API is fully
    documented and matches the workflow one-to-one). The "strictly
    defensive" requirement is easy to satisfy honestly since the system
    only ever recommends/drafts, never moves money, and a human gate sits
    before every contest submission.

12. **Why it might fail to stand out:** Fraud/chargeback detection is,
    per `docs/competition-analysis.md` §2, "a well-worn ML demo category" —
    novelty must come from execution quality and dataset honesty, not
    category choice. If the synthetic dataset is not built carefully, the
    headline metric could be simultaneously "official-requirement-
    satisfying" and unconvincing to a skeptical reviewer.

---

## Track 03 — AI Revenue Recovery

### Candidate: Failed-Subscription Recovery Agent

1. **Product name (working):** RecoverFlow (placeholder)

2. **Problem being solved:** Recurring-payment failures (expired card,
   insufficient funds, bank decline) silently churn subscribers unless
   someone diagnoses the cause and intervenes — most merchants either
   retry blindly or do nothing.

3. **Target user:** A subscription merchant's revenue/billing operations
   owner.

4. **Core end-to-end workflow:** Subscription charge fails → webhook
   received (`subscription.pending` / eventual `subscription.halted`) →
   signature verified, event deduplicated via idempotency key → AI
   diagnoses likely root cause from decline reason + payment history →
   AI selects an intervention (retry now / retry with backoff / notify
   customer to update payment method / offer grace period) → deterministic
   policy gate enforces stopping rules (max retries, contact-frequency
   limit, no action if subscription already cancelled) → bounded recovery
   action executed via Razorpay subscription APIs in test mode → outcome
   observed (subscription re-activated or not) → recovered revenue
   computed and logged with full audit trail.

5. **Where AI genuinely adds value:** Diagnosing *why* a charge failed
   from partial/noisy signals and choosing the fitting intervention
   (a hard-decline card is not the same problem as an insufficient-funds
   soft-decline, and each merits a different action) — a reasoning task
   over ambiguous evidence, not a fixed lookup table in most real cases.

6. **Where deterministic logic should be used:** Idempotent webhook
   processing (per **[Verified research]**, `docs/research.md` §4,
   Razorpay explicitly warns of duplicate/out-of-order webhook delivery
   and provides `x-razorpay-event-id` for dedup), retry/stopping-rule
   limits, escalation-frequency compliance, and the recovered-revenue
   calculation itself (must not be estimated by the model).

7. **Razorpay/test-mode dependency:** Subscription lifecycle simulation
   (successful/failed charge simulation, pending → halted transition after
   exhausted retries) and the associated webhook events
   (`subscription.charged`, `.pending`, `.halted`, `.activated`) are
   **[Verified research]** (`docs/research.md` §3, sourced to Razorpay's
   subscription test-mode docs) — the most concretely evidenced
   Razorpay-workflow fit of any candidate in this document.

8. **Measurable success metric:** Total/percentage of at-risk MRR
   recovered across a batch of simulated failing subscriptions — this is
   an **[Official]** required metric for this track — plus number of
   stopping-rule triggers and count of compliant vs. blocked escalation
   attempts.

9. **Demonstrable failure mode:** A subscription that has already
   exhausted its retry budget must be recognized as "halted, do not
   retry further" rather than looping — deliberately construct this case
   and show the stopping rule firing instead of a runaway retry loop.

10. **Biggest technical risk:** Exactly which recovery actions are
    executable purely through Razorpay APIs versus requiring
    Dashboard/customer-side interaction is **[Assumption — needs
    validation]** per `docs/research.md` §3 and §7. If key interventions
    (e.g. sending an update-payment-method link) turn out to require
    manual/dashboard steps, the "end-to-end automated" story weakens.

11. **Why it could stand out:** Per `docs/research.md` §11 and
    `docs/competition-analysis.md` §2, this is the candidate with the
    strongest combined technical fit (verified subscription/webhook
    lifecycle), the hardest-to-fake official metric (money recovered,
    not just detected), and a workflow that naturally forces the
    AI-reasoning-behind-a-deterministic-gate architecture Razorpay's own
    framing rewards.

12. **Why it might fail to stand out:** It is the most moving-parts
    candidate here (detect → diagnose → decide → gate → act → measure),
    which is higher build risk in a short window; a shallow implementation
    that skips the diagnosis step and just "retries with a message" would
    collapse most of the claimed AI value. "Compliant escalation" also
    implies collections/dunning norms (contact-frequency limits, etc.)
    that are currently unresearched — an invented compliance rule could
    look reasonable but be simply wrong.

---

## Track 04 — AI Finance Controller

### Candidate: Multi-Source Settlement Reconciliation Agent

1. **Product name (working):** ReconLoop (placeholder)

2. **Problem being solved:** Merchants must match Razorpay settlement
   records against their own internal ledger/bank statement to confirm
   what was actually paid out; mismatches (partial settlements, combined
   payouts, fee deductions, delayed entries) are currently found manually
   line-by-line.

3. **Target user:** A merchant's finance/accounting staff performing
   month-end or daily settlement reconciliation.

4. **Core end-to-end workflow:** Ingest a batch (≥50 records, per the
   track's official minimum) of settlement records and a synthetic
   counterpart ledger/bank-statement dataset → deterministic exact-match
   pass on unambiguous fields (amount + reference ID) → remaining
   unmatched records passed to an AI matching step that reasons over
   ambiguous cases (split settlements, inconsistent narration text,
   rounding/fee differences) and proposes a match with a rationale →
   proposed AI matches above a confidence threshold are accepted, others
   flagged as exceptions for human review → final report: match rate,
   throughput, and an honest list of unresolved exceptions.

5. **Where AI genuinely adds value:** Resolving the ambiguous long tail —
   records that don't match on exact keys because of free-text narration
   differences, combined/split settlement amounts, or fee adjustments —
   where pattern-matching/reasoning over noisy text and numbers helps.

6. **Where deterministic logic should be used:** The first-pass exact/
   fuzzy-key matching (this should resolve the majority of records
   without needing AI at all), tolerance thresholds for what counts as a
   "match," and the match-rate/throughput calculation and exception
   reporting themselves — these must be computed deterministically, not
   asserted by the model.

7. **Razorpay/test-mode dependency:** **[Assumption — needs validation]**.
   Unlike Tracks 02 and 03, `docs/research.md` §8 explicitly states the
   exact settlement/reconciliation API operations available in Test Mode
   have *not* been verified. This candidate's Razorpay-specific grounding
   is currently the weakest of the three presented so far and must be
   confirmed before implementation, not assumed.

8. **Measurable success metric:** Match rate (% of records correctly
   reconciled), throughput (records processed per unit time), and count
   plus nature of unresolved exceptions — all **[Official]** required
   evidence for this track, over a batch of at least 50 synthetic
   records (**[Official]** minimum).

9. **Demonstrable failure mode:** A genuinely ambiguous record (e.g. one
   settlement amount that could plausibly match either of two ledger
   entries) should be reported as an honest exception rather than the
   AI guessing confidently and silently mismatching — construct this case
   deliberately and show it flagged, not resolved incorrectly.

10. **Biggest technical risk:** The Razorpay-side API grounding is
    unverified (see #7). There is also a subtler risk: if the exact-match
    deterministic layer alone resolves the large majority of a naively
    constructed synthetic batch, the AI step may end up doing very little
    real work — the synthetic data has to be deliberately designed with a
    non-trivial ambiguous tail, or the "AI Judgment" signal becomes thin.

11. **Why it could stand out:** Most concretely boundable scope of any
    candidate in this document — "reconcile a batch, report match rate/
    throughput/exceptions" is unambiguous to build and unambiguous to
    grade, and it is a clean, legible example of deterministic-vs-AI
    division of labor (the two things the cross-track rubric explicitly
    asks to see, per `docs/hackathon.md` "Deterministic Engineering").

12. **Why it might fail to stand out:** Per `docs/competition-analysis.md`
    §2 (Track 04 weaknesses), this is the least visually/narratively
    compelling track for a 5-minute video — "N settlement rows matched"
    is a harder story to make compelling than an agent buying something
    or money being recovered live. Combined with the unverified API
    grounding (#7/#10), this candidate currently carries the most
    open risk of the four presented, even though its scope is the
    cleanest.

---

## Summary Table (for reference only — not a ranking decision)

| Track | Candidate | Strongest evidence tie | Weakest point |
|---|---|---|---|
| 01 Growth & Agentic Commerce | Agent-Readable Storefront + Bounded Shopping Agent | High novelty, direct fit to stated track objective | No forced metric; no verified agent-checkout API pattern |
| 02 Risk Manager | Chargeback/Dispute Evidence Assistant | Disputes API fully verified end-to-end | Credible held-out dataset construction is hard, easy to get wrong unintentionally |
| 03 Revenue Recovery | Failed-Subscription Recovery Agent | Subscription + webhook lifecycle fully verified; official money-recovered metric | Most moving parts; compliant-escalation norms unresearched |
| 04 Finance Controller | Multi-Source Settlement Reconciliation Agent | Cleanest, most boundable scope; forced match-rate/throughput metric | Settlement API operations in Test Mode unverified; weakest demo appeal |

No track or candidate is selected by this document. This is input to the
next phase (Idea Evaluation → Track and Product Selection), which per
`CLAUDE.md` requires explicit review before proceeding.
