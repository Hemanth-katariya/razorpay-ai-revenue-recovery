# Razorpay AI Buildathon

## Official Competition

Razorpay AI Buildathon: Build. Show. Get hired.

A student-only program to discover and hire the next generation
of AI Builder Interns.

### Internship

- Role: AI Builder Intern
- Duration: 6 or 12 months
- Location: In-person, Bangalore
- Start: September
- Monthly stipend: ₹75,000

### Hiring Process

There is no traditional resume screening, aptitude test, or group
discussion as the primary selection mechanism.

The submission is evaluated through the work produced.

The application asks for:

- Full name
- College
- Graduation year
- In-person availability from September
- 6 or 12 month preference
- Resume
- Selected track
- Project name
- Problem being solved
- Public GitHub repository
- 5-minute pitch video
- What broke and how it was fixed

Applications close: 5 September.

---

# What Razorpay Says It Values

Razorpay emphasizes four major signals.

## 1. Problem Taste

Did the builder choose a problem that actually matters?

## 2. Build Quality

Does the system run?

Is it structured?

Would someone trust the implementation?

## 3. AI Judgment

Did the builder use AI where it provides meaningful value?

Did they deliberately avoid AI where deterministic software
would be better?

## 4. Failure Recovery

What broke?

How did the builder detect it?

How did they recover?

What safeguards were implemented?

The final submission should therefore demonstrate not only
functionality but engineering judgment.

---

# Track 01: AI Growth & Agentic Commerce

## Objective

Grow merchant revenue and make merchants transactable by AI buyers.

Build an agent that either:

1. Grows revenue for a merchant using Razorpay test-mode APIs, or
2. Makes a merchant transactable by an AI buyer end-to-end.

## Why Razorpay Highlights This

NPCI's UAP and global protocol developments such as ACP, AP2,
and x402 are making agent-to-agent commerce an important emerging
problem.

Razorpay also references in-app pilots in this area.

## Example Directions

- Conversational in-app checkout
- Agent-readable catalog
- Upsell and cross-sell agent
- Campaign orchestrator

## Evaluation Bar

Every money action must be:

- Explainable
- Bounded
- Gated

The submission should demonstrate:

- Audit trail
- At least one failure handled gracefully

---

# Track 02: AI Risk Manager

## Objective

Help merchants avoid losses caused by:

- Fraud
- Returns
- Chargebacks
- Other relevant abuse/loss mechanisms

Build a working detector, verifier, or auto-responder for one
class of loss.

## Required Evidence

The system must have measured:

- Precision
- Recall

using a held-out test set.

## Example Directions

- Chargeback evidence responder
- Return-risk scorer
- Fraud-spike detector
- Abuse-ring sentinel

## Evaluation Bar

Metrics must be honest.

The submission should include:

- Precision
- Recall
- False-positive cost

The project must be strictly defensive.

Anything that is offense-capable is disqualified.

---

# Track 03: AI Revenue Recovery

## Objective

Find revenue that is at risk and recover it.

Build an agent that:

1. Detects revenue at risk
2. Determines the appropriate intervention
3. Executes a bounded recovery workflow

Potential problems include:

- Payment failures
- Checkout abandonment
- Failed subscriptions
- Overdue receivables

## Example Directions

- Payment degradation → root cause → recovery action
- Checkout drop-off recovery
- Failed-subscription recovery
- B2B receivables chaser
- Mandate retry sequencer
- Hinglish voice recovery
- Promise-to-pay tracker

## Evaluation Bar

The system must go beyond identifying the problem.

It should demonstrate:

- Measured money recovered across a batch
- Compliant escalation
- Stopping rules
- Audit trail

The key outcome is actual recovery rather than merely prediction
or detection.

---

# Track 04: AI Finance Controller

## Objective

Automate one finance-operations loop involving books or cash position.

Build an agent that closes one finance-ops loop across a batch
containing at least 50 synthetic records.

## Example Directions

- Multi-source reconciliation
- Settlement Q&A agent
- Forward cash forecaster
- Tax-line matcher

## Required Evidence

Report:

- Match rate / accuracy
- Throughput
- Exceptions that could not be resolved

## Evaluation Bar

The project must demonstrate:

- Meaningful batch processing
- Measured accuracy
- Honest exception reporting

A single cherry-picked successful match is not sufficient.

---

# Track 05: Open Track

## Objective

Build something that does not fit the predefined tracks.

The project can address any domain, workflow, or user.

However, it must still demonstrate:

- A real problem
- Meaningful AI usage
- Working product
- Evidence of value
- Strong execution
- Reliability
- Technical depth

## Example Directions

- A problem the builder deeply understands
- A novel workflow
- Something Razorpay did not explicitly suggest

Open Track is not an easier track.

The same standards apply.

---

# Cross-Track Requirements

Regardless of track, a strong submission should demonstrate:

## Real Problem

The problem should have meaningful business or user value.

## Meaningful AI

AI should perform work that benefits from intelligence,
reasoning, prediction, classification, generation, or agentic
decision-making.

AI should not be added merely for appearance.

## Deterministic Engineering

Use deterministic software where deterministic software is
more reliable than AI.

Examples may include:

- Payment state validation
- Idempotency
- Authorization
- Policy enforcement
- Hard limits
- Transaction validation
- Data integrity

## Measurable Value

The submission should define quantitative metrics appropriate
to its selected track.

## Reliability

The system should explicitly handle:

- Invalid inputs
- API failures
- Timeouts
- Duplicate operations
- Model failures
- Uncertainty
- Partial failures
- Unexpected states

## Safety

Money-related actions should be:

- Explainable
- Bounded
- Gated
- Auditable

## Evaluation

Do not rely only on one successful demo example.

Use batches, held-out data, synthetic data, or other appropriate
evaluation methodology.

Report failures and unresolved cases honestly.

## Demonstration

The final submission requires:

- Public GitHub repository
- 5-minute pitch video
- Architecture explanation
- Explanation of what broke and how it was fixed

The demo should make the business value and technical depth
easy to understand.

---

# Strategic Objective

Our goal is not to build the flashiest AI demo.

Our goal is to identify and build the project that provides
the strongest combined signal across:

- Problem selection
- Razorpay relevance
- AI judgment
- Technical depth
- Measurable impact
- Differentiation
- Reliability
- Failure recovery
- Demo quality
- Engineering quality
- Interview defensibility