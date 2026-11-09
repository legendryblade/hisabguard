# API Contract v1

Frontend uses `/api`, backend port 8834, Vite development port 5181. Money is a decimal STRING in BDT with exactly two fractional digits; the backend uses integer paisa. All ids are integers, except human-readable trip `code`. All JSON errors use `{ "detail": "safe message" }`; validation errors can use standard FastAPI detail arrays.

## Models

Trip: `{id,code,customer,driver,truck,origin,destination,status,revision,created_at}`. Status: collecting | investigating | awaiting_response | ready_for_review | unresolved | settled.

Evidence: `{id,trip_id,title,kind,state,amount_bdt,transaction_id,trip_ref,note,text,delivered,confidence,source_type,synthetic,filename,mime,extraction_error,created_at}`. Kind: invoice | payment | expense | advance | cash_return | delivery | statement. State: draft | confirmed | excluded. Optional scalar fields can be null. `confidence` is a record of field names to 0..1. `source_type`: manual | image | audio. `filename` is null if no file. Files are private and reached only through the evidence-file endpoint, not a static mount.

Settlement: `{invoice_bdt,received_bdt,outstanding_bdt,expense_bdt,advance_bdt,cash_return_bdt,advance_balance_bdt,delivery_confirmed,can_settle,issues,sources}`. Issue: `{code,severity,title,detail,evidence_ids}` where severity is blocking | warning. `sources` maps money column names to evidence id arrays. Draft and excluded evidence cannot change totals. Multiple confirmed invoices block and are not added together. Duplicate transaction ids/file hashes block and count at most once. Overpayments block until resolved. No confirmed invoice or delivery proof blocks closure. `advance_balance_bdt` = advance - expenses - cash returned; it must be zero for closure.

Investigation: `{id,trip_id,revision,mode,status,summary,question,recipient,evidence_ids,steps,created_at}`. Mode: model | demo. Status: investigating | completed | failed | awaiting_response. Question and recipient nullable. Steps: `[{tool,args,result}]`. Model failure is not converted into successful demo output. Only one active run per trip is permitted; a ten-minute lease enables explicit recovery from an interrupted worker. Model context carries recent decisions, not recursively embedded old tool transcripts.

Action: `{id,trip_id,revision,kind,recipient,message,evidence_ids,status,created_at}`. Kind followup. Status: pending | approved | rejected | stale. Approved means draft approved, never message sent. Revision mismatch is rejected as stale. Every evidence mutation increases revision and marks old pending actions stale.

Audit: `{id,trip_id,actor,event,detail,created_at}`. Detail is a JSON object. Personal evidence/text never goes in terminal logs.

TripDetail: `{trip,evidence,settlement,investigations,actions,audit}`.

TripSummary: Trip plus `{invoice_bdt,received_bdt,outstanding_bdt,expense_bdt,advance_bdt,advance_balance_bdt,evidence_count,exceptions_count}`.

## Endpoints

- GET `/api/status` -> `{model_configured,model_name,vision_configured,stt_configured,mode,external_delivery:"draft_only",demo:true,auth_required}`. No secret values exposed.
- GET `/api/trips` -> `{trips:TripSummary[],overview:{trips,exceptions,outstanding_bdt,pending_approvals}}`.
- POST `/api/trips` JSON `{code,customer,driver,truck,origin,destination}` -> TripDetail. Code is optional, other text fields required except origin/destination.
- GET `/api/trips/{id}` -> TripDetail.
- POST `/api/trips/{id}/evidence` JSON `{kind,title,amount_bdt?,transaction_id?,trip_ref?,note?,text?,delivered?}` -> TripDetail; creates a draft operator record.
- POST `/api/trips/{id}/upload` multipart `{file,title,kind_hint}` -> TripDetail. kind_hint is one of evidence kinds. Images and audio only; max 10 MB. Store original even if provider not configured, leave extraction_error visible. Extraction proposals always draft. Audio transcripts ALWAYS remain statements, never ledger transactions or delivery proof. Repeated identical file on the same trip returns 409, not silent success.
- POST `/api/evidence/{id}/review` JSON `{decision:"confirm"|"exclude",fields?:{kind,amount_bdt?,transaction_id?,trip_ref?,note?,text?,delivered?}}` -> TripDetail. Model cannot call this route. Explicit manual correction and review can recover an extraction failure. A statement cannot be reviewed into a payment. Exclude removes a duplicate claim from totals, not its audit history.
- GET `/api/evidence/{id}/file` -> original binary with content-type and no-cache. No file exists: 404.
- POST `/api/trips/{id}/investigate` -> TripDetail. Configured model uses bounded tools; absent model uses labelled demo review; provider failure creates failed run and returns safe 502 detail.
- POST `/api/trips/{id}/reply` JSON `{text}` -> TripDetail. Records a confirmed statement (not a transaction), increments revision; then owner can click investigate again. It cannot overwrite money or trip identifiers.
- POST `/api/actions/{id}/decision` JSON `{decision:"approve"|"reject"}` -> TripDetail. Pending action only; stale returns 409. Repeated approval does not repeat an effect.
- GET `/api/actions/{id}/export` -> approved follow-up UTF-8 text attachment; unapproved/stale revision refuses.
- POST `/api/trips/{id}/close` JSON `{decision:"approve_settlement"}` -> TripDetail. Validator requires can_settle and a completed current-revision investigation; otherwise 409.
- GET `/api/trips/{id}/report` -> escaped printable HTML containing settlement, evidence ids, issues, proposals and audit trail. Authenticated fetch can open a Blob URL for printing.
- GET `/api/export` -> versioned JSON backup, excluding secrets/original binary files.
- GET `/api/activity` -> `{activity:Audit[]}`.

## Providers Module (Owned Separately)

`app/providers.py`: `ProviderError`, `get_status()`, `extract_image(data:bytes,mime:str)->dict`, `transcribe_audio(data:bytes,filename:str,mime:str)->str`, `agent_turn(messages:list,tools:list)->dict` (standard assistant message with content/tool_calls). All synchronous, safe failures via ProviderError. Model/vision use HISABGUARD_LLM_BASE_URL, HISABGUARD_LLM_API_KEY, HISABGUARD_LLM_MODEL, HISABGUARD_VISION_MODEL. STT uses HISABGUARD_STT_BASE_URL, HISABGUARD_STT_API_KEY, HISABGUARD_STT_MODEL. Explicit root .env load, no credentials from other projects. Extracted dict keys match review fields plus confidence. Provider outputs are validated by backend, never written as confirmed evidence.

## Access

HISABGUARD_ACCESS_TOKEN optional for loopback development; mandatory for documented public deployment. API bearer header if configured. Frontend supports entering token into sessionStorage after 401. GET status public and non-personal. Reject cross-origin write requests unless Origin is own host or explicit configured development origin. Unknown /api paths return JSON 404, never SPA HTML. All client routes serve SPA only after API/static registration.
