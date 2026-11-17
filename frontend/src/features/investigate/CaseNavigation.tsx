import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { type Kind, type QueuePage, base, fields, investigateSearch, message, request } from "./contracts";

export function casePagePath(job: number, kind: Kind, field: string, page: number) {
  return `${base(job)}/discrepancies?kind=${kind}&page=${page}&page_size=15${field ? `&field=${field}` : ""}`;
}
export async function loadCasePage(job: number, kind: Kind, field: string, page: number, signal: AbortSignal) {
  const value = await request<QueuePage>(casePagePath(job, kind, field, page), signal);
  if (value.job_id !== job || value.page !== page || value.page_size !== 15 || !Array.isArray(value.discrepancies) || value.discrepancies.length > 15 || !Number.isSafeInteger(value.total) || value.total < 0 ||
    new Set(value.discrepancies.map(item => item.discrepancy_id)).size !== value.discrepancies.length ||
    value.discrepancies.some(item => !fields.includes(item.field) || typeof item.flight !== "string" || typeof item.discrepancy_id !== "string" || !item.discrepancy_id || item.discrepancy_id.length > 80 || !item.flags || !Number.isSafeInteger(item.observation_count) || item.observation_count < 0 || !Number.isSafeInteger(item.candidate_count) || item.candidate_count < 0)) {
    throw new Error("Unexpected discrepancy page. No complete queue was confirmed.");
  }
  return value;
}

export function CaseNavigation({job, id, data, loading, error, kind, field, page, search, remember, retry}: {
  job: number; id: string; data: QueuePage | null; loading: boolean; error: string; kind: Kind; field: string; page: number; search: string;
  remember: (data: QueuePage) => void; retry: () => void;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false); const [failure, setFailure] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => { setBusy(false); return () => controller.current?.abort(); }, [search]);
  useEffect(() => { setFailure(""); }, [data]);
  const index = data?.discrepancies.findIndex(item => item.discrepancy_id === id) ?? -1;
  const complete = data && data.page === page && data.discrepancies.length === Math.max(0, Math.min(15, data.total - (page - 1) * 15));
  const positioned = !!data && complete && index >= 0 && !loading && !error;
  const position = (page - 1) * 15 + index + 1;
  async function move(direction: -1 | 1) {
    if (!positioned || !data || busy) return;
    setFailure("");
    const adjacent = data.discrepancies[index + direction];
    if (adjacent) { navigate({pathname: "/investigate", search: investigateSearch(search, "case", {discrepancy: adjacent.discrepancy_id})}); return; }
    setBusy(true); controller.current = new AbortController();
    try {
      const nextPage = page + direction;
      const next = await loadCasePage(job, kind, field, nextPage, controller.current.signal);
      if (controller.current.signal.aborted) return;
      if (next.total !== data.total || next.discrepancies.length !== Math.min(15, next.total - (nextPage - 1) * 15) || !next.discrepancies.length || next.discrepancies.some(item => data.discrepancies.some(current => current.discrepancy_id === item.discrepancy_id))) throw new Error("The case selection changed. Return to Cases and refresh before continuing.");
      const selected = next.discrepancies[direction === 1 ? 0 : next.discrepancies.length - 1];
      remember(next);
      navigate({pathname: "/investigate", search: investigateSearch(search, "case", {page: String(nextPage), discrepancy: selected.discrepancy_id})});
    } catch (reason) { if (!controller.current.signal.aborted) setFailure(message(reason)); }
    finally { if (!controller.current.signal.aborted) setBusy(false); }
  }
  return <nav aria-label="Case navigation" className="case-navigation">
    <p className="text-xs text-muted-foreground" aria-live="polite">{loading ? "Loading case order…" : positioned ? `Case ${position} of ${data!.total} in this selection` : "Case position unavailable. Return to Cases to choose within your filters."}</p>
    <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={!positioned || busy || position <= 1} onClick={() => void move(-1)}>Previous case</Button><Button variant="outline" disabled={!positioned || busy || position >= (data?.total ?? 0)} onClick={() => void move(1)}>{busy ? "Loading next page…" : "Next case"}</Button></div>
    {(error || failure) && <p role="alert" className="text-sm notice-error">{error || failure} <button className="underline" onClick={retry}>Refresh case order</button></p>}
  </nav>;
}
