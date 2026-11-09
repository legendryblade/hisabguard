# HisabGuard

A trip-settlement investigation workspace for small transport operators in Bangladesh.

## User And Outcome

The illustrative operator runs three trucks and receives challans, fuel receipts, advances, payment screenshots, and driver statements in different places. HisabGuard reconstructs one trip, identifies what is unsupported, asks for the next useful evidence, and drafts a follow-up for the owner. The persona and every seeded document are synthetic, not customer validation.

The hero workflow is a BDT 32,000 invoice, BDT 25,000 received payment, signed challan, BDT 3,500 fuel receipt, and BDT 5,000 driver advance. A promise about the remaining BDT 7,000 must never count as receipt of that money. The BDT 1,500 advance balance remains separately accountable.

## Scope

- Persist trips, original evidence, extraction proposals, reviews, investigation runs, questions, approved drafts, and audit events.
- Accept image evidence, audio voice notes through a configurable transcription service, and explicitly labelled typed operator records.
- Review extracted fields before they enter settlement arithmetic. All financial values retain an evidence id.
- Investigate short payments, missing delivery proof, duplicate claims, conflicting invoices, unreviewed evidence, and unaccounted advances.
- Reassess after customer or driver statements and additional documents. Statements remain statements.
- Approve or reject follow-ups, then export approved text. No WhatsApp, banking, or government integration is claimed.
- Close a settlement only after the independent validator confirms the delivery, received payment, expense and advance accounting, and all blocking evidence issues. The model cannot close it.
- Provide printable evidence packets and a backup export.

## Agent And Validator

An OpenAI-compatible model chooses among bounded read, clarification, follow-up, and finish tools. Tool calls and results are persisted. Amounts in natural-language conclusions cannot change balances. Date, currency, duplicate detection, settlement calculations, and approval freshness checks stay deterministic.

Without model credentials, the application provides a labelled deterministic review demonstration, not a pretend AI agent. Image and audio processing require the respective provider credentials; unavailable or failed processing leaves the original evidence visible for manual review. It never supplies invented extracted fields.

## UX

The home screen is an exception queue, not a generic chatbot. Each trip opens a settlement desk with evidence review, the independent money breakdown, next evidence needed, proposed follow-ups, and an activity trail. Desktop uses a navy navigation rail, paper-coloured workspace, tabular money, and restrained orange exception accents. Mobile reflows to one column. Input labels, keyboard controls, retry states, approval freshness, synthetic labels, and provider status are visible.

## Acceptance

1. A promise leaves BDT 7,000 outstanding; a reviewed payment record changes the balance.
2. Duplicate payment ids and receipt hashes never add twice and prevent settlement closure until resolved.
3. A failed model call or malformed extraction remains failed with a safe error and retry path.
4. Approving a follow-up does not send it, settle a trip, or mark money received.
5. Evidence changes invalidate pending approvals and settlement recommendations.
6. State, audit history, and documents survive restart.
7. Desktop and mobile tests drive upload/review, investigation/reply, approval/export, and settlement refusal/success.

## Deliberate Limits

Local SQLite and private filesystem storage support the single-operator pilot. This is not a multi-tenant production deployment or a fraud detector. Public hosting requires an access token, TLS, restricted private storage, a retention/backup policy, and a security review. Real Bangla transcription and image accuracy require genuine documents and credentials to benchmark. Test results and synthetic demos cannot be advertised as real revenue saved.

## Hackathon Deliverables

Working demo URL, 90-second evidence-to-follow-up recording, repository, setup instructions, exact model/provider disclosure, and measured controlled-test outcomes. Interview a transport operator before claiming user validation. Registered teams must have 3-4 members per the supplied brief. Do not claim Devin use unless it was actually used.
