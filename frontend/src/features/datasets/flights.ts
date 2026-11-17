import Papa from "papaparse";

export const FLIGHT_FIELDS = ["tuple_id", "src", "flight", "sched_dep_time", "act_dep_time", "sched_arr_time", "act_arr_time"] as const;
export const PREVIEW_ROWS = 5;
export const PAGE_SIZE = 25;
export const POLL_INTERVAL = 2000;
export const MAX_POLLS = 60;
export type FlightStatus = "pending" | "queued" | "processing" | "completed" | "failed";
export interface ImportIssue { code: string; field: string | null; row_number: number | null; message: string }
export interface FlightsJob {
  id: number; job_kind: "raha_flights_v1"; contract_version: number; status: FlightStatus;
  filename_original: string; filename_input_saved: string; input_sha256: string; file_size: number;
  created_at: string; processed_at: string | null; attempts: number; duration_ms: number;
  observation_count: number; observations_available: boolean; issues: ImportIssue[]; error_message: string | null;
}
export interface FlightObservation extends Record<typeof FLIGHT_FIELDS[number], string> { row_number: number; issues: ImportIssue[] }
export interface ObservationPage { job_id: number; observations: FlightObservation[]; total: number; page: number; page_size: number }
export interface AcceptedUpload { job_id: number; status: FlightStatus; message: string; status_url: string }
export interface LocalPreview { headers: string[]; rows: string[][]; prefixLimited: boolean }

export function validJobId(value: string | null): number | null {
  if (!value || !/^[0-9]+$/.test(value)) return null;
  const id = Number(value);
  return Number.isInteger(id) && id > 0 && id <= 2147483647 ? id : null;
}

export function localPreview(file: File, signal: AbortSignal): Promise<LocalPreview> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    const abort = () => { reader.abort(); reject(new DOMException("Preview canceled", "AbortError")); };
    if (signal.aborted) return abort();
    signal.addEventListener("abort", abort, { once: true });
    reader.onload = () => {
      signal.removeEventListener("abort", abort);
      if (signal.aborted) return;
      const result = Papa.parse<string[]>(String(reader.result), { preview: PREVIEW_ROWS + 1, skipEmptyLines: false, dynamicTyping: false });
      if (result.errors.some(error => error.code === "MissingQuotes")) {
        reject(new Error("The bounded preview could not read complete quoted records. The backend can still validate the original file.")); return;
      }
      const rows = [...result.data];
      if (!result.meta.truncated) {
        if (file.size > 65536) rows.pop(); // Never show a potentially cut final record as complete.
        else if (/[\r\n]$/.test(String(reader.result)) && rows.at(-1)?.length === 1 && rows.at(-1)?.[0] === "") rows.pop();
      }
      if (!rows.length) { reject(new Error("No complete header was available in the bounded preview. The original CSV can still be submitted.")); return; }
      resolve({ headers: rows[0], rows: rows.slice(1, PREVIEW_ROWS + 1), prefixLimited: file.size > 65536 });
    };
    reader.onerror = () => { signal.removeEventListener("abort", abort); reject(new Error("Local preview is unavailable. You can still submit the original CSV.")); };
    reader.readAsText(file.slice(0, 65536), "UTF-8");
  });
}
