# Operator Validation Protocol

**Status: NOT INTERVIEWED. No completed interviews or measured user outcomes are recorded here.** This is a protocol, not validation evidence. No external contact or interview has been performed for this document.

## Purpose And Consent

Spend 15-20 minutes with a consenting transport owner or settlement clerk on one trip: delivery proof, customer payment, driver expenses and advance accounting, then an evidence-backed follow-up. The three-truck persona in the [PRD](../PRD.md) is illustrative, not a recruited participant.

Start with: "We are testing a prototype, not auditing you. Participation is voluntary; you may skip a question or stop. We will use synthetic records unless you explicitly permit otherwise. May we take anonymized notes?" Ask separately for recording, artifact copying, external AI processing and public quotation; agreement to an interview is not agreement to any of these. Record each choice privately. Default to no recording and no public quotation.

- Request one recent trip's invoice, signed challan, fuel/other expense receipts, driver advance/cash-return record, partial-payment records and, optionally, a voice promise. Ask for redacted copies or a private on-device walkthrough; never require originals or access to accounts.
- Prefer synthetic substitutes. Remove names, signatures, NID numbers/images, customer and driver phones, bank/mobile-money account numbers, transaction identifiers, truck plates, addresses, faces, QR codes and file metadata. Use consistent aliases where cross-record matching matters; flatten redactions and check they cannot be recovered. For audio, prefer a synthetic reenactment without real names or voices.
- No real NID, customer phone or bank account data may be uploaded without explicit permission. Before any real artifact upload, confirm authority and consent for affected people, the specific data, storage and named external provider processing. Interview consent or the operator's possession of a receipt is not sufficient. If consent or safe redaction is uncertain, do not upload; use synthetic records.
- Even a local app can send uploaded images/audio or investigation text to configured providers. Explain that boundary before processing. Agree a private storage location, access, retention/deletion date and withdrawal procedure before copying anything; do not promise an automated deletion feature. Keep consent/contact records separate from anonymized observations. Publish no participant artifact by default.

## 18-Minute Session

| Minutes | Activity |
|---------|----------|
| 0-2 | Explain purpose, obtain granular consent, confirm synthetic/redacted inputs and note-taking permissions. |
| 2-6 | Ask the operator to describe one recent settlement and the evidence they normally consult. Do not lead with the product. |
| 6-10 | Manual baseline: use paper/calculator or their usual method on the supplied synthetic packet; observer times and scores without hints. |
| 10-14 | HisabGuard task: review the same inputs, investigate, inspect citations, approve/export a follow-up and explain why closure remains blocked. Nothing is sent or paid. |
| 14-17 | Ask what was confusing, unsupported or unlike their real process; compare the two answers, not just speed. |
| 17-18 | Confirm permitted use of notes/artifacts, retention and withdrawal route. Offer to stop or remove any sensitive material. |

Questions for the workflow and debrief:

- How are driver advances recorded, matched to fuel and other expenses, and reconciled with returned cash? What happens when an expense has no receipt or belongs to another trip?
- How do you track partial customer payments and connect each receipt to the correct invoice? What counts as sufficient evidence of receipt?
- When a customer or driver promises payment in a call or voice note, what do you record, and what proof is still missing? Does anyone mistakenly treat that promise as money received?
- Who checks a challan, resolves conflicting/duplicate records, approves follow-ups and decides a trip is settled? Which exception causes the most rechecking?
- Which proposed question would you actually ask next? Can you trace each amount to a record, and can you explain what approving the draft does and does not do?

## Comparison Method

Use the [synthetic TRIP-104 packet](demo.md) in both conditions. Prepare the manual packet with the same source information available in the app, not its computed totals. Before timing, write a private scoring key from those records: BDT 7,000 customer outstanding; BDT 1,500 advance balance separately accountable; a voice promise changes neither; delivery proof and unresolved evidence must be checked; the next follow-up requests missing evidence, not assumed payment. These are fixture answers, not recovered money.

Ask the same tasks in both conditions: identify received versus promised money, compute both balances, list missing/unsupported evidence, choose recipient and draft a follow-up, and decide whether closure is justified. Start timing when the packet/task is presented; stop when the operator states answers and finishes the draft. Include app review and provider waiting time; record setup time separately. Cap each condition at four minutes and mark unfinished tasks as incomplete, not successful or zero-time. Note provider mode/model, errors/retries, assistance and task familiarity.

Score each task against the prewritten key as correct/incorrect/incomplete; record wrong amounts, promise-as-payment errors, missed evidence and assistance counts. Report manual seconds and app seconds, with difference = manual - app only for equally completed tasks. Preserve negative differences; do not turn a capped or assisted result into a savings claim. Manual-first reuse has a practice/order effect, so this short session is descriptive, not causal proof. For further sessions, alternate order or use matched synthetic packets with equivalent tasks and separate answer keys; document any input differences. Do not pool synthetic author checks with operator observations or extrapolate to revenue, fraud reduction or population-wide efficiency.

## Blank Observation Sheet

**NOT INTERVIEWED / NOT COLLECTED.** Blank cells below are placeholders, not observations. Complete only after consent and an actual session; use an anonymous session id, never a phone/NID.

Session id: ____ | Role (self-described): ____ | Consent choices/private record reference: ____

Packet/order: ____ | App mode/provider/model: ____ | Setup seconds: ____ | Retention/deletion agreement: ____

| Task | Manual Seconds | Manual Correct/Incorrect/Incomplete | App Seconds | App Correct/Incorrect/Incomplete | Errors / Assistance / Wait / Notes |
|------|----------------|-------------------------------------|-------------|----------------------------------|------------------------------------|
| Separate received payment from promise | | | | | |
| Compute customer outstanding | | | | | |
| Reconcile advance, expenses and cash return | | | | | |
| Identify missing/unsupported evidence | | | | | |
| Draft next follow-up and explain closure | | | | | |

Observed confusion/limitations: ____ | Permitted anonymized quote (only with separate consent): ____

Keep raw records private. Add an anonymized result summary only after a real review and explicit publication permission; until then, user fit and impact remain unproven. Technical checks belong in [evaluation results](evaluation-results.md), which the main agent will produce, not in an interview count.
