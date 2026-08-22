# External Research

Status: Research completed for track selection.

This document is NOT an official Razorpay specification.

Information is classified as:

- [Verified] Directly supported by external documentation.
- [Inference] Our interpretation of verified information.
- [Needs Validation] Something we must test or verify before relying on it.

The official hackathon requirements remain in:
docs/hackathon.md

---

# 1. Razorpay Test Mode

[Verified]

Razorpay provides a Test Mode sandbox separate from Live Mode.

Test Mode:
- Uses separate test API keys.
- Does not process real money.
- Test entities do not affect the Live environment.
- Can be used for development and integration testing.

Source:
https://razorpay.com/docs/payments/dashboard/test-live-modes/

Razorpay's current quickstart also states that Test Mode can be
used before KYC completion, while KYC is required for Live Mode.

Source:
https://razorpay.com/docs/payments/quickstart/

[Inference]

The hackathon can therefore demonstrate meaningful payment workflows
without moving real money.

[Needs Validation]

Before committing to a product, we must verify the exact Test Mode
operations required by that product.

---

# 2. Payments

[Verified]

Razorpay provides Payment APIs for retrieving payment information
and capturing authorized payments.

The Payments API itself is not the mechanism for collecting a
customer payment. Payment collection is performed through Razorpay
products such as Checkout.

Source:
https://razorpay.com/docs/api/payments/

[Inference]

For an AI system involving payment decisions, we should separate:

AI reasoning
→ policy validation
→ deterministic Razorpay operation

The LLM should not directly control unrestricted payment operations.

---

# 3. Subscriptions

[Verified]

Razorpay provides Subscription APIs including:

- Create Plan
- Create Subscription
- Fetch Subscription
- Cancel Subscription
- Update Subscription
- Pause Subscription
- Resume Subscription
- Fetch Subscription Invoices

Source:
https://razorpay.com/docs/api/payments/subscriptions/

Razorpay documents a Test Mode workflow for simulating subsequent
subscription charges.

Test Mode can simulate successful and failed subscription charges.

Repeated failures can move a subscription from active to pending
and eventually to halted after retries are exhausted.

Relevant webhook events include:

- subscription.charged
- subscription.pending
- subscription.halted
- subscription.activated

Source:
https://razorpay.com/docs/payments/subscriptions/test/

[Inference]

This makes subscription-payment recovery a particularly promising
candidate for Track 03 because the payment-failure lifecycle can be
demonstrated in a controlled environment.

[Needs Validation]

We must verify exactly which recovery actions can be executed through
the available APIs and which require Dashboard/customer interaction.

---

# 4. Webhooks

[Verified]

Razorpay provides asynchronous webhooks for events involving
payments, orders, settlements, disputes and other products.

Examples include:

- payment.authorized
- payment.failed
- order.paid

Source:
https://razorpay.com/docs/webhooks/

[Verified]

Razorpay recommends webhook-based automation and API verification
where immediate confirmation is required.

Webhook delivery is asynchronous.

Source:
https://razorpay.com/docs/webhooks/

[Verified]

Webhook delivery can contain duplicate events.

Razorpay provides the `x-razorpay-event-id` identifier so applications
can implement idempotent processing.

Webhook events may also arrive out of order.

Source:
https://razorpay.com/docs/webhooks/validate-test/

[Inference]

A production-quality architecture should therefore include:

Webhook
→ signature verification
→ idempotency check
→ event processing
→ AI decision
→ policy gate
→ action
→ verification
→ audit log

This is a potentially strong engineering signal for the buildathon.

---

# 5. Track 01: AI Growth & Agentic Commerce

[Verified from hackathon brief]

Track 01 asks builders to either:

- Grow merchant revenue using Razorpay test-mode APIs, or
- Make a merchant transactable by an AI buyer end-to-end.

The official examples include:

- Conversational in-app checkout
- Agent-readable catalog
- Upsell/cross-sell agent
- Campaign orchestrator

The official bar requires every money action to be:

- Explainable
- Bounded
- Gated

It also requires an audit trail and a gracefully handled failure.

Source:
docs/hackathon.md

[External context]

Agentic commerce protocols such as ACP, AP2 and x402 are relevant
to the broader ecosystem.

[Inference]

Track 01 potentially has a very high differentiation ceiling because
the problem involves AI agents interacting with commerce and payments.

[Needs Validation]

We must not assume that any external agentic-commerce protocol has
a ready-to-use Razorpay sandbox integration.

If we use a protocol-inspired design rather than a real integration,
the distinction must be explicit in the final submission.

---

# 6. Track 02: AI Risk Manager

[Verified from hackathon brief]

Track 02 requires a working detector, verifier or auto-responder
for one class of financial loss.

The official evaluation bar requires:

- Precision
- Recall
- Held-out test set
- False-positive cost

Example directions include:

- Chargeback evidence responder
- Return-risk scorer
- Fraud-spike detector
- Abuse-ring sentinel

Source:
docs/hackathon.md

[Verified]

Razorpay provides Disputes APIs including:

- Fetch disputes
- Fetch individual dispute
- Accept dispute
- Contest dispute with explanations and supporting documents

Source:
https://razorpay.com/docs/api/disputes/

[Inference]

A dispute-analysis or evidence-assistance system could therefore
have meaningful Razorpay relevance.

[Risk]

Track 02 requires a credible evaluation dataset.

A demo using only a handful of manually selected examples would
not satisfy the spirit of the track's evaluation requirement.

---

# 7. Track 03: AI Revenue Recovery

[Verified from hackathon brief]

Track 03 requires an agent that:

1. Detects revenue at risk.
2. Determines the appropriate intervention.
3. Executes a bounded recovery workflow.

The official examples include:

- Payment degradation → root cause → recovery action
- Checkout drop-off recovery
- Failed-subscription recovery
- B2B receivables chaser
- Mandate retry sequencer
- Hinglish voice recovery
- Promise-to-pay tracker

The official evaluation bar requires:

- Measured money recovered across a batch
- Compliant escalation
- Stopping rules
- Audit trail

Source:
docs/hackathon.md

[Verified]

Razorpay's Test Mode supports subscription charge-failure simulation.

Razorpay documents failed recurring charges moving subscriptions into
pending and eventually halted states after retries are exhausted.

Source:
https://razorpay.com/docs/payments/subscriptions/test/

[Inference]

Track 03 currently has a strong technical fit with Razorpay's
test environment.

A potential architecture is:

Payment/subscription event
→ detect revenue risk
→ diagnose cause
→ choose intervention
→ policy gate
→ bounded recovery action
→ observe outcome
→ calculate recovered revenue
→ audit

[Needs Validation]

We must verify the exact actions that can be automated through
Razorpay APIs versus actions that require customer interaction.

[Current Assessment]

Track 03 is currently the strongest risk-adjusted candidate.

This is our inference, NOT a Razorpay requirement.

---

# 8. Track 04: AI Finance Controller

[Verified from hackathon brief]

Track 04 requires an agent that closes one finance-operations loop
across at least 50 synthetic records.

The submission must report:

- Match rate
- Exceptions
- Throughput/accuracy evidence

Examples include:

- Multi-source reconciliation
- Settlement Q&A
- Forward cash forecasting
- Tax-line matching

Source:
docs/hackathon.md

[Needs Validation]

Before selecting this track, verify the exact settlement/reconciliation
API operations available in Test Mode for the intended workflow.

[Inference]

This track offers strong quantitative evaluation potential because
batch reconciliation naturally produces measurable matches and
exceptions.

The main product challenge is making the five-minute demonstration
compelling while maintaining genuine technical depth.

---

# 9. Track 05: Open Track

[Verified from hackathon brief]

Open Track allows any domain or workflow.

The same bar still applies:

- Real problem
- Meaningful AI usage
- Working product
- Evidence of value
- Reliability
- Technical depth

Source:
docs/hackathon.md

[Inference]

Open Track should only be selected if we discover an idea that is
materially stronger than the opportunities available in Tracks 01-04.

---

# 10. Cross-Track Engineering Principle

[Inference]

A recurring architecture appears across the strongest candidates:

AI reasoning
→ deterministic policy/constraints
→ authorization gate
→ bounded action
→ verification
→ audit trail

This architecture is particularly relevant because the hackathon
explicitly emphasizes explainability, bounded/gated money actions,
failure handling and evidence.

---

# 11. Preliminary Assessment

This is NOT the final track decision.

| Track | Technical Depth | Measurement | Demo Potential | Current Feasibility | Differentiation |
|---|---:|---:|---:|---:|---:|
| AI Revenue Recovery | 5/5 | 5/5 | 5/5 | 5/5 | 4/5 |
| AI Growth & Agentic Commerce | 5/5 | 4/5 | 5/5 | 3/5 | 5/5 |
| AI Risk Manager | 5/5 | 5/5 | 4/5 | 4/5 | 4/5 |
| AI Finance Controller | 4/5 | 5/5 | 3/5 | 4/5 | 4/5 |
| Open Track | Unknown | Unknown | Unknown | Unknown | Potentially 5/5 |

These scores are our strategic judgments, not official Razorpay
ratings.

Current leading candidates:

1. AI Revenue Recovery
2. AI Growth & Agentic Commerce
3. AI Risk Manager

---

# 12. Remaining Validation Questions

Before choosing a final track, answer:

1. What exact Razorpay Test Mode actions can our chosen product execute?
2. Can we demonstrate the complete workflow end-to-end?
3. Can we measure the required outcome across a meaningful batch?
4. What existing solutions make the obvious ideas generic?
5. Where can AI provide genuine value instead of cosmetic LLM usage?
6. What failure modes can we deliberately demonstrate?
7. What safety/policy gates are required?
8. What would make our project difficult to replicate superficially?
9. Can the entire story be demonstrated clearly in five minutes?

---

# Source Hierarchy

When there is a conflict:

1. Official Razorpay hackathon brief
2. Official Razorpay documentation
3. Official protocol documentation
4. Other external sources
5. Our own inference

Never treat an inference as an official requirement.
Never claim an API capability until it has been verified.