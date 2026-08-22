# Track and Product Decision

Status: **DECIDED.** Track and candidate are locked in.

This decision was made by comparing exactly two candidates from
`docs/candidates.md` against the requirements in `docs/hackathon.md`,
using evidence already gathered in `docs/competition-analysis.md` and
`docs/research.md`. No new research was performed to reach it.

---

## Selected Track

**Track 03 — AI Revenue Recovery**

## Selected Candidate

**Failed-Subscription Recovery Agent** (working name: RecoverFlow)

Full candidate description: `docs/candidates.md`, Track 03 section.

---

## Why Track 03 Won Over Track 01

Track 01 (Agent-Readable Storefront + Bounded Shopping Agent) and Track 03
were compared head-to-head across 13 criteria (problem taste, build
quality, meaningful AI usage, measurable value, Razorpay integration
feasibility, demo feasibility, failure recovery, explainability/bounded/
gated actions, differentiation, 5-minute evidence strength,
implementation risk, LLM-wrapper risk, and unverified-capability risk).

Track 03 won on 10 of 13 criteria. The decisive factors:

- **Verified Razorpay mechanics.** Track 03's core lifecycle (subscription
  charge failure → `subscription.pending` → `subscription.halted` after
  exhausted retries, with corresponding webhook events) is directly
  **[Verified research]** in `docs/research.md` §3–§4, sourced to
  Razorpay's own documentation. Track 01's core mechanic — an AI agent
  initiating a purchase — has no verified Razorpay sandbox integration
  for any agentic-commerce pattern; `docs/research.md` §5 and §9
  explicitly flag this as unvalidated.
- **Forced, official quantitative bar.** Track 03 requires "measured
  money recovered across a batch" as an official evaluation criterion
  (`docs/hackathon.md`). Track 01 has no forced metric, meaning
  Measurable Value would have to be self-imposed and could still read as
  a demo rather than a measured system.
- **Deterministic-gate-behind-AI architecture is structurally forced.**
  Idempotent webhook handling, retry stopping rules, and escalation
  limits are not optional add-ons for Track 03 — they are required to
  satisfy the track's own official bar, which naturally produces the
  AI-reasoning-behind-deterministic-policy architecture the buildathon
  rewards. Track 01 could satisfy its (lighter) official bar with a much
  thinner deterministic layer.
- Track 01's genuine advantage — higher category novelty and explicit
  Razorpay interest in agentic commerce — was real but, per the
  comparison instructions, not sufficient on its own against a candidate
  with stronger verified evidence and a harder-to-fake metric.

## Weighted Comparison

| Track | Weighted Score |
|---|---|
| Track 03 — AI Revenue Recovery | **7.76 / 10** |
| Track 01 — AI Growth & Agentic Commerce | 5.94 / 10 |

Weights used were our own judgment (not an official Razorpay rubric —
the actual reviewer weighting is unknown per `docs/research.md` §1.3),
biased toward the four official signals (Problem Taste, Build Quality,
AI Judgment, Failure Recovery) plus each track's own forced evaluation
bar.

---

## Key Strengths of the Selected Candidate

- Subscription and webhook lifecycle needed for the core loop is already
  verified against Razorpay documentation, not assumed.
- The official required metric (money recovered across a batch) is
  concrete, hard to fake, and directly tied to real business value.
- Naturally exercises deterministic engineering (idempotent webhook
  processing, stopping rules, escalation limits, audit trail) alongside
  genuine AI reasoning (root-cause diagnosis, intervention selection) —
  a clean demonstration of "AI Judgment" as Razorpay defines it.
- Rich, realistic failure modes exist by construction (duplicate/
  out-of-order webhooks, exhausted retries) that map directly to the
  application's required "what broke and how it was fixed" narrative.

## Known Risks

- **Most moving parts of any candidate considered:** detect → diagnose →
  decide → gate → act → measure is a longer pipeline than a single-
  purpose classifier, raising build risk within the available time.
- **Compliant escalation is currently unresearched.** What counts as
  compliant contact-frequency/collections behavior in this context is
  not yet known; an invented rule could look reasonable but be wrong.
- **Weaker category differentiation.** Subscription dunning/recovery is
  a well-known problem space; standing out depends on execution quality
  (diagnosis accuracy, gating rigor, honest metrics) rather than
  novelty of category.
- **Synthetic-batch credibility.** Money-recovered figures on synthetic
  data can look impressive while being an artifact of how the batch was
  constructed; the batch must be built to avoid this, not just to
  produce a good headline number.

## The Single Remaining Feasibility Question

**Which recovery interventions can be executed programmatically through
Razorpay APIs in Test Mode, versus which require Dashboard or
customer-side interaction?**

This is currently unverified (`docs/research.md` §3, §7 flag it
explicitly as "Needs Validation"). It is the single biggest open item
that could affect the shape of the eventual product: if only a narrow
set of interventions (e.g., retrying a charge) are truly API-driven and
others (e.g., prompting a customer to update their payment method)
require manual or dashboard-side steps, the "automated, bounded
recovery workflow" must be scoped around whatever is actually
programmatically executable. This question must be resolved before
architecture and implementation planning begin.

---

## Status

Track and candidate selection is complete. Per `CLAUDE.md`, the next
phase is **Product Specification**, followed by Architecture. Neither
has been started. No application code exists.
