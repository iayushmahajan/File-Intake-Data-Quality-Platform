import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useBlocker, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { type FlightsJob, validJobId } from "../datasets/flights";
import { type Kind, type QueuePage, base, fields, message, request, investigateView, investigateSearch } from "./contracts";
import { CaseDetail } from "./CaseDetail";
import { CaseNavigation, casePagePath, loadCasePage } from "./CaseNavigation";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../components/ui/dialog";
import { DatasetOverview } from "./DatasetOverview";
import { CaseTable } from "./CaseTable";


function DatasetWorkspace({ job, search, onDraftChange, navigationBlocked }: {job: number; search: string; onDraftChange: (dirty: boolean, locked: boolean) => void; navigationBlocked: boolean}) {
  const navigate = useNavigate();
  const params = new URLSearchParams(search);
  const selected = params.get("discrepancy");
  const overview = investigateView(search) === "overview";
  const rawKind = params.get("kind") ?? "attention";
  const kind: Kind = ["attention", "conflict", "uncertain", "missing", "all"].includes(rawKind) ? rawKind as Kind : "attention";
  const field = fields.includes(params.get("field") as typeof fields[number]) ? params.get("field")! : "";
  const rawPage = params.get("page") ?? "1";
  const page = /^\d+$/.test(rawPage) && Number.isSafeInteger(Number(rawPage)) && Number(rawPage) >= 1 && Number(rawPage) <= 2147483647 ? Number(rawPage) : 1;
  const [status, setStatus] = useState<FlightsJob | null>(null);
  const [jobError, setJobError] = useState("");
  const [jobRefresh, setJobRefresh] = useState(0);
  const [queue, setQueue] = useState<QueuePage | null>(null);
  const [queueError, setQueueError] = useState("");
  const [queueLoading, setQueueLoading] = useState(false);
  const [queueRefresh, setQueueRefresh] = useState(0);
  const prefetched = useRef<{path: string; data: QueuePage} | null>(null);
  const update = (values: Record<string, string | null>) => {
    const next = new URLSearchParams(search); next.delete("job");
    Object.entries(values).forEach(([key, value]) => value === null ? next.delete(key) : next.set(key, value));
    next.set("view", next.get("discrepancy") ? "case" : "table");
    navigate({pathname: "/investigate", search: `?${next}`});
  };
  useEffect(() => {
    const controller = new AbortController(); setStatus(null); setJobError("");
    request<FlightsJob>(base(job), controller.signal).then(value => {
      if (controller.signal.aborted) return;
      if (value.id !== job || value.job_kind !== "raha_flights_v1" || value.contract_version !== 1 || !["pending", "queued", "processing", "completed", "failed"].includes(value.status)) throw new Error("This is not a supported Flights job response.");
      setStatus(value);
    }).catch(error => { if (!controller.signal.aborted) setJobError(message(error)); });
    return () => controller.abort();
  }, [job, jobRefresh]);
  useEffect(() => {
    if (status?.status !== "completed" || overview) return;
    const controller = new AbortController(); setQueueLoading(true); setQueueError(""); setQueue(null);
    const path = casePagePath(job, kind, field, page);
    const cached = prefetched.current?.path === path ? prefetched.current.data : null;
    prefetched.current = null;
    (cached ? Promise.resolve(cached) : loadCasePage(job, kind, field, page, controller.signal)).then(value => {
      if (controller.signal.aborted) return;
      setQueue(value);
    }).catch(error => { if (!controller.signal.aborted) setQueueError(message(error)); }).finally(() => { if (!controller.signal.aborted) setQueueLoading(false); });
    return () => controller.abort();
  }, [job, status?.status, kind, field, page, queueRefresh, overview]);
  if (jobError) return <div className="working-surface mt-8 surface-section" role="alert"><p className="notice-error">{jobError}</p><Button variant="outline" className="mt-4" onClick={() => setJobRefresh(v => v + 1)}>Retry dataset status</Button></div>;
  if (!status) return <p role="status" className="working-surface mt-8 surface-section">Loading authoritative Flights job status…</p>;
  if (status.status !== "completed") return <div className="working-surface mt-8 surface-section"><Badge variant={status.status === "failed" ? "error" : "default"}>{status.status}</Badge><h2 className="mt-4 text-xl font-semibold">{status.status === "failed" ? "This import failed." : "The dataset is not ready for investigation."}</h2><p className="mt-3 text-sm">{status.error_message ?? "Only completed Flights observations can be investigated. No discrepancy queue has been inferred."}</p><p className="mt-3 break-words text-sm">{status.filename_original}</p><div className="mt-4 flex flex-wrap items-center gap-4"><Button variant="outline" onClick={() => setJobRefresh(v => v + 1)}>Check dataset status</Button><Link className="text-sm underline" to={`/datasets?dataset=${job}`}>View dataset</Link></div></div>;
  const navigation = <nav aria-label="Dataset views" className="dataset-view-navigation">
    <Link to={{pathname: "/investigate", search: investigateSearch(search, "overview")}} aria-current={overview ? "page" : undefined}>Overview</Link>
    <Link to={{pathname: "/investigate", search: investigateSearch(search, "table")}} aria-current={!overview ? "page" : undefined}>Cases</Link>
    <Link to={`/datasets?dataset=${job}&view=records`} state={{investigateReturn: search}}>All source records</Link>
  </nav>;
  if (overview) return <>{navigation}<DatasetOverview job={status} search={search} /></>;
  if (!selected) return <>{navigation}<CaseTable job={job} filename={status.filename_original} search={search} data={queue} loading={queueLoading || (!queue && !queueError)} error={queueError} kind={kind} field={field} page={page} update={update} retry={() => setQueueRefresh(v => v + 1)} /></>;
  return <>{navigation}<div className="working-surface focused-case mt-6">
    {selected.length <= 80 ? <CaseDetail key={`${job}:${selected}`} job={job} id={selected} onDraftChange={onDraftChange} navigationBlocked={navigationBlocked}
      navigation={<CaseNavigation job={job} id={selected} data={queue} loading={queueLoading} error={queueError} kind={kind} field={field} page={page} search={search}
        remember={data => { prefetched.current = {path: casePagePath(job, kind, field, data.page), data}; }} retry={() => setQueueRefresh(v => v + 1)} />} /> : <p role="alert" className="surface-section">Invalid case identifier. Return to Cases to select a field.</p>}
  </div></>;

}

export function InvestigatePage() {
  const location = useLocation(); const navigate = useNavigate();
  const draft = useRef({dirty: false, locked: false});
  const [locked, setLocked] = useState(false);
  const onDraftChange = useCallback((dirty: boolean, locked: boolean) => { draft.current = {dirty, locked}; setLocked(locked); }, []);
  const blocker = useBlocker(({currentLocation, nextLocation}) => (draft.current.dirty || draft.current.locked) &&
    (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search || currentLocation.hash !== nextLocation.hash));
  const returnFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (draft.current.dirty || draft.current.locked) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, []);
  const query = new URLSearchParams(location.search); const id = validJobId(query.get("dataset"));
  const [input, setInput] = useState(""); const [error, setError] = useState("");
  const view = investigateView(location.search);
  const overview = !!id && view === "overview";
  const previousView = useRef(`${id}:${overview}`);
  useEffect(() => {
    const next = `${id}:${overview}`;
    if (previousView.current !== next) window.scrollTo?.({top: 0, behavior: "auto"});
    previousView.current = next;
  }, [id, overview]);
  return <><section className={`workspace-container investigate-page ${overview ? "overview-container" : view === "table" ? "cases-container" : "focused-container"}`}><div className={view === "case" ? "sr-only" : "page-introduction"}><h1 className="workspace-title">Investigate</h1><p className="mt-3 max-w-2xl text-muted-foreground">Compare source values and review disagreements.</p></div>
    {!id ? <div className="working-surface mt-8 surface-section"><h2 className="text-2xl font-semibold">Open a Flights dataset.</h2><p className="mt-3 text-sm">Enter an existing Flights import number, or <Link className="underline" to="/datasets">import source observations</Link>.</p>{query.has("dataset") && <p role="alert" className="notice-error mt-4">The dataset identifier is invalid. Enter a positive Flights import number.</p>}
      <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={event => {event.preventDefault(); const number = validJobId(input); if (!number) {setError("Enter a valid positive Flights import number."); return;} navigate(`/investigate?dataset=${number}`);}}><label className="block min-w-0 text-sm font-medium">Flights import number<input className="field mt-2" inputMode="numeric" value={input} onChange={event => {setInput(event.target.value);setError("");}} /></label><Button type="submit" variant="accent">Open investigation workspace</Button></form>{error && <p role="alert" className="notice-error mt-3">{error}</p>}
    </div> : <DatasetWorkspace key={id} job={id} search={location.search} onDraftChange={onDraftChange} navigationBlocked={blocker.state !== "unblocked"} />}
  </section><Dialog open={blocker.state === "blocked"} onOpenChange={open => { if (!open && blocker.state === "blocked") blocker.reset(); }}>
    <DialogContent onOpenAutoFocus={() => { returnFocus.current = document.activeElement as HTMLElement; }} onPointerDownOutside={event => event.preventDefault()}
      onCloseAutoFocus={event => { event.preventDefault(); if (blocker.state !== "proceeding") queueMicrotask(() => { if (document.querySelector('[role="dialog"][data-state="open"]')) return; const previous = returnFocus.current; if (previous?.isConnected && previous.getClientRects().length) previous.focus({preventScroll: true}); else document.getElementById("main-content")?.focus({preventScroll: true}); }); }}>
      <DialogTitle className="text-lg font-semibold">{locked ? "A request still needs confirmation" : "Leave your unfinished review?"}</DialogTitle>
      <DialogDescription className="mt-3 text-sm text-muted-foreground">{locked ? "Wait for the request or reconcile its outcome with the exact retry before leaving. This prevents losing its request identifier." : "Your unsaved review will be discarded. No decision has been submitted by navigating."}</DialogDescription>
      <div className="mt-6 flex flex-wrap justify-end gap-3"><Button autoFocus variant="outline" onClick={() => blocker.state === "blocked" && blocker.reset()}>Continue editing</Button>
        {!locked && <Button onClick={() => { if (blocker.state === "blocked") { draft.current = {dirty: false, locked: false}; blocker.proceed(); } }}>Discard changes and leave</Button>}</div>
    </DialogContent>
  </Dialog></>;
}
