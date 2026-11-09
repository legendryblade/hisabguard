export const evidenceKinds = ['invoice', 'payment', 'expense', 'advance', 'cash_return', 'delivery', 'statement'] as const;
export type EvidenceKind = typeof evidenceKinds[number];
export const tripStatuses = ['collecting', 'investigating', 'awaiting_response', 'ready_for_review', 'unresolved', 'settled'] as const;
export type TripStatus = typeof tripStatuses[number];
export type EvidenceState = 'draft' | 'confirmed' | 'excluded';
export interface Trip {
  id: number; code: string; customer: string; driver: string; truck: string;
  origin: string; destination: string; status: TripStatus; revision: number; created_at: string;
}
export interface Evidence {
  id: number; trip_id: number; title: string; kind: EvidenceKind; state: EvidenceState;
  amount_bdt: string | null; transaction_id: string | null; trip_ref: string | null;
  note: string | null; text: string | null; delivered: boolean | null;
  confidence: Record<string, number>; source_type: 'manual' | 'image' | 'audio'; synthetic: boolean;
  filename: string | null; mime: string | null; extraction_error: string | null; created_at: string;
}
export interface Issue {
  code: string; severity: 'blocking' | 'warning'; title: string; detail: string; evidence_ids: number[];
}
export const moneyColumns = ['invoice_bdt', 'received_bdt', 'outstanding_bdt', 'expense_bdt', 'advance_bdt', 'cash_return_bdt', 'advance_balance_bdt'] as const;
export type MoneyColumn = typeof moneyColumns[number];
export type Settlement = Record<MoneyColumn, string> & {
  delivery_confirmed: boolean; can_settle: boolean; issues: Issue[]; sources: Record<string, number[]>;
};
export interface Investigation {
  id: number; trip_id: number; revision: number; mode: 'model' | 'demo';
  status: 'investigating' | 'completed' | 'failed' | 'awaiting_response'; summary: string;
  question: string | null; recipient: string | null; evidence_ids: number[];
  steps: { tool: string; args: unknown; result: unknown }[]; created_at: string;
}
export interface Action {
  id: number; trip_id: number; revision: number; kind: 'followup'; recipient: string;
  message: string; evidence_ids: number[]; status: 'pending' | 'approved' | 'rejected' | 'stale'; created_at: string;
}
export interface Audit {
  id: number; trip_id: number | null; actor: string; event: string; detail: Record<string, unknown>; created_at: string;
}
export interface TripDetail {
  trip: Trip; evidence: Evidence[]; settlement: Settlement; investigations: Investigation[]; actions: Action[]; audit: Audit[];
}
export interface TripSummary extends Trip {
  invoice_bdt: string; received_bdt: string; outstanding_bdt: string; expense_bdt: string;
  advance_bdt: string; advance_balance_bdt: string; evidence_count: number; exceptions_count: number;
}
export interface QueueData {
  trips: TripSummary[];
  overview: { trips: number; exceptions: number; outstanding_bdt: string; pending_approvals: number };
}
export interface ProviderStatus {
  model_configured: boolean; model_name: string | null; vision_configured: boolean; stt_configured: boolean;
  mode: 'model' | 'demo'; external_delivery: 'draft_only'; demo: true; auth_required: boolean;
  judge_mode?: boolean; uploads_enabled?: boolean; judge_runs_remaining?: number | null;
}
export interface EvidenceFields {
  kind: EvidenceKind; amount_bdt: string | null; transaction_id: string | null;
  trip_ref: string | null; note: string | null; text: string | null; delivered: boolean | null;
}
export type NewEvidence = EvidenceFields & { title: string };
export interface NewTrip {
  code: string; customer: string; driver: string; truck: string; origin: string; destination: string;
}
