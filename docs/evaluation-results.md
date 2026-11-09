# HisabGuard Evaluation Results

Recorded November 8, 2026. These are synthetic technical checks, not customer validation, bank verification, fraud accuracy, or money recovered.

## What Was Actually Exercised

- OpenRouter model `nvidia/nemotron-3.5-super-vl:free` performed real tool calls on six synthetic trip packets.
- Optional extended reasoning was explicitly disabled after default reasoning consumed the response budget without usable tool output. This uses OpenRouter's documented `reasoning.enabled` control on a model whose catalogue marks reasoning optional.
- The baseline is the application's actual `app.demo.review` reviewer. It already handles missing delivery records, duplicate transactions, promises and arithmetic; it is not an intentionally empty competitor.
- Inputs contain reviewed synthetic operator records and an unstructured statement. Routing tests do not include OCR in their inputs. The separate vision test uses three generated images.
- Expected roles and evidence keywords were written before the runs and are not included in model inputs. Opaque trip codes avoid leaking the scenario name.
- The provider calls used the user-authorized environment key, mapped to HisabGuard in process memory only. No key was printed or saved in the repository.

Dataset SHA-256: `d7744f35521dc7593b31913dce24a00f09766b96b0e02fa560c29094e40b420b`.

Agent code SHA-256 for the routing run: `276097088a037b9d2ef8d5945bd265ac3a42941a5d4dd751fa47e66523c7ce98`.

Local raw result: `artifacts/evaluation-bounded.json`. The latest focus-only prompt refinement was made after this run and has not been revalidated live because the provider became rate-limited. Do not attribute these scores to a new prompt or model.

## Routing Results

Scoring is a **lexical/recipient proxy**: the question must contain an expected evidence keyword and its recipient must contain a permitted role. It can overestimate usefulness when the model merely mentions a topic or asks several parties. Every question is published below for human review.

| Synthetic Case | Existing Reviewer | Live Model | Model Recipient | Elapsed Seconds / Calls |
|----------------|-------------------|------------|-----------------|-------------------------|
| Promise is not payment | Match | Match | customer and driver | 16.54 / 5 |
| Cash reportedly held by driver | No match | Match | trip owner | 14.63 / 4 |
| Disputed weight deduction | No match | Match | customer and driver | 12.88 / 4 |
| Missing delivery challan | Match | Match | customer and driver | 21.08 / 4 |
| Duplicate fuel receipt | Match | No match | Synthetic customer | 13.28 / 4 |
| Fully documented account | Match | Match; no question | none | 11.43 / 3 |

Automatic proxy: **model 5/6; baseline 4/6**. All six live investigations completed without an engine/provider exception. Ledger values and validator eligibility remained unchanged in all six; the model did not settle a trip or approve an action. The suite made 28 provider requests including a capability check and three image requests.

Timing includes application work and a minimum 3.2-second interval between provider request starts to reduce free-tier throttling. It is not a millisecond latency claim or a general performance benchmark.

### Human Inspection

The automatic score is **not enough to claim a superior operator workflow**. Several model questions bundled all outstanding issues and multiple recipients. The weight-deduction answer mentioned the weighbridge but still requested ordinary payment and advance proof rather than focusing solely on the deduction basis. The duplicate answer addressed the customer even though duplicate fuel evidence belongs with the operator/driver.

These are real weaknesses, not hidden failures. The prompt now requests one focused question for one role, prioritizes conflicting records, and distinguishes reported cash collections/deductions from ordinary nonpayment. This refinement needs a new live run and a separate held-out dataset; the six current cases are development fixtures, not an independent test set.

## Generated Questions

### Promise

> Trip EVAL-001 has two blocking issues: (1) BDT 7000.00 invoice balance remains outstanding with no received-payment evidence (invoice EVAL-001-INV BDT 32000.00 vs payment EVAL-001-PAY BDT 25000.00); (2) advance accounting is incomplete — advance BDT 5000.00 (EVAL-001-ADV) minus fuel expense BDT 3500.00 (EVAL-001-FUEL) and cash return BDT 0.00 leaves BDT 1500.00 unaccounted, which must be zero. The customer's statement (evidence 6) promises BDT 7000 tomorrow but is not payment evidence. Please provide: (a) proof of receipt for the remaining BDT 7000.00, or an explanation and supporting document for why it remains unpaid; and (b) documentation showing how the BDT 1500.00 advance balance was settled (expense receipts, cash return, or adjustment), so it reaches zero.

### Cash With Driver

> Can you provide a receipt, bank transfer record, or other payment evidence showing that BDT 7000.00 was received against invoice EVAL-002-INV (BDT 32000.00)? The customer and driver statements say the cash was handed to the driver, but no receipt or handover record exists. Also, can you provide documentation showing how the BDT 5000.00 advance (EVAL-002-ADV) was fully applied against BDT 3500.00 in expenses (EVAL-002-FUEL) and any cash return, so the advance balance reaches zero instead of BDT 1500.00?

### Disputed Deduction

> The independent settlement shows two blocking issues: (1) BDT 7000.00 remains outstanding — invoice BDT 32000.00 (evidence 13) minus received payment BDT 25000.00 (evidence 14); and (2) advance accounting is incomplete — advance BDT 5000.00 (evidence 16) minus fuel expense BDT 3500.00 (evidence 15) and cash returned BDT 0.00 leaves BDT 1500.00, which must be zero. The customer's statement (evidence 18) contests the final BDT 7000 due to short unloading weight, and the driver says he can obtain the destination weighbridge slip. Please provide: (a) proof of the remaining BDT 7000.00 payment or a documented settlement of the disputed amount, and (b) proof of how the BDT 1500.00 advance balance was settled (cash return, additional expense receipt, or adjustment). Cite any supporting evidence ids you can provide.

### Missing Challan

> Trip EVAL-004 has three blocking issues: (1) BDT 7000.00 payment outstanding against invoice BDT 32000.00 (invoice EVAL-004-INV, evidence 19) with only BDT 25000.00 received (payment EVAL-004-PAY, evidence 20); (2) advance accounting incomplete — advance BDT 5000.00 (evidence 22) minus fuel expense BDT 3500.00 (evidence 21) leaves BDT 1500.00 unaccounted, must be zero; (3) delivery proof missing — no confirmed delivery evidence with delivered=true exists. Please provide: (a) evidence of the remaining BDT 7000.00 customer payment or an explanation of how the outstanding balance will be settled; (b) evidence accounting for the BDT 1500.00 advance balance (additional expense receipt, cash return, or adjustment); and (c) a signed delivery challan or other confirmed delivery proof with delivered=true for trip EVAL-004.

### Duplicate Fuel

> Please provide evidence supporting the remaining BDT 7000.00 payment outstanding on invoice EVAL-005-INV (BDT 32000.00) after the received payment of BDT 25000.00 (EVAL-005-PAY). Also clarify whether the duplicate fuel transaction EVAL-005-FUEL (evidence 26 and 28, BDT 3500.00 each) should be counted once, and how the advance balance of BDT 1500.00 (advance BDT 5000.00 EVAL-005-ADV minus expense BDT 3500.00) will be resolved to zero.

Balanced case: no question was generated.

## Vision And Provider Failures

Full-field match requires kind, amount, transaction id and trip reference to match the printed fixture. In the completed bounded run, **1/3** image fixtures passed the full-field gate. The invoice and payment proposals failed schema validation; the expense passed. Originals remain drafts whenever extraction fails.

A targeted diagnostic found `null` confidence for an inapplicable delivery field. The parser now omits an unknown/inapplicable confidence hint rather than inventing a score or rejecting otherwise valid fields. A unit test verifies that behavior. The live three-image retest was blocked by **HTTP 429 on all three requests**, so its result is provider unavailability, not a measurement of the parser fix or image accuracy.

Other observed failures:

- Paid `openai/gpt-4.1-mini` capability request: HTTP 402.
- Free Gemma capability request: HTTP 429.
- Default-reasoning NVIDIA run: 0/6 completed investigations; output budget was exhausted before usable calls. The application correctly kept all ledgers unchanged. Disabling optional reasoning resolved that problem in the measured six-case run.
- Zero-priced preview-model capability request: HTTP 403.

No failed live run was replaced by a canned successful model response. Do not advertise real Bangla STT, genuine receipt accuracy, production fraud detection or endpoint reliability from these checks.

## Reproduce

From the repository root, with a user-authorized OpenRouter environment credential:

```powershell
python scripts/evaluate.py --live --provider openrouter --model "nvidia/nemotron-3.5-super-vl:free" --reasoning off --pace-seconds 3.2 --max-calls 32 --output artifacts/evaluation-new.json
python scripts/evaluate.py --live --provider openrouter --model "nvidia/nemotron-3.5-super-vl:free" --reasoning off --pace-seconds 3.2 --ocr-only --max-calls 3 --output artifacts/ocr-new.json
```

No external calls occur without `--live`. A funded accessible model or restored provider quota is needed for a reliable new live recording. Model ids can be changed explicitly; do not claim the new model's results are the ones reported here.
