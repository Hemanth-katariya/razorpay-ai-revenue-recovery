# Recovery Feasibility Check

Status: Narrow feasibility check for Track 03 (AI Revenue Recovery),
candidate: Failed-Subscription Recovery Agent. This does not select an
architecture, design a product, or expand scope — it only answers which
recovery actions our backend can actually execute programmatically
against Razorpay's documented APIs in Test Mode.

Evidence sources are either:
- **Fetched this session** — Razorpay documentation pages fetched directly
  during this check.
- **docs/research.md** — sources already verified and cited in an earlier
  phase of this project (also official Razorpay documentation).

Two dedicated endpoint-parameter pages returned HTTP 404 during this
session's fetches (Invoices "Send Notifications" detail page, Payment
Links "Send/Resend Notifications" detail page, Cancel Subscription detail
page, Pause Subscription detail page). Where that happened, only
overview-level existence is confirmed, and parameter/Test-Mode detail is
marked UNCERTAIN rather than assumed.

| Action | Classification | Test Mode? | Evidence | Limitation |
|---|---|---|---|---|
| Receive failed-charge signal via webhook (`payment.failed`, `subscription.pending`, `subscription.halted`) | API_EXECUTABLE | Yes | docs/research.md §3–4 (subscription test-mode + webhook idempotency docs); this session's fetch of `/docs/webhooks/` confirms the webhook mechanism and the `payment.failed` event | This session's general webhooks-page fetch did not itself re-list subscription-specific event names; a dedicated subscription-events page was not successfully fetched today, so today's confirmation of the full event catalog relies on the earlier-cited research.md source, not a fresh fetch |
| Fetch a subscription's current state (GET Subscription by ID) | API_EXECUTABLE | UNCERTAIN | This session's fetch of `/docs/api/payments/subscriptions/` — "Fetch Subscription With ID – GET" | No parameter/response detail retrieved; Test Mode behavior not restated on this specific endpoint |
| Fetch all invoices generated for a subscription (GET) | API_EXECUTABLE | UNCERTAIN | Same overview fetch — "Fetch All Invoices for a Subscription – GET" | No parameter/response detail retrieved |
| Cancel a subscription (POST) | API_EXECUTABLE | UNCERTAIN | Same overview fetch — "Cancel a Subscription – POST" | Dedicated parameter page returned 404 this session; required fields (e.g. cancel-at-cycle-end options) not confirmed |
| Update a subscription, e.g. plan/quantity (PATCH) | API_EXECUTABLE | UNCERTAIN | Same overview fetch — "Update a Subscription – PATCH" | No parameter detail retrieved; not confirmed whether usable on a `pending`/`halted` subscription specifically |
| Pause a subscription (POST) | API_EXECUTABLE | UNCERTAIN | Same overview fetch — "Pause a Subscription – POST" | Dedicated page returned 404 this session; behavior on an already-failing subscription not confirmed |
| Resume a subscription (POST) | API_EXECUTABLE | UNCERTAIN | Same overview fetch — "Resume a Subscription – POST" | Same as above |
| Force/trigger the automatic subscription retry schedule via API | NOT_SUPPORTED | N/A | This session's fetch of `/docs/payments/subscriptions/test/` — retries are described as "scheduled, automatic"; explicitly: "the documentation does not mention an API endpoint to manually trigger retries" | This is a documented gap, not merely an unfetched page — but absence in one fetched page cannot fully rule out an undocumented mechanism |
| Manually attempt to charge a halted subscription's issued invoice ("Attempt Charge" / "Charge this now") | DASHBOARD_ONLY | N/A | Same test-mode fetch — described as a Dashboard button ("Charge this now") and an "Attempt Charge" option for issued invoices | Described only in UI-button language, not as an API call; a true API endpoint for this was neither confirmed nor ruled out (detail pages 404'd) |
| Change/update the customer's payment method or re-authorize the mandate on an existing subscription | NOT_SUPPORTED | N/A | This session's fetch of the subscriptions overview explicitly notes this as a gap: "does not mention endpoints for... changing payment method/authorization on existing subscriptions" | See next row for a possible but unconfirmed alternative |
| Create a Subscription Link (possible re-authorization / new-mandate route) | UNCERTAIN | UNCERTAIN | Overview fetch — "Create a Subscription Link – POST – Creates a Subscription link" (one-line description only) | No detail retrieved on what this link actually does or whether it can re-authorize a failed subscription vs. only create a new one |
| Send/resend an invoice notification (payment reminder) to the customer via email/SMS | API_EXECUTABLE | UNCERTAIN | This session's fetch of `/docs/api/payments/invoices/` — "Send Notifications... Sends notifications to customers" | Exact endpoint path, parameters, and channel selection not retrieved; dedicated endpoint page returned 404. See verified detail below. |
| Create a new Payment Link for the outstanding amount and send/resend its notification | API_EXECUTABLE | UNCERTAIN | This session's fetch of `/docs/api/payment-links/` — "Create Standard Payment Link (POST)" and "Send or Resend Notifications (POST) ... for payment collection and reminders" | Exact parameters not retrieved; whether this can be tied back to a specific failed subscription/invoice was not confirmed; dedicated page returned 404. See verified detail below. |

## Verified Detail: The Two Candidate Notification Actions

Both dedicated endpoint-parameter pages for these two actions returned
HTTP 404 when fetched this session. The findings below are therefore
limited to what the overview-level pages established. Every field the
fetched documentation did not establish is marked UNCERTAIN — none are
inferred.

### 1. Send/resend an invoice notification for an outstanding invoice

- **Exact API endpoint (path):** UNCERTAIN — not retrieved. The overview
  fetch of `/docs/api/payments/invoices/` names the action "Send
  Notifications" but the dedicated page giving its path returned 404.
- **HTTP method:** UNCERTAIN — not explicitly stated for this specific
  endpoint in the fetched overview (the overview listed it in prose as
  "Resend/notify customers" among 14 endpoints, without a method marker).
- **Required parameters:** UNCERTAIN — not retrieved.
- **Usable with an existing outstanding invoice:** UNCERTAIN — the
  overview text states the endpoint "sends notifications to customers"
  and can "resend invoices or payment reminders," which describes acting
  on an existing invoice, but no parameter (e.g. an `invoice_id`) or
  status precondition (e.g. must be `issued`/unpaid) was confirmed.
- **Available in Test Mode:** UNCERTAIN — the fetched page states "Test
  API Keys" are used to explore the Invoices API generally via Razorpay's
  Postman workspace, but this was not confirmed specifically for the
  notification endpoint.
- **Can we simulate the resulting payment in Test Mode:** UNCERTAIN — not
  addressed anywhere in the fetched content.
- **Can we observe the resulting payment/recovery via webhooks/API:**
  UNCERTAIN — not addressed in the fetched content for this action; no
  invoice-related webhook event (e.g. an "invoice paid" event) was
  confirmed this session.
- **Limitation:** Only the endpoint's existence and general purpose are
  confirmed. Path, method, parameters, and Test Mode/observability
  behavior all require a successful fetch of the dedicated page (which
  404'd this session) before this action can be relied on.

### 2. Create a Payment Link for an outstanding amount and send/resend its notification

- **Exact API endpoint (path):** UNCERTAIN — not retrieved for either the
  create step or the notify step. The overview fetch of
  `/docs/api/payment-links/` names "Create Standard Payment Link" and
  "Send or Resend Notifications" as endpoints, but the dedicated
  parameter page for the notification action returned 404, and the create
  endpoint's path was never fetched.
- **HTTP method:** Create Standard Payment Link — **POST** (confirmed,
  stated explicitly in the overview fetch). Send or Resend Notifications —
  **POST** (confirmed, stated explicitly in the overview fetch as "Send
  or Resend Notifications (POST)").
- **Required parameters:** UNCERTAIN — not retrieved for either action.
- **Usable with an existing outstanding invoice/subscription:** UNCERTAIN
  — the overview only confirms a Payment Link can be created generally;
  it does not establish that a Payment Link can be created against, or
  linked back to, a specific existing subscription or invoice's
  outstanding amount.
- **Available in Test Mode:** UNCERTAIN — the fetched page references
  "Test API Keys" for the Payment Links API generally, but this was not
  confirmed specifically for the create or notify actions.
- **Can we simulate the resulting payment in Test Mode:** UNCERTAIN — not
  addressed anywhere in the fetched content.
- **Can we observe the resulting payment/recovery via webhooks/API:**
  UNCERTAIN — not addressed in the fetched content for this action. The
  general webhooks page (fetched this session) names `payment.authorized`
  and `order.paid` as example events, but no Payment-Link-specific
  webhook event was confirmed.
- **Limitation:** Only endpoint names and HTTP methods are confirmed.
  Paths, required parameters, linkage to an existing subscription/invoice,
  Test Mode behavior, and observability all require a successful fetch of
  the dedicated pages (which 404'd this session) before this action can be
  relied on.

## Summary

- **Detection is solid:** webhook-based detection of failed subscription
  charges is API-executable and Test-Mode capable (backed by
  docs/research.md).
- **State inspection is solid at the existence level:** fetching a
  subscription and its invoices are confirmed API endpoints; parameter-
  level and Test-Mode confirmation for these specific calls is UNCERTAIN
  pending a successful fetch of their dedicated pages.
- **There is no API to force an automatic subscription retry.** Retries
  are system-scheduled only. The one manual-charge mechanism found
  ("Attempt Charge" / "Charge this now") is documented as a Dashboard
  action, not confirmed as an API call.
- **There is no confirmed API to change a customer's payment method or
  re-authorize a mandate.** The closest lead ("Create a Subscription
  Link") is unconfirmed and marked UNCERTAIN.
- **The most concretely useful recovery-adjacent actions found are
  notification-based:** resending an invoice reminder, or creating and
  sending a fresh Payment Link — both API-executable at the existence
  level, with Test Mode and parameter detail still UNCERTAIN.

This narrows the executable recovery surface considerably relative to
what `docs/candidates.md` assumed ("retry with backoff," "grace period,"
"notify customer to update payment method" as freely available actions).
Several of those assumed actions are NOT_SUPPORTED or UNCERTAIN as stated
here. This should inform — but is not itself — the next phase (Product
Specification / Architecture).
