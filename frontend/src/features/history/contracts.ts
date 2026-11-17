import { apiResponse } from "../../lib/api";
import type { FlightStatus } from "../datasets/flights";
export interface JobSummary {id: number; job_kind: "raha_flights_v1"; contract_version: number | null; status: FlightStatus; filename_original: string; created_at: string; processed_at: string | null; file_size: number | null; observation_count: number; error_message: string | null}
export interface JobPage {jobs: JobSummary[]; total: number; page: number; page_size: number}
export interface Snapshot {job_id: number; snapshot_digest: string; field_count: number; ungroupable_observation_count: number}
export const artifacts = ["reviewed", "exceptions", "provenance"] as const;
export type Artifact = typeof artifacts[number];
export interface ReviewedExport {id: string; request_id: string; job_id: number; snapshot_digest: string; input_sha256: string; policy_version: string; artifacts: Record<Artifact, {sha256: string; bytes: number}>; created_at: string}
export interface ExportPage {exports: ReviewedExport[]; total: number; page: number; page_size: number}
export interface ExportRequest {expected_snapshot_digest: string; request_id: string}
export const hash = (value: string) => /^sha256:[0-9a-f]{64}$/.test(value);
export function validExport(e: ReviewedExport, job: number) {
  return e?.job_id === job && /^[0-9a-f]{32}$/.test(e.id) && hash(e.snapshot_digest) && /^[0-9a-f]{64}$/.test(e.input_sha256) && typeof e.policy_version === "string" &&
    artifacts.every(key => e.artifacts?.[key] && Number.isInteger(e.artifacts[key].bytes) && e.artifacts[key].bytes >= 0 && e.artifacts[key].bytes <= 32 * 1024 * 1024 && /^[0-9a-f]{64}$/.test(e.artifacts[key].sha256));
}
export async function artifactBlob(job: number, item: ReviewedExport, key: Artifact, signal: AbortSignal) {
  if (!validExport(item, job) || !artifacts.includes(key)) throw new Error("Invalid export or artifact identity.");
  const response = await apiResponse(`/api/v1/flights/jobs/${job}/exports/${item.id}/download/${key}`, {signal});
  const expected = item.artifacts[key].bytes;
  const chunks: ArrayBuffer[] = []; let size = 0;
  const reader = response.body?.getReader();
  if (reader) {
    try {
      for (;;) {
        const {done, value} = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > expected) {await reader.cancel(); throw new Error("Artifact size differs from published metadata. No download was prepared.");}
        chunks.push(value.slice().buffer as ArrayBuffer);
      }
    } finally {reader.releaseLock();}
  }
  if (size !== expected) throw new Error("Artifact size differs from published metadata. No download was prepared.");
  return new Blob(chunks, {type: key === "provenance" ? "application/json" : "text/csv"});
}
export function pageNumber(value: string | null) {return value && /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) > 0 && Number(value) <= 2147483647 ? Number(value) : 1;}
