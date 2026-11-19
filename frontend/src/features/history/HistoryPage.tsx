import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { type FlightsJob, validJobId } from "../datasets/flights";
import { type History, type QueuePage, type Review, base, message, readable, request } from "../investigate/contracts";
import { type JobPage, pageNumber } from "./contracts";
import { ExportPanel } from "./ExportPanel";

function DecisionHistory({job, id}: {job: number; id: string}) {
  const [review, setReview] = useState<Review | null>(null); const [history, setHistory] = useState<History | null>(null);
  const [page, setPage] = useState(1); const [refresh, setRefresh] = useState(0); const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController(); setError(""); setHistory(null); setReview(null);
    Promise.all([request<Review>(`${base(job, id)}/review`, abort.signal), request<History>(`${base(job, id)}/review/history?page=${page}&page_size=5`, abort.signal)])
      .then(([current, events]) => {if (abort.signal.aborted) return;
        if (current.job_id !== job || current.discrepancy_id !== id || events.page !== page || events.page_size !== 5 || !Array.isArray(events.events) || events.events.length > 5 || events.events.some(e => e.job_id !== job || e.discrepancy_id !== id)) throw new Error("Inconsistent decision history scope.");
        setReview(current); setHistory(events);
      }).catch(reason => {if (!abort.signal.aborted) setError(message(reason));});
    return () => abort.abort();
  }, [job, id, page, refresh]);
  return <div className="mt-5 border-t border-border pt-5">{error ? <div role="alert"><p className="notice-error">{error}</p><Button className="mt-3" variant="outline" onClick={() => setRefresh(v => v + 1)}>Retry decision history</Button></div> : !review || !history ? <p role="status">Loading current review and historical events…</p> : <>
    {history.events.some(event => event.revision > review.revision) && <p role="alert" className="notice-error mb-4">Newer history arrived after the current-review read. Refresh before interpreting the effective decision.</p>}
    <Button variant="outline" className="mb-4" onClick={() => setRefresh(v => v + 1)}>Refresh selected review</Button>
    <div className="flex flex-wrap gap-3 items-center"><h4 className="font-semibold">Current review</h4><Badge variant={review.stale ? "warning" : review.state === "accepted" || review.state === "overridden" ? "success" : "default"}>{review.stale ? "stale" : review.state}</Badge></div>
    <p className="mt-2 text-sm">Revision {review.revision} · {review.resolution && !review.stale ? review.resolution.canonical_clock : "No current approved value"}</p>
    <Link className="mt-3 inline-block underline underline-offset-4 text-sm" to={`/investigate?dataset=${job}&discrepancy=${encodeURIComponent(id)}`}>Inspect evidence or revise this field</Link>
    {!history.total && <p className="mt-4 text-sm">No human review events recorded for this field.</p>}
    <ol className="mt-4 space-y-4">{history.events.map(event => <li key={event.id} className="text-sm"><div className="flex flex-wrap gap-2 items-center"><strong>Revision {event.revision} · {readable(event.action)}</strong><Badge>{event.revision > review.revision ? "Newer event · refresh review" : event.id === review.decision?.id ? review.stale ? "Latest event · stale" : "Current event" : "Superseded event"}</Badge></div><p className="mt-1">{event.resolution?.canonical_clock ?? "No approved value in this event"} · {event.reviewer_label} (unverified local label)</p><p className="text-xs">{event.created_at}</p><p className="mt-2 raw-value">{event.rationale}</p><details className="mt-2 text-xs"><summary>Event provenance</summary><dl className="evidence-references"><dt>Event ID</dt><dd>{event.id}</dd><dt>Evidence digest</dt><dd>{event.evidence_digest}</dd><dt>Candidate</dt><dd>{event.candidate_id ?? "None"}</dd><dt>AI investigation</dt><dd>{event.investigation_id ?? "None"}</dd><dt>Original manual entry</dt><dd className="raw-value">{event.manual_value ?? "None"}</dd><dt>Origin</dt><dd>{event.resolution?.origin ?? "No resolution"}</dd><dt>Supporting observations</dt><dd>{event.resolution?.supporting_observation_ids.join(" · ") || "None"}</dd></dl></details></li>)}</ol>
    <div className="mt-4 flex flex-wrap gap-3"><Button variant="outline" disabled={page === 1} onClick={() => setPage(v => v - 1)}>Previous decision events</Button><span className="self-center text-xs">Page {page} · {history.total} events</span><Button variant="outline" disabled={page * 5 >= history.total} onClick={() => setPage(v => v + 1)}>Next decision events</Button></div>
  </>}</div>;
}

function SelectedJob({job, discrepancy, selectField}: {job: number; discrepancy: string | null; selectField: (id: string) => void}) {
  const [detail, setDetail] = useState<FlightsJob | null>(null); const [error, setError] = useState(""); const [refresh, setRefresh] = useState(0);
  const [fieldsRefresh, setFieldsRefresh] = useState(0);
  const [fields, setFields] = useState<QueuePage | null>(null); const [fieldsError, setFieldsError] = useState(""); const [page, setPage] = useState(1);
  useEffect(() => {
    const abort = new AbortController(); setDetail(null); setError("");
    request<FlightsJob>(base(job), abort.signal).then(value => {if (abort.signal.aborted) return; if (value?.id !== job || value.job_kind !== "raha_flights_v1" || value.contract_version !== 1) throw new Error("Unsupported Flights job contract."); setDetail(value);}).catch(reason => {if (!abort.signal.aborted) setError(message(reason));});
    return () => abort.abort();
  }, [job, refresh]);
  useEffect(() => {
    if (detail?.status !== "completed") return;
    const abort = new AbortController(); setFields(null); setFieldsError("");
    request<QueuePage>(`${base(job)}/discrepancies?kind=all&page=${page}&page_size=15`, abort.signal).then(value => {if (abort.signal.aborted) return; if (value.job_id !== job || value.page !== page || value.page_size !== 15 || !Array.isArray(value.discrepancies) || value.discrepancies.length > 15) throw new Error("Inconsistent field listing."); setFields(value);}).catch(reason => {if (!abort.signal.aborted) setFieldsError(message(reason));});
    return () => abort.abort();
  }, [job, detail?.status, page, fieldsRefresh]);
  return <section className="working-surface mt-7" aria-labelledby="selected-history-title"><div className="surface-section"><p className="text-xs text-muted-foreground">Import #{job}</p><h2 id="selected-history-title" className="mt-2 break-words text-2xl font-semibold">{detail?.filename_original ?? `Import #${job}`}</h2>
    {error ? <div role="alert"><p className="notice-error mt-3">{error}</p><Button variant="outline" className="mt-3" onClick={() => setRefresh(v => v + 1)}>Retry selected dataset</Button></div> : !detail ? <p role="status" className="mt-3">Loading selected dataset…</p> : <>
      <Badge className="mt-3" variant={detail.status === "failed" ? "error" : "default"}>{detail.status}</Badge><p className="mt-3 text-sm">{detail.status === "completed" ? `${detail.observation_count} observations imported. Values still require review.` : "Review and export creation require a completed import."}</p>{detail.error_message && <p role="alert" className="notice-error mt-3">{detail.error_message}</p>}
      <div className="mt-4 flex flex-wrap gap-4 text-sm"><Link className="underline underline-offset-4" to={`/datasets?dataset=${job}`}>View source dataset</Link>{detail.status === "completed" && <Link className="underline underline-offset-4" to={`/investigate?dataset=${job}`}>Investigate this dataset</Link>}</div>
      <details className="mt-4 text-xs"><summary>Import metadata and provenance</summary><dl className="evidence-references mt-2"><dt>Contract</dt><dd>{detail.job_kind} · version {detail.contract_version}</dd><dt>Created / processed</dt><dd>{detail.created_at} / {detail.processed_at ?? "Not completed"}</dd><dt>Input bytes / attempts</dt><dd>{detail.file_size} / {detail.attempts}</dd><dt>Input SHA-256</dt><dd>{detail.input_sha256}</dd></dl>{detail.issues.map((issue, i) => <p key={i} className="mt-2">{issue.code}: {issue.message}</p>)}</details>
      {detail.status !== "completed" && <Button variant="outline" className="mt-4" onClick={() => setRefresh(v => v + 1)}>Refresh import status</Button>}
    </>}</div>
    {detail?.status === "completed" && <><ExportPanel job={job} /><section className="surface-section"><h3 className="text-xl font-semibold">Field decisions</h3><p className="mt-2 text-sm text-muted-foreground">Choose a field to view its decisions and revisions.</p>
      {fieldsError && <div role="alert"><p className="notice-error mt-3">{fieldsError}</p><Button className="mt-3" variant="outline" onClick={() => setFieldsRefresh(v => v + 1)}>Retry field choices</Button></div>}{!fields && !fieldsError && <p role="status" className="mt-3">Loading fields…</p>}
      {fields && <><label className="block mt-4 text-sm font-medium">Field history<select className="field mt-2" value={fields.discrepancies.some(f => f.discrepancy_id === discrepancy) ? discrepancy! : ""} onChange={event => {if (event.target.value) selectField(event.target.value);}}><option value="">Select from this page</option>{fields.discrepancies.map(item => <option key={item.discrepancy_id} value={item.discrepancy_id}>{item.flight} · {readable(item.field)}{item.requires_attention ? " · attention required" : " · observed agreement"}</option>)}</select></label><div className="mt-3 flex flex-wrap gap-3"><Button variant="outline" disabled={page === 1} onClick={() => setPage(v => v - 1)}>Previous field page</Button><span className="self-center text-xs">Page {page} · {fields.total} fields</span><Button variant="outline" disabled={page * 15 >= fields.total} onClick={() => setPage(v => v + 1)}>Next field page</Button></div>{fields.ungroupable_observation_count > 0 && <p className="mt-3 text-sm text-warning">{fields.ungroupable_observation_count} ungroupable observations remain visible in source data and export exceptions.</p>}</>}
      {discrepancy && (discrepancy.length <= 80 ? <DecisionHistory key={discrepancy} job={job} id={discrepancy} /> : <p role="alert" className="notice-error mt-3">Invalid discrepancy identifier.</p>)}
    </section></>}
  </section>;
}

export function HistoryPage() {
  const location = useLocation(); const navigate = useNavigate(); const params = new URLSearchParams(location.search);
  const selected = validJobId(params.get("dataset")); const page = pageNumber(params.get("jobs_page"));
  const status = ["pending", "queued", "processing", "completed", "failed"].includes(params.get("status") ?? "") ? params.get("status")! : "";
  const [jobs, setJobs] = useState<JobPage | null>(null); const [error, setError] = useState(""); const [refresh, setRefresh] = useState(0);
  const update = (values: Record<string, string | null>) => {const next = new URLSearchParams(location.search); next.delete("job"); Object.entries(values).forEach(([key, value]) => value === null ? next.delete(key) : next.set(key, value)); navigate(`/history?${next}`);};
  useEffect(() => {
    const abort = new AbortController(); setJobs(null); setError("");
    request<JobPage>(`/api/v1/flights/jobs?page=${page}&page_size=15${status ? `&status=${status}` : ""}`, abort.signal).then(value => {if (abort.signal.aborted) return; if (value.page !== page || value.page_size !== 15 || !Array.isArray(value.jobs) || value.jobs.length > 15 || !Number.isInteger(value.total) || value.total < 0 || value.jobs.some(job => job.job_kind !== "raha_flights_v1")) throw new Error("Inconsistent Flights history response."); setJobs(value);}).catch(reason => {if (!abort.signal.aborted) setError(message(reason));});
    return () => abort.abort();
  }, [page, status, refresh]);
  return <section className="workspace-container history-page"><div className="page-introduction"><h1 className="workspace-title">History</h1><p className="mt-3 max-w-2xl text-muted-foreground">View previous datasets, review decisions, and download results.</p></div>
    <section className="working-surface mt-7 surface-section" aria-labelledby="history-list-title"><div className="flex flex-wrap justify-between items-start gap-4"><div><h2 id="history-list-title" className="text-xl font-semibold">Flights imports</h2><p className="mt-2 text-sm text-muted-foreground">Your imports and their processing status.</p></div><Button variant="outline" onClick={() => setRefresh(v => v + 1)}>Refresh imports</Button></div>
      <label className="block mt-5 max-w-xs text-sm font-medium">Processing status<select className="field mt-2" value={status} onChange={event => update({status: event.target.value || null, jobs_page: null})}><option value="">All processing states</option>{["pending", "queued", "processing", "completed", "failed"].map(state => <option key={state} value={state}>{state}</option>)}</select></label>
      {params.has("dataset") && !selected && <p role="alert" className="notice-error mt-4">Invalid dataset identifier. Choose a Flights import below.</p>}
      {error ? <p role="alert" className="notice-error mt-4">{error}</p> : !jobs ? <p role="status" className="mt-5">Loading Flights import history…</p> : <>
        {!jobs.jobs.length ? <p className="mt-5 text-sm">{page === 1 && !status ? "No datasets yet." : "No datasets match this page and filter."} <Link className="underline" to="/datasets">Upload a CSV to get started.</Link></p> : <div className="table-scroll mt-5" tabIndex={0} role="region" aria-label="Flights import history"><table className="flight-table"><caption className="sr-only">Persisted Flights imports</caption><thead><tr>{["Import", "Created", "Processing", "Contract", "Observations", "Actions"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{jobs.jobs.map(job => <tr key={job.id} aria-selected={selected === job.id}><td><Button className="history-job-button" variant="ghost" onClick={() => update({dataset: String(job.id), discrepancy: null})}>#{job.id} · {job.filename_original}</Button>{job.error_message && <p className="mt-2 text-xs text-danger">{job.error_message}</p>}</td><td>{job.created_at}</td><td><Badge variant={job.status === "failed" ? "error" : "default"}>{job.status}</Badge></td><td>{job.job_kind}<br />v{job.contract_version ?? "unknown"}</td><td>{job.status === "completed" ? job.observation_count : "Not completed"}</td><td><Link className="underline" to={`/datasets?dataset=${job.id}`}>Dataset</Link>{job.status === "completed" && <Link className="block mt-2 underline" to={`/investigate?dataset=${job.id}`}>Investigate</Link>}</td></tr>)}</tbody></table></div>}
        {(jobs.total > 0 || page > 1) && <div className="mt-4 flex flex-wrap items-center gap-3"><span className="mr-auto text-sm">Page {page} · {jobs.total} imports</span><Button variant="outline" disabled={page === 1} onClick={() => update({jobs_page: String(page - 1)})}>Previous imports</Button><Button variant="outline" disabled={page * 15 >= jobs.total} onClick={() => update({jobs_page: String(page + 1)})}>Next imports</Button></div>}
      </>}
    </section>
    {selected && <SelectedJob key={selected} job={selected} discrepancy={params.get("discrepancy")} selectField={id => update({discrepancy: id})} />}

  </section>;
}
