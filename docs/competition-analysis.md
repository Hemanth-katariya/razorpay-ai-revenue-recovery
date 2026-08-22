# Competition Analysis

Status: Discovery phase. No track selected. No application code written.

Source of truth: `docs/hackathon.md`. Where this document goes beyond that
source, it is explicitly labeled as **[External Research Needed]**,
**[Assumption]**, or **[Our Inference]**. Nothing here should be read as
an official requirement unless it is directly traceable to
`docs/hackathon.md`.

---

## 1. What Razorpay Is Actually Evaluating

### 1.1 The four stated signals (official)

`docs/hackathon.md` states Razorpay evaluates on four axes:

1. **Problem Taste** — did the builder choose a problem that matters?
2. **Build Quality** — does it run, is it structured, would someone trust it?
3. **AI Judgment** — was AI used where it adds value, and *deliberately
   avoided* where deterministic software is better?
4. **Failure Recovery** — what broke, how was it detected, how was it
   recovered, what safeguards exist?

These four map directly onto four different failure modes a submission can
have, and a submission can fail on any one of them independently of the
other three. A technically excellent build with a weak problem still loses
on Problem Taste. A great idea with brittle code still loses on Build
Quality.

### 1.2 What the application form implies (official, but requires inference)

The form does not just ask for a repo and a video — it explicitly asks
"What broke and how it was fixed" as a **named field**, separate from the
demo. **[Our Inference]** This means failure recovery is not a nice-to-have
buried in the README — it is a first-class deliverable that will be read
and scored on its own. A submission with no honest failure story is
incomplete by the application's own structure, regardless of how well the
happy path works.

The form also asks for "Selected track," "Project name," and "Problem
being solved" as distinct fields before the repo/video. **[Our Inference]**
This suggests the pitch (what problem, why it matters) is evaluated
somewhat independently from the artifact itself — a reviewer likely reads
the problem statement first and forms an expectation, then checks whether
the repo/video deliver on it.

### 1.3 What kind of hire this is (official + inference)

This is a hiring funnel for an **in-person, 6–12 month internship in
Bangalore**, not a hackathon prize. **[Our Inference]** Razorpay is
filtering for people they want to work with for months, in person. This
likely biases evaluation toward:

- Engineering judgment and honesty (the failure-recovery axis) over raw
  cleverness — because that is what predicts whether someone is safe to
  put on production-adjacent systems.
- Scope discipline — a finished, bounded MVP likely reads better than an
  ambitious but half-working system, since it signals how the person will
  behave with a real backlog.
- Communication quality in the 5-minute video, since that is a proxy for
  how the person will represent their work to a team.

**[External Research Needed]** We do not know the actual reviewer
composition (engineers? recruiters? a mix?), how many submissions they
expect, or whether review is single-pass or multi-round. This materially
affects how much we should optimize for "reads well fast" vs. "rewards
deep inspection."

### 1.4 Cross-track requirements as a scoring rubric (official)

The "Cross-Track Requirements" section of `docs/hackathon.md` effectively
functions as a checklist that applies no matter which track is chosen:
real problem, meaningful AI, deterministic engineering where appropriate,
measurable value, reliability (invalid inputs, API failures, timeouts,
duplicates, model failures, uncertainty, partial failures, unexpected
states), safety (explainable/bounded/gated/auditable money actions), and
evaluation on batches/held-out data rather than a single cherry-picked
demo.

**[Our Inference]** Because this checklist is repeated at the cross-track
level after being stated per-track, it is likely the actual rubric
reviewers use, with the per-track sections mainly scoping *what kind* of
problem and *what kind* of metric is expected.

---

## 2. Track-by-Track Analysis

For each track: objective is restated from the official doc; strengths
and weaknesses are our analysis of how well that track's evaluation
criteria can be satisfied convincingly in a short buildathon timeframe.
No track is recommended over another here — this is input to the later
track-comparison phase, not a decision.

### Track 01 — AI Growth & Agentic Commerce

**Objective (official):** grow merchant revenue or make a merchant
transactable by an AI buyer, using Razorpay test-mode APIs.

**Strengths**
- Highest novelty ceiling — agent-to-agent commerce (ACP/AP2/x402, NPCI
  UAP) is a genuinely emerging area, so a good submission here could stand
  out on Problem Taste and differentiation almost by category alone.
- Directly named by Razorpay ("references in-app pilots"), suggesting
  active internal interest — plausible relevance to real roadmap work.
- Clear story potential for a 5-minute video: "an AI agent buys something
  from a merchant" is visually and narratively compelling.

**Weaknesses**
- Least mature evaluation bar of the five tracks — it only asks for an
  audit trail and one gracefully handled failure, with no required
  quantitative metric. **[Our Inference]** This is double-edged: easier to
  satisfy the letter of the requirement, but harder to demonstrate
  "measurable value" convincingly, which is a cross-track requirement.
  Submissions here risk being judged as a demo rather than a measured
  system unless we impose our own metrics.
- Protocols referenced (ACP, AP2, x402, NPCI UAP) are unfamiliar and
  require real research before we can judge feasibility or credibility of
  claiming to use them.
- Risk of becoming a "generic LLM wrapper" (explicitly rejected by
  planning principles) if the "agent" is just an LLM calling a checkout
  API with no bounded decision logic.

### Track 02 — AI Risk Manager

**Objective (official):** detect/verify/auto-respond to one class of loss
(fraud, returns, chargebacks, abuse), strictly defensive.

**Strengths**
- Most rigorous, unambiguous evaluation bar: precision/recall on a
  held-out set is explicit and standard ML practice. Easy to demonstrate
  "honest metrics" and hard to fake — good fit for Build Quality and
  measured-value signals.
- Defensive-only scope keeps the safety story simple (no money is moved,
  only flagged), reducing the surface area for "explainable, bounded,
  gated" concerns.
- Data for this kind of problem (fraud/chargeback patterns) is easier to
  synthesize plausibly than realistic agentic-commerce transaction flows.

**Weaknesses**
- "Anything offense-capable is disqualified" — an explicit hard
  constraint we must design around from day one; any dual-use ambiguity
  in the detector could be read as a violation.
- Precision/recall on synthetic data is easy to game unintentionally
  (data leakage, unrealistic class balance) — the metric can look strong
  while being meaningless. Highest risk of the "honest metrics" bar being
  violated by accident, which directly damages the Build Quality /
  Problem Taste signals if caught.
- Less inherently novel — fraud/chargeback detectors are a well-worn ML
  demo category, so standing out requires strong execution rather than
  category novelty.

### Track 03 — AI Revenue Recovery

**Objective (official):** detect revenue at risk, determine intervention,
execute a bounded recovery workflow (payment failures, checkout
abandonment, failed subscriptions, overdue receivables).

**Strengths**
- Evaluation bar explicitly requires going beyond detection to *measured
  money recovered across a batch* — this is the strongest, most concrete
  tie to "real business value" of any track, and hardest to fake with a
  toy demo.
- Naturally exercises deterministic engineering (stopping rules,
  compliant escalation, audit trail) alongside AI (root-cause reasoning,
  intervention selection), which is exactly the "AI Judgment" signal
  Razorpay says it wants.
- Wide menu of sub-problems (Hinglish voice recovery, mandate retry
  sequencer, promise-to-pay tracker) allows scoping to something concrete
  and bounded rather than open-ended.

**Weaknesses**
- Requires simulating a full loop (detect → decide → act → measure) which
  is more moving parts than a single-purpose classifier — higher build
  risk in a short timeframe.
- "Compliant escalation" implies we need at least a working knowledge of
  what compliant collections/dunning behavior looks like (e.g., contact
  frequency limits) — currently unresearched.
- Money-recovered metrics on synthetic data can look impressive while
  being an artifact of how we constructed the synthetic scenarios;
  requires careful, non-cherry-picked batch design to be credible.

### Track 04 — AI Finance Controller

**Objective (official):** automate one finance-ops loop over books/cash
position, batch of at least 50 synthetic records.

**Strengths**
- Most concrete, boundable scope of all tracks — "close one loop over a
  batch" is a well-defined unit of work with an explicit minimum batch
  size (50), which makes success/failure unambiguous.
- Required evidence (match rate, throughput, honest exceptions) is
  straightforward to report without ambiguity, similar to Track 02's
  precision/recall clarity.
- Reconciliation/matching problems are a natural fit for a mix of
  deterministic rules (exact/fuzzy matching, tolerances) and AI (matching
  ambiguous or unstructured records) — a clean opportunity to show
  deliberate AI-vs-deterministic judgment.

**Weaknesses**
- Least visually/narratively compelling for a 5-minute pitch video —
  "reconciled 50 ledger rows" is harder to make compelling on camera than
  an agent buying something or recovering a failed payment.
- Domain (bookkeeping, settlement, tax-line matching) is less familiar
  territory than payments/checkout flows; more research needed to avoid
  building something naively wrong.
- Risk of being perceived as the "safe, boring" track — could underperform
  on Problem Taste/differentiation even with excellent execution.

### Track 05 — Open Track

**Objective (official):** anything outside the four tracks, held to the
same standards (real problem, meaningful AI, working product, evidence of
value, execution, reliability, technical depth).

**Strengths**
- Freedom to pick a problem we deeply understand, which can produce the
  strongest Problem Taste signal if the problem is genuinely well-chosen
  and Razorpay-relevant.
- No competing directly against submissions clustered around the same
  four prompts — potential differentiation by category.

**Weaknesses**
- Explicitly "not an easier track" — same bar, zero scaffolding. All the
  ambiguity of scope, metric selection, and Razorpay-relevance falls on
  us with no template to react against.
- Highest risk of drifting into "generic LLM wrapper" territory precisely
  because there's no track-specific evaluation bar forcing a measurable
  angle (e.g., no forced precision/recall or money-recovered number).
- Weakest built-in Razorpay relevance unless we deliberately anchor the
  problem to payments/fintech — planning principles list "Strong Razorpay
  relevance" as an explicit objective, and Open Track is the only track
  that doesn't guarantee this by construction.

### Cross-track observation

**[Our Inference]** Tracks 2–4 have an explicit, hard-to-fake quantitative
bar built into the track definition itself (precision/recall; money
recovered; match rate/throughput). Tracks 1 and 5 do not — for those, we
would have to impose our own rigorous metric to satisfy the cross-track
"Measurable Value" and "Evaluation" requirements, since the track
definition alone won't force it.

---

## 3. Additional Research Needed Before Choosing a Track

Grouped by what it would inform.

**Razorpay platform capabilities**
- What Razorpay test-mode APIs actually expose (payments, subscriptions,
  payment links, settlements, webhooks) and their rate limits/sandbox
  data realism — needed for Tracks 1, 3, 4 in particular.
- Whether Razorpay provides any sample/synthetic datasets, or whether we
  are expected to generate our own for all tracks (Track 4 explicitly
  requires ≥50 synthetic records — is "synthetic" self-generated or
  provided?).

**Domain literacy**
- ACP, AP2, x402, and NPCI's UAP — what they actually specify, and
  whether a credible agentic-commerce demo can reference them honestly
  without overclaiming (Track 1).
- What "compliant escalation" means in Indian collections/dunning context
  — relevant regulatory limits on contact frequency, disclosures, etc.
  (Track 3).
- Realistic patterns for fraud/chargeback/return abuse so synthetic data
  isn't naively separable (Track 2).
- Standard reconciliation/settlement/tax-matching workflows at a
  merchant, so Track 4 doesn't misrepresent how finance ops actually work.

**Competition mechanics (unknown, not in `docs/hackathon.md`)**
- Reviewer composition and process (technical review vs. video-only
  triage vs. both).
- Relative weighting across the four signals, if any — or whether they
  are evaluated as independent gates.
- Whether solo vs. team submissions are scored differently, and what team
  size (if any) is expected/allowed.
- Total build time available before the 5 September deadline, and whether
  in-person availability/6-vs-12-month preference has any bearing on
  scoring vs. being purely logistical intake.
- Whether there is any prior year's data (winning submissions, judge
  feedback) we could learn from.

**Our own constraints**
- Solo build vs. any collaborators, and actual hours available between
  now (2026-08-23) and 5 September — needed to right-size scope for
  whichever track is chosen.

None of the above blocks producing this analysis document, but several
items (platform capabilities, dataset expectations, compliance
constraints) should be resolved *before* committing to a track, since they
materially affect feasibility.

---

## 4. Exceptional vs. Generic Submission

| Axis | Generic submission | Exceptional submission |
|---|---|---|
| Problem Taste | Picks a track's example direction verbatim, no reasoning shown | Explains *why* this specific sub-problem matters, with a concrete stakeholder and a plausible cost of inaction |
| AI Judgment | AI does everything, including things a rule or lookup would do better | AI is used only where reasoning/prediction/generation is genuinely needed; deterministic code explicitly handles validation, idempotency, authorization, limits — and the README says why |
| Build Quality | Runs once, on the happy path, on the demo's own data | Runs on a batch/held-out set, has visible structure (not one script), and a stranger could clone and run it from the README |
| Measured Value | One flashy example, no numbers | A real metric (precision/recall, money recovered, match rate) computed over a batch, reported even when it's mediocre |
| Reliability | No handling for bad input, API failure, timeouts, duplicates, or model errors — or handling that's never actually exercised | Each of those failure modes is deliberately triggered and shown being handled, not just theoretically supported |
| Safety (money actions) | An agent can act with no limit, no log, no human-legible reason | Every money-related action is capped, logged with a reason, and (where relevant) requires a gate before executing |
| Failure Recovery | The "what broke" answer is invented after the fact for the form | A real failure occurred during build, was detected via a concrete signal (not "we just noticed"), and the fix and resulting safeguard are traceable in the repo |
| Evaluation Honesty | Metrics computed on the same data used to tune the system, best run reported | Held-out or out-of-sample evaluation, failures/exceptions reported alongside successes, no cherry-picking |
| Demo | Walkthrough of features in UI order | Narrative built around the business problem, showing the metric moving and at least one failure being handled live |

**[Our Inference]** The single biggest differentiator across this rubric
is *evidence*: a generic submission asserts these qualities in prose; an
exceptional one shows the artifact (a number, a log line, a rejected
transaction, a commit) that proves it. This should guide the eventual
architecture and evaluation-strategy phases — every claim we plan to make
in the video should have a corresponding artifact in the repo.

---

## 5. Status

This document completes the **Competition Analysis** phase only.

No track has been selected. No product idea has been chosen. No
application code exists. Next phases per `CLAUDE.md` are External
Research, then Track Comparison — both of which depend on resolving the
open items in Section 3.
