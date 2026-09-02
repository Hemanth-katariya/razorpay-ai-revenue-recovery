# 5-Minute Pitch Video Script

Status: shooting script for the required demo video, expanded from
`docs/product-spec.md` §9 with actual commands/screens. Rehearse once
end-to-end before recording — the timing is tight.

**Before recording:**
1. Run the §4.1 capability spike (`scripts/verify_actions.py`, see
   README) so at least the `payment_link` action is `API_VERIFIED`.
   This is what lets you show a real `EXECUTING → RECOVERED` cycle
   instead of only escalations.
2. Reset the DB (`rm backend/recoverflow.db`) and re-seed so the demo
   batch is the only data on screen.
3. Start the backend (`uvicorn app.main:app --reload`) and frontend
   (`npm run dev`), confirm the "API Connected" indicator is green.
4. Have `backend/synthetic_data/events_batch_01.json` and a terminal
   ready to run the replay script live, or pre-run it and just narrate
   over the frontend — pre-running is safer for a 5-minute window.

---

### 1. Problem statement (0:00–0:30)

> "When a Razorpay subscription charge fails, Razorpay retries it
> automatically — but there's no API to force that retry, and no
> confirmed API to change a customer's payment method or re-authorize
> their mandate. We checked before assuming otherwise —
> [`docs/recovery-feasibility.md`](../docs/recovery-feasibility.md)
> in this repo documents exactly what's API-executable versus
> Dashboard-only versus unsupported. So a halted subscription is silent
> revenue loss: a human has to notice, and nobody's measuring how much
> of it was actually recoverable. RecoverFlow is scoped to what's
> actually possible: notification-based recovery, gated and audited."

*(Show `docs/recovery-feasibility.md`'s summary table on screen for ~5s
— it's the single strongest "problem taste" signal you have.)*

### 2. Feed a batch (0:30–1:30)

> "Here's a batch of 14 synthetic failed-subscription events — some
> duplicates to test idempotency, four failures on one subscription to
> test the attempt cap, a ₹1.5 lakh subscription to test the exposure
> cap, a halted-mandate case, and one that gets paid later so we can
> show real recovery."

Run (or show already-run output of):
```
python -m scripts.replay_batch synthetic_data/events_batch_01.json --label "demo batch"
```
Switch to the frontend Pipeline view — point at the flow diagram
(`DETECTED → DIAGNOSED → GATED → …`) populating with counts.

### 3. Walk one subscription end-to-end (1:30–3:00)

Click into **Subscriptions**, select the subscription that reaches
`RECOVERED` (or `EXECUTING`, if the spike promoted an action). Narrate
the audit timeline top to bottom:

> "Detected on the first `payment.failed` webhook. Diagnosed —
> here's the AI's category, confidence, and one-line rationale, pulled
> straight from `diagnoses.raw_model_output`, not paraphrased. Gated —
> every policy check is logged even when it passes: allow-list, attempt
> cap, cooldown, exposure cap, idempotency. [If verified:] Executed —
> here's the real Razorpay Test Mode response. And recovered — not
> because we sent a message, but because a later `payment.captured`
> webhook actually confirmed it. That's the whole audit trail for one
> subscription, reconstructable from this screen alone, no code
> required."

### 4. Show a failure handled gracefully (3:00–4:00)

> "Not everything gets executed automatically, and it shouldn't. Here's
> the escalation queue."

Click **Escalations**. Pick one with reason `unverified_action` or
`schema_invalid` or `low_confidence` and open its audit trail.

> "This one's diagnosis confidence came back below our threshold, so
> instead of guessing, the system routed it to a human queue and logged
> exactly why — no crash, no silent retry loop, no fabricated action."

*(If you have a `schema_invalid` case, this is the strongest one to
show — it demonstrates the system refusing to trust a malformed model
response rather than silently defaulting.)*

### 5. Batch metrics, honestly (4:00–5:00)

Click **Metrics**.

> "This is the full batch, not a cherry-picked example: revenue at risk
> detected, revenue actually recovered — confirmed by webhook, never
> inferred — recovery rate, and the honest numbers most demos skip:
> escalation rate and stop rate, broken down by reason. And this
> reconciliation line is the whole point: recovered plus stopped plus
> not-recovered plus still-open always equals the batch size. Nothing's
> hidden, nothing's left stuck."

Point at the "Batch Size Reconciliation" panel closing the video on
that equation.

---

## Fallback lines if something breaks live

- **API disconnected banner:** "This is exactly the kind of failure the
  system is built to surface loudly rather than hide — same principle
  as the escalation queue." (Then fix it off-camera / cut.)
- **No `EXECUTING` cases in this batch:** "This batch's actions are
  still `API_ASSUMED` pending our Test Mode verification spike — every
  event correctly escalates rather than guessing. Here's the unit test
  that proves the execution path works once an action is verified:
  `tests/test_policy_gates.py`." Have that test file open as a backup
  screen.
