# Razorpay AI Buildathon Project

## Project

**AI Revenue Recovery Orchestrator** (working name: RecoverFlow) —
a Failed-Subscription Recovery Agent.

## Track & Product Status

**Track 03 — AI Revenue Recovery is LOCKED.**
Product direction is LOCKED. See `docs/decision.md` for the full
rationale. Do not revisit track selection.

## Current Phase

**Implementation.**

Completed phases / docs:

1. Competition analysis — `docs/competition-analysis.md`
2. External research — `docs/research.md`
3. Track comparison & decision — `docs/decision.md`
4. Idea candidates — `docs/candidates.md`
5. Recovery feasibility check — `docs/recovery-feasibility.md`
6. Product specification — `docs/product-spec.md`
7. Architecture — `docs/architecture.md`

## Source of Truth

- Official hackathon requirements: `docs/hackathon.md`
- Track/product decision & rationale: `docs/decision.md`
- What Razorpay APIs can actually execute in Test Mode: `docs/recovery-feasibility.md`
- Product spec: `docs/product-spec.md`
- Architecture: `docs/architecture.md`

Clearly distinguish official requirements, external research,
assumptions, and decisions. Do not invent hackathon requirements.

## Critical Rules (non-negotiable)

- **Never assume an UNCERTAIN Razorpay capability works.** Anything
  marked UNCERTAIN in `docs/recovery-feasibility.md` must be verified
  against live Test Mode behavior before being relied on — never coded
  against as if confirmed.
- **Never fake recovery.** Recovered-revenue outcomes must reflect real,
  observed Razorpay state changes — never simulated, estimated, or
  hardcoded to look successful.
- **Test Mode only.** All Razorpay API calls and demos run against
  Razorpay Test Mode. No live/production keys or charges.
- Every autonomous money-related action must be bounded, explainable,
  gated, and auditable.
- Prefer deterministic logic when AI is unnecessary; AI's role
  (diagnosis/decision) must be clearly justified, per `docs/product-spec.md`.

## Development Workflow

Phases: competition analysis → external research → track comparison →
idea generation → idea evaluation → track/product selection → product
specification → architecture → evaluation strategy → **implementation**
(current) → testing → demo preparation.

## Terminal and Git Learning Mode

I am learning Bash, Git, GitHub, and professional development workflows.

When a terminal or Git command is needed:

- Tell me the exact command.
- Briefly explain why I need it.
- Explain what I should expect.
- Prefer letting me execute the command myself.
- Do not commit or push changes unless I explicitly ask.

Do not silently perform destructive operations.

## Documentation

Important decisions should be documented in the docs/ directory.
