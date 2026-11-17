import { api } from "../../lib/api";
export type Field = "sched_dep_time" | "act_dep_time" | "sched_arr_time" | "act_arr_time";
export const fields: Field[] = ["sched_dep_time", "act_dep_time", "sched_arr_time", "act_arr_time"];
export const fieldLabels: Record<Field, string> = {
  sched_dep_time: "Scheduled departure time", act_dep_time: "Actual departure time",
  sched_arr_time: "Scheduled arrival time", act_arr_time: "Actual arrival time",
};
export type Kind = "attention" | "conflict" | "uncertain" | "missing" | "all";
export type ParseStatus = "parsed" | "missing" | "placeholder" | "ambiguous" | "unsupported";
export interface Normalization { raw: string; status: ParseStatus; canonical_clock: string | null; precision: "minute" | "second" | null; qualifiers: string[]; reason: string | null; policy_version: string }
export interface Claim { tuple_id: string; row_number: number; src: string; source_usable: boolean; normalization: Normalization; identity_issues: {code: string; field: string | null; message: string}[] }
export interface Candidate {
  candidate_id: string; canonical_clock: string; precision: "minute" | "second"; qualifiers: string[]; raw_values: string[];
  supporting_observation_ids: string[]; supporting_source_ids: string[]; observation_support_count: number; distinct_source_support_count: number;
  contradicting_candidate_ids: string[]; contradicting_observation_ids: string[]; incomparable_candidate_ids: string[]; context_observation_ids: string[];
  detection_policy: string; normalization_policy: string;
}
export interface Flags { confirmed_conflict: boolean; has_missing: boolean; has_placeholders: boolean; has_ambiguous: boolean; has_unsupported: boolean; formatting_variation: boolean; incomparable_supported_values: boolean; unusable_source_identity: boolean; internal_source_conflict: boolean; insufficient_support: boolean }
export interface Baseline { status: "proposal" | "abstain"; candidate_id: string | null; abstention_reasons: string[]; policy_version: string; authoritative: false }
export interface Summary { discrepancy_id: string; flight: string; field: Field; observation_count: number; usable_source_count: number; candidate_count: number; counts: Record<ParseStatus, number>; flags: Flags; baseline: Baseline; requires_attention: boolean; summary: string; evidence_digest: string; detection_policy: string; normalization_policy: string }
export interface Evidence extends Omit<Summary, "candidate_count"> { job_id: number; claims: Claim[]; candidates: Candidate[]; candidate_state: "supported_candidates" | "no_supported_candidate"; internally_inconsistent_source_ids: string[] }
export interface QueuePage { job_id: number; discrepancies: Summary[]; total: number; page: number; page_size: number; ungroupable_observation_count: number; raw_observations_url: string }
export type AIStatus = "not_requested" | "running" | "proposed" | "abstained" | "unavailable" | "invalid_response" | "failed" | "stale" | "ineligible";
export interface Recommendation { recommendation: "propose" | "abstain"; candidate_id: string | null; supporting_claim_ids: string[]; contradicting_claim_ids: string[]; explanation: string; uncertainty: string }
export interface Investigation {
  id: string; request_id: string; job_id: number; discrepancy_id: string; evidence_digest: string; status: AIStatus; stored_status: AIStatus; current: boolean; authoritative: false;
  recommendation: Recommendation | null; claim_references: {claim_id: string; observation_id: string; source_id: string}[];
  provider: string | null; model: string | null; resolved_model: string | null; usage: Record<string, number>; error_code: string | null;
  policy_version: string; prompt_version: string; schema_version: string; created_at: string; completed_at: string | null;
}
export interface LatestAI { status: AIStatus; investigation: Investigation | null }
export interface Resolution { origin: "observed_candidate" | "human_assertion"; canonical_clock: string; precision: "minute" | "second"; qualifiers: string[]; supporting_observation_ids: string[]; supporting_source_ids: string[] }
export type Action = "accept" | "override" | "reject" | "unresolved";
export interface Decision { id: string; request_id: string; job_id: number; discrepancy_id: string; flight: string; field: Field; evidence_digest: string; revision: number; action: Action; candidate_id: string | null; investigation_id: string | null; manual_value: string | null; resolution: Resolution | null; rationale: string; reviewer_label: string; created_at: string }
export interface Review { job_id: number; discrepancy_id: string; evidence_digest: string; state: "unreviewed" | "accepted" | "overridden" | "rejected" | "unresolved"; stale: boolean; revision: number; decision: Decision | null; resolution: Resolution | null; reviewer_identity_verified: false }
export interface History { events: Decision[]; total: number; page: number; page_size: number }
export interface ReviewRequest { action: Action; expected_evidence_digest: string; expected_revision: number; request_id: string; reviewer_label: string; rationale: string; candidate_id?: string; investigation_id?: string; manual_value?: string }
export const base = (job: number, discrepancy?: string) => `/api/v1/flights/jobs/${job}${discrepancy ? `/discrepancies/${encodeURIComponent(discrepancy)}` : ""}`;
export const readable = (value: string) => value.replace(/_/g, " ");
export const message = (error: unknown) => error instanceof TypeError ? "The backend could not be reached. No new result was confirmed." : error instanceof Error ? error.message : "The request could not be completed.";
// A request deadline bounds waiting, not the outcome of a server-side write.
export async function request<T>(path: string, signal: AbortSignal, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener("abort", abort, { once: true });
  const timeout = setTimeout(abort, body ? 45000 : 15000);
  if (signal.aborted) controller.abort();
  try { return await api<T>(path, { signal: controller.signal, ...(body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {}) }); }
  catch (error) { if (controller.signal.aborted && !signal.aborted) throw new Error("The response timed out. Refresh reads; retry uncertain writes with the same request ID."); throw error; }
  finally { clearTimeout(timeout); signal.removeEventListener("abort", abort); }
}
export function validEvidence(value: Evidence, job: number, id: string) {
  return value?.job_id === job && value.discrepancy_id === id && /^sha256:[0-9a-f]{64}$/.test(value.evidence_digest) &&
    Array.isArray(value.claims) && Array.isArray(value.candidates) && value.claims.length <= 250 && value.candidates.length <= 64;
}
export function currentProposal(ai: LatestAI | null, evidence: Evidence): Investigation | null {
  const result = ai?.investigation;
  return result && result.current && result.status === "proposed" && result.authoritative === false && result.evidence_digest === evidence.evidence_digest &&
    result.job_id === evidence.job_id && result.discrepancy_id === evidence.discrepancy_id && result.recommendation?.recommendation === "propose" &&
    evidence.candidates.some(candidate => candidate.candidate_id === result.recommendation?.candidate_id) ? result : null;
}

// Selected-case bookmarks take precedence; bare datasets now open the overview.
export type InvestigateView = "overview" | "table" | "case";
export function investigateView(search: string): InvestigateView {
  const query = new URLSearchParams(search);
  if (query.get("discrepancy")) return "case";
  const view = query.get("view");
  if (view === "table" || view === "case") return "table";
  if (view !== null) return "overview";
  return ["kind", "field", "page"].some(key => query.has(key)) ? "table" : "overview";
}
export function investigateSearch(search: string, view: InvestigateView, values: Record<string, string | null> = {}) {
  const query = new URLSearchParams(search);
  query.delete("job");
  query.set("view", view);
  if (view !== "case") query.delete("discrepancy");
  Object.entries(values).forEach(([key, value]) => value === null ? query.delete(key) : query.set(key, value));
  return `?${query}`;
}
