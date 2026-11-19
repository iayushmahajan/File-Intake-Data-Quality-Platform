import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { base, message, request } from "../investigate/contracts";
import { type ExportPage, type ExportRequest, type ReviewedExport, type Snapshot, artifactBlob, artifacts, hash, validExport } from "./contracts";

export function ExportPanel({job}: {job: number}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [list, setList] = useState<ExportPage | null>(null);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [snapshotError, setSnapshotError] = useState("");
  const [writeError, setWriteError] = useState("");
  const [notice, setNotice] = useState("");
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef<ExportRequest | null>(null);
  const controller = useRef(new AbortController());
  const [download, setDownload] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const urls = useRef<string[]>([]);
  useEffect(() => {controller.current = new AbortController(); return () => {controller.current.abort(); urls.current.forEach(url => URL.revokeObjectURL(url));};}, []);
  useEffect(() => {
    const abort = new AbortController(); setLoading(true); setError(""); setSnapshotError(""); setSnapshot(null); setList(null);
    void (async () => {
      const results = await Promise.allSettled([request<ExportPage>(`${base(job)}/exports?page=${page}&page_size=5`, abort.signal), request<Snapshot>(`${base(job)}/exports/snapshot`, abort.signal)]);
      if (abort.signal.aborted) return;
      const [exports, snap] = results;
      if (exports.status === "fulfilled" && exports.value.page === page && exports.value.page_size === 5 && Number.isInteger(exports.value.total) && exports.value.total >= 0 && Array.isArray(exports.value.exports) && exports.value.exports.length <= 5 && exports.value.exports.every(e => validExport(e, job))) setList(exports.value);
      else setError(exports.status === "rejected" ? message(exports.reason) : "Inconsistent export metadata. Nothing was inferred as available.");
      if (snap.status === "fulfilled" && snap.value.job_id === job && hash(snap.value.snapshot_digest)) setSnapshot(snap.value);
      else setSnapshotError(snap.status === "rejected" ? message(snap.reason) : "Inconsistent current snapshot.");
      setLoading(false);
    })();
    return () => abort.abort();
  }, [job, page, refresh]);
  const create = async () => {
    if (busy || (!pending.current && (!snapshot || !ack))) return;
    const body = pending.current ?? {expected_snapshot_digest: snapshot!.snapshot_digest, request_id: crypto.randomUUID()}; pending.current = body;
    setBusy(true); setWriteError(""); setNotice("");
    try {
      const value = await request<ReviewedExport>(`${base(job)}/exports`, controller.current.signal, body);
      if (controller.current.signal.aborted) return;
      if (!validExport(value, job) || value.request_id !== body.request_id || value.snapshot_digest !== body.expected_snapshot_digest) throw new Error("Unexpected export receipt. Creation could not be confirmed.");
      pending.current = null; setUncertain(false); setAck(false); setNotice("The server recorded a frozen export. Artifact availability is checked when downloading."); setPage(1); setRefresh(v => v + 1);
    } catch (reason) {
      if (controller.current.signal.aborted) return;
      const ambiguous = !(reason instanceof ApiError) || reason.status >= 500;
      setUncertain(ambiguous); setWriteError(message(reason) + (ambiguous ? " The outcome is uncertain. Retry retains the exact request ID and snapshot." : ""));
      if (!ambiguous) pending.current = null;
      if (reason instanceof ApiError && reason.status === 409) {setAck(false); setRefresh(v => v + 1); setWriteError(message(reason) + " Refreshing the snapshot. Inspect it and acknowledge again; nothing was automatically resubmitted.");}
    } finally {if (!controller.current.signal.aborted) setBusy(false);}
  };
  const save = async (item: ReviewedExport, key: typeof artifacts[number]) => {
    if (download) return; setDownload(`${item.id}:${key}`); setDownloadError("");
    const abort = new AbortController(); const cancel = () => abort.abort(); controller.current.signal.addEventListener("abort", cancel, {once: true}); const timeout = setTimeout(cancel, 15000);
    try {
      const blob = await artifactBlob(job, item, key, abort.signal);
      if (abort.signal.aborted) return;
      const url = URL.createObjectURL(blob); urls.current.push(url);
      const link = document.createElement("a"); link.href = url; link.download = `${item.id}-${key}.${key === "provenance" ? "json" : "csv"}`; link.click();
      setTimeout(() => {URL.revokeObjectURL(url); urls.current = urls.current.filter(value => value !== url);}, 1000);
      setNotice(`${key === "provenance" ? "Provenance JSON" : key === "reviewed" ? "Reviewed CSV" : "Exceptions CSV"} download prepared. Frozen artifacts were not regenerated.`);
    } catch (reason) {if (!controller.current.signal.aborted) setDownloadError(abort.signal.aborted ? "Download timed out. Retry the existing artifact; no new export was created." : message(reason));}
    finally {clearTimeout(timeout); controller.current.signal.removeEventListener("abort", cancel); if (!controller.current.signal.aborted) setDownload("");}
  };
  return <section className="surface-section" aria-labelledby="exports-title"><h3 id="exports-title" className="mt-2 text-xl font-semibold">Exports & provenance</h3>
    <p className="mt-3 text-sm text-muted-foreground">Only approved values are included. Unreviewed, rejected, unresolved and stale fields stay empty and appear in exceptions. Each export is frozen.</p>
    {loading && <p role="status" className="mt-4">Loading frozen export history and the current snapshot…</p>}
    {snapshotError && <p role="alert" className="notice-error mt-4">Snapshot: {snapshotError}</p>}
    {snapshot && <div className="mt-4"><p className="text-sm">Current snapshot: {snapshot.field_count} fields · {snapshot.ungroupable_observation_count} ungroupable observations</p><details className="mt-2 text-xs"><summary>Inspect current snapshot identity</summary><p className="break-all mt-2 font-mono">{snapshot.snapshot_digest}</p></details></div>}
    <label className="mt-5 flex items-start gap-3 text-sm"><input className="mt-1 size-4 shrink-0" type="checkbox" disabled={busy || uncertain || !snapshot} checked={ack} onChange={event => setAck(event.target.checked)} /><span>I understand that unapproved fields stay empty and this creates a new frozen snapshot.</span></label>
    <div className="mt-4 flex flex-wrap gap-3"><Button variant="accent" disabled={busy || (!uncertain && (!ack || !snapshot || loading))} onClick={() => void create()}>{busy ? "Creating frozen export…" : uncertain ? "Retry exact export request" : "Create frozen export"}</Button><Button variant="outline" disabled={loading || busy} onClick={() => {setAck(false);setRefresh(v => v + 1);}}>Refresh export state</Button></div>
    {writeError && <p role="alert" className="notice-error mt-4">{writeError}</p>}{notice && <p role="status" className="mt-4 text-sm">{notice}</p>}
    {error && <p role="alert" className="notice-error mt-4">Export history: {error}</p>}{downloadError && <p role="alert" className="notice-error mt-4">{downloadError}</p>}
    {list && <><p className="mt-6 text-sm">{list.total} frozen exports · Page {page}</p>{!list.exports.length && <p className="mt-3 text-sm text-muted-foreground">No frozen exports on this page. Creating one requires your explicit action above.</p>}
      <ol className="mt-4 space-y-5">{list.exports.map((item, i) => <li key={item.id} className="export-entry"><h4 className="font-semibold">Frozen export · {item.created_at}</h4><p className="mt-1 text-xs text-muted-foreground">{item.policy_version} · Import #{item.job_id}</p>
        <details className="mt-3 text-xs"><summary>Inspect export {i + 1} metadata</summary><dl className="evidence-references mt-2"><dt>Export ID</dt><dd>{item.id}</dd><dt>Snapshot</dt><dd>{item.snapshot_digest}</dd><dt>Original input SHA-256</dt><dd>{item.input_sha256}</dd>{artifacts.map(key => <div key={key}><dt>{key} artifact</dt><dd>{item.artifacts[key].bytes.toLocaleString()} bytes · SHA-256 {item.artifacts[key].sha256}</dd></div>)}</dl></details>
        <div className="mt-4 flex flex-wrap gap-2">{artifacts.map(key => <Button variant="outline" key={key} disabled={!!download} onClick={() => void save(item, key)}>{download === `${item.id}:${key}` ? "Preparing download…" : key === "reviewed" ? "Reviewed CSV" : key === "exceptions" ? "Exceptions CSV" : "Provenance JSON"}</Button>)}</div><p className="mt-2 text-xs text-muted-foreground">Published metadata; file existence and integrity are checked by the server on download.</p>
      </li>)}</ol><div className="mt-5 flex flex-wrap gap-3"><Button variant="outline" disabled={loading || page === 1} onClick={() => setPage(v => v - 1)}>Previous exports</Button><Button variant="outline" disabled={loading || page * 5 >= list.total} onClick={() => setPage(v => v + 1)}>Next exports</Button></div></>}
  </section>;
}
