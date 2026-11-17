import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { type AcceptedUpload, FLIGHT_FIELDS, type FlightsJob, type LocalPreview, type ObservationPage, PAGE_SIZE, POLL_INTERVAL, MAX_POLLS, localPreview, validJobId } from "./flights";

function RawCell({ value }: { value: string }) {
  return value === "" ? <span className="text-muted-foreground" aria-label="Empty string">∅</span> : <span className="raw-value">{value}</span>;
}
function failure(error: unknown) { return error instanceof TypeError ? "The backend could not be reached. Check its connection and try again." : error instanceof Error ? error.message : "The request could not be completed."; }

function DatasetJob({ id, recordsOnly = false }: { id: number; recordsOnly?: boolean }) {
  const [job, setJob] = useState<FlightsJob | null>(null);
  const [error, setError] = useState("");
  const [paused, setPaused] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [page, setPage] = useState(1);
  const [observations, setObservations] = useState<ObservationPage | null>(null);
  const [observationError, setObservationError] = useState("");
  const [observationRetry, setObservationRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    setError(""); setPaused(false);
    const poll = async () => {
      try {
        deadline = setTimeout(() => { setError("The status request timed out. Check the connection and retry explicitly."); controller.abort(); }, 15000);
        const result = await api<FlightsJob>(`/api/v1/flights/jobs/${id}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (!result || typeof result !== "object" || result.id !== id || result.job_kind !== "raha_flights_v1" || result.contract_version !== 1 ||
            !["pending", "queued", "processing", "completed", "failed"].includes(result.status) ||
            !Number.isInteger(result.observation_count) || result.observation_count < 0 ||
            typeof result.filename_original !== "string" || !/^[0-9a-f]{64}$/.test(result.input_sha256) ||
            !Number.isInteger(result.file_size) || result.file_size < 0 || !Number.isInteger(result.attempts) ||
            typeof result.observations_available !== "boolean" || !Array.isArray(result.issues)) throw new Error("Unexpected Flights job response. No completion was confirmed.");
        setJob(result);
        attempts++;
        if (!["completed", "failed"].includes(result.status)) {
          if (attempts < MAX_POLLS) timer = setTimeout(poll, POLL_INTERVAL);
          else setPaused(true);
        }
      } catch (reason) { if (!controller.signal.aborted) setError(failure(reason)); }
      finally { clearTimeout(deadline); }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); clearTimeout(deadline); };
  }, [id, refresh]);
  useEffect(() => {
    if (job?.status !== "completed" || !job.observations_available) return;
    const controller = new AbortController();
    setObservations(null); setObservationError("");
    const deadline = setTimeout(() => { setObservationError("The observations request timed out. Retry explicitly."); controller.abort(); }, 15000);
    api<ObservationPage>(`/api/v1/flights/jobs/${id}/observations?page=${page}&page_size=${PAGE_SIZE}`, { signal: controller.signal })
      .then(result => {
        if (controller.signal.aborted) return;
        if (!result || typeof result !== "object" || result.job_id !== id || result.page !== page || result.page_size !== PAGE_SIZE || !Number.isInteger(result.total) || result.total < 0 ||
            !Array.isArray(result.observations) || result.observations.length > PAGE_SIZE || result.total !== job.observation_count ||
            new Set(result.observations.map(row => row.tuple_id)).size !== result.observations.length ||
            result.observations.some(row => !Number.isInteger(row.row_number) || !FLIGHT_FIELDS.every(field => typeof row[field] === "string") || !Array.isArray(row.issues)))
          throw new Error("Unexpected observation response. Refresh the preview.");
        setObservations(result);
      }).catch(reason => { if (!controller.signal.aborted) setObservationError(failure(reason)); }).finally(() => clearTimeout(deadline));
    return () => { controller.abort(); clearTimeout(deadline); };
  }, [id, job?.status, job?.observations_available, page, observationRetry]);
  const metadata = job && (
    <dl className="surface-section grid gap-x-8 gap-y-5 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div><dt className="text-muted-foreground">Contract</dt><dd className="mt-1 font-medium">{job.job_kind}</dd></div>
        <div><dt className="text-muted-foreground">Stored observations</dt><dd className="mt-1 font-medium tabular-nums">{job.status === "completed" ? job.observation_count.toLocaleString() : "Available on completion"}</dd></div>
        <div><dt className="text-muted-foreground">Original file</dt><dd className="mt-1 tabular-nums">{job.file_size.toLocaleString()} bytes</dd></div>
        <div><dt className="text-muted-foreground">Worker attempts</dt><dd className="mt-1 tabular-nums">{job.attempts}</dd></div>
        <div className="sm:col-span-2 lg:col-span-4"><dt className="text-muted-foreground">Original SHA-256</dt><dd className="mt-1 break-all font-mono text-xs">{job.input_sha256}</dd></div>
      </dl>
  );
  return <section className="working-surface mt-6" aria-labelledby="import-status-title">
    <div className="surface-section flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-xs text-muted-foreground">Import #{id}</p><h2 id="import-status-title" className="mt-2 break-words text-xl font-semibold">{job?.filename_original ?? `Flights import #${id}`}</h2></div>
      {job && <Badge variant={job.status === "completed" ? "success" : job.status === "failed" ? "error" : "default"}>{job.status}</Badge>}
    </div>
    {error && <div className="surface-section" role="alert"><p className="notice-error">{error}</p><Button className="mt-3" variant="outline" onClick={() => setRefresh(value => value + 1)}>Retry status</Button></div>}
    {!job && !error && <p role="status" className="surface-section">Loading the server’s job status…</p>}
    {job && <>
      <div className="surface-section" aria-live="polite">
        <p className="text-sm">{job.status === "completed" ? "Import completed. Source values are unchanged and still require review." : job.status === "failed" ? "Import failed. No completed dataset is being presented." : job.status === "processing" ? "The worker is parsing and persisting source observations." : "The server accepted this job; it is waiting for processing."}</p>
        {(paused || (error && !["completed", "failed"].includes(job.status))) && <div className="mt-3"><p className="text-sm text-warning">{paused ? "Automatic checks paused after 60 requests. This is not a job failure." : "The status above is the last confirmed response."}</p><Button className="mt-3" variant="outline" onClick={() => setRefresh(value => value + 1)}>Check status again</Button></div>}
        {job.error_message && <p role="alert" className="notice-error mt-4">{job.error_message}</p>}
        {!!job.issues.length && <ul className="mt-3 space-y-2 text-sm" aria-label="Import diagnostics">{job.issues.map((issue, index) => <li key={index} className="text-danger">{issue.row_number !== null ? `Record ${issue.row_number}: ` : ""}{issue.message}</li>)}</ul>}
      </div>
      {recordsOnly ? <details className="source-import-details"><summary>Import details</summary>{metadata}</details> : metadata}

      {job.status === "completed" && job.observations_available && <div className="surface-section">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4"><div><h3 className="text-lg font-semibold">Raw observations</h3><p className="mt-1 text-sm text-muted-foreground">Original decoded strings. ∅ marks an empty string.</p></div>
          <Button asChild variant="accent"><Link to={`/investigate?dataset=${id}`}>Investigate evidence <span aria-hidden="true">↗</span></Link></Button></div>
        <p className="mb-4 text-xs text-muted-foreground">Review evidence before approving values.</p>
        {observationError ? <div role="alert"><p className="notice-error">{observationError}</p><Button className="mt-3" variant="outline" onClick={() => setObservationRetry(value => value + 1)}>Retry observations</Button></div> : !observations ? <p role="status">Loading persisted observations…</p> : <>
          <div className="table-scroll" tabIndex={0} role="region" aria-label="Persisted observations table"><table className="flight-table"><caption className="sr-only">Persisted source observations for import {id}</caption><thead><tr><th scope="col">Record</th>{FLIGHT_FIELDS.map(field => <th scope="col" key={field}>{field}</th>)}<th scope="col">Issues</th></tr></thead><tbody>{observations.observations.map(row => <tr key={row.tuple_id}><td>{row.row_number}</td>{FLIGHT_FIELDS.map(field => <td key={field}><RawCell value={row[field]} /></td>)}<td>{row.issues.length ? row.issues.map(issue => issue.message).join("; ") : "None"}</td></tr>)}</tbody></table></div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm"><p>Page {page} · {observations.total.toLocaleString()} observations · {PAGE_SIZE} per page</p><div className="flex gap-2"><Button variant="outline" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous observations</Button><Button variant="outline" disabled={page * PAGE_SIZE >= observations.total} onClick={() => setPage(value => value + 1)}>Next observations</Button></div></div>
        </>}
      </div>}
    </>}
  </section>;
}

export function DatasetsPage({ datasetId, invalidId = false }: { datasetId: number | null; invalidId?: boolean }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<LocalPreview | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [existingId, setExistingId] = useState("");
  const [idError, setIdError] = useState("");
  const upload = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const uploadDeadline = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => { upload.current?.abort(); clearTimeout(uploadDeadline.current); }, []);
  useEffect(() => {
    setPreview(null); setPreviewError("");
    if (!file) { setPreviewLoading(false); return; }
    const controller = new AbortController(); setPreviewLoading(true);
    localPreview(file, controller.signal).then(value => { if (!controller.signal.aborted) setPreview(value); })
      .catch(error => { if (!controller.signal.aborted) setPreviewError(failure(error)); })
      .finally(() => { if (!controller.signal.aborted) setPreviewLoading(false); });
    return () => controller.abort();
  }, [file]);
  const open = (id: number, accepted = false) => {
    const params = new URLSearchParams(location.search); params.delete("job"); params.set("dataset", String(id));
    navigate({ pathname: "/datasets", search: `?${params}` }, { state: accepted ? { acceptedDataset: id } : null });
  };
  const submit = async () => {
    if (!file || uploading) return;
    const controller = new AbortController(); upload.current = controller;
    setUploading(true); setUploadError("");
    const deadline = uploadDeadline.current = setTimeout(() => { controller.abort(); setUploading(false); setUploadError("Upload response timed out. Acceptance is unknown; the server may have accepted the file. Check before submitting again."); }, 60000);
    const data = new FormData(); data.append("file", file);
    try {
      const response = await api<AcceptedUpload>("/api/v1/flights/uploads", { method: "POST", body: data, signal: controller.signal });
      if (controller.signal.aborted) return;
      if (!response || typeof response.job_id !== "number" || !validJobId(String(response.job_id))) throw new Error("The upload response did not identify a valid job. Acceptance could not be confirmed.");
      open(response.job_id, true);
    } catch (error) {
      if (!controller.signal.aborted) {
        const uncertain = !(error instanceof ApiError) || error.status >= 500;
        setUploadError(failure(error) + (uncertain ? " No completion was confirmed. The server may have accepted the file; check before submitting again." : ""));
      }
    } finally { clearTimeout(deadline); if (!controller.signal.aborted) setUploading(false); }
  };
  const recordsOnly = datasetId !== null && new URLSearchParams(location.search).get("view") === "records";
  if (recordsOnly) {
    let context = typeof location.state?.investigateReturn === "string" ? new URLSearchParams(location.state.investigateReturn) : new URLSearchParams();
    if (validJobId(context.get("dataset")) !== datasetId) context = new URLSearchParams();
    context.set("dataset", String(datasetId)); context.set("view", "table"); context.delete("discrepancy"); context.delete("job");
    return <section className="workspace-container datasets-page records-page">
      <div className="page-introduction"><h1 className="workspace-title">Source records</h1><p className="mt-3 text-muted-foreground">Inspect the original reports from this Flights import. Source values are unchanged.</p></div>
      <nav aria-label="Source record navigation" className="dataset-view-navigation"><Link to={`/investigate?${context}`}>Back to cases</Link><Link to={`/datasets?dataset=${datasetId}`}>Dataset details and upload</Link></nav>
      <DatasetJob key={datasetId} id={datasetId} recordsOnly />
    </section>;
  }
  return <section className="workspace-container datasets-page">
    <div className="page-introduction"><h1 className="workspace-title">Import a dataset</h1><p className="mt-3 max-w-2xl text-muted-foreground">Upload a Flights CSV to find disagreements between reported values.</p></div>
    {invalidId && <p role="alert" className="canvas-notice mt-5">The dataset identifier is invalid. Use a positive import number.</p>}
    {location.state?.acceptedDataset === datasetId && datasetId !== null && <p role="status" className="canvas-notice mt-5">Upload accepted · Import #{datasetId}. Processing status is shown below.</p>}
    <section className="working-surface mt-8" aria-labelledby="upload-flights-title">
      <div className="surface-section">
          <h2 id="upload-flights-title" className="sr-only">Flights CSV upload</h2>
          <label htmlFor="flights-file" className="text-sm font-semibold">Flights observation CSV</label>
          <input ref={input} id="flights-file" type="file" accept=".csv,text/csv" disabled={uploading} className="flight-file mt-3" aria-describedby="file-guidance required-columns" onChange={event => { setFile(event.target.files?.[0] ?? null); setUploadError(""); }} />
          <p id="file-guidance" className="mt-3 text-sm text-muted-foreground">Supported format: <code>raha_flights_v1</code>. Upload original source observations.</p>
          <p id="required-columns" className="mt-2 text-xs leading-relaxed text-muted-foreground"><span className="font-medium">Required columns:</span> {FLIGHT_FIELDS.map((field, i) => <span key={field}><code>{field}</code>{i < FLIGHT_FIELDS.length - 1 ? ", " : "."}</span>)}</p>
          {file && <p className="mt-4 break-words text-sm"><strong>{file.name}</strong><span className="mt-1 block text-muted-foreground">{file.size.toLocaleString()} bytes · Local selection</span></p>}
          <div className="mt-5 flex flex-wrap gap-3"><Button variant="accent" disabled={!file || uploading} onClick={() => void submit()}>{uploading ? "Uploading original CSV…" : "Import observations"}</Button>{file && !uploading && <Button variant="outline" onClick={() => { setFile(null); if (input.current) input.current.value = ""; }}>Clear selection</Button>}{uploading && <Button variant="outline" onClick={() => { upload.current?.abort(); clearTimeout(uploadDeadline.current); setUploading(false); setUploadError("Stopped waiting for the upload response. This does not cancel a job already accepted by the server."); }}>Stop waiting</Button>}</div>
          {uploading && <p role="status" className="mt-3 text-sm">Sending the file. No job completion has been confirmed.</p>}
          {uploadError && <p role="alert" className="notice-error mt-4">{uploadError}</p>}
      </div>
      {file && <div className="surface-section"><div className="flex flex-wrap items-baseline justify-between gap-3"><h3 className="font-semibold">Local preview</h3><span className="text-xs text-muted-foreground">Up to 5 records · First 64 KiB only</span></div>
        <p className="mt-2 text-xs text-muted-foreground">Original strings shown as supplied. The server validates the full file.</p>
        {previewLoading && <p role="status" className="mt-4">Reading a bounded local preview…</p>}{previewError && <p role="status" className="mt-4 text-sm text-warning">{previewError}</p>}
        {preview && <><div className="table-scroll mt-4" tabIndex={0} role="region" aria-label="Local CSV preview"><table className="flight-table"><caption className="sr-only">Actual selected CSV headers and bounded sample rows</caption><thead><tr>{preview.headers.map((header, index) => <th scope="col" key={index}><RawCell value={header} /></th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{row.map((value, cell) => <td key={cell}><RawCell value={value} /></td>)}</tr>)}</tbody></table></div>
          {preview.headers.join(",") !== FLIGHT_FIELDS.join(",") && <p className="mt-3 text-sm text-warning">The preview header differs from the supported contract. The backend will decide whether to accept the file.</p>}{preview.prefixLimited && <p className="mt-3 text-xs text-muted-foreground">Only the bounded file prefix was read. Later content has not been inspected.</p>}</>}
      </div>}
    </section>
    <form className="mt-6 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); const id = validJobId(existingId); if (id) open(id); else setIdError("Enter a valid positive import number."); }}>
      <div className="min-w-0"><label htmlFor="existing-import" className="text-sm">Open an existing Flights import</label><input id="existing-import" inputMode="numeric" aria-invalid={!!idError} aria-describedby={idError ? "existing-import-error" : undefined} className="field mt-2 max-w-xs" value={existingId} onChange={event => { setExistingId(event.target.value); setIdError(""); }} placeholder="Import number" /></div><Button variant="outline" type="submit" disabled={uploading}>Open import</Button>
    </form>{idError && <p id="existing-import-error" role="alert" className="mt-3 text-sm">{idError}</p>}
    {datasetId !== null && <DatasetJob key={datasetId} id={datasetId} />}

  </section>;
}
