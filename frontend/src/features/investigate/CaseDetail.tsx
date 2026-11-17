import { type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { type Evidence, type History, type LatestAI, type Review, base, currentProposal, fieldLabels, message, readable, request, validEvidence, investigateSearch } from "./contracts";
import { EvidenceView } from "./EvidenceView";
import { ReviewPanel } from "./ReviewPanel";
import { Dialog } from "../../components/ui/dialog";
import {type CaseDetailSelection} from "./CaseDetailWindow";
import { caseFindings } from "./CaseTable";

export function CaseDetail({ job, id, navigation, onDraftChange, navigationBlocked }: {job: number; id: string; navigation: ReactNode; onDraftChange: (dirty: boolean, locked: boolean) => void; navigationBlocked: boolean}) {
  const { search } = useLocation();
  const [detail, setDetail] = useState<CaseDetailSelection | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const draft = useRef({dirty: false, locked: false});
  const reportDraft = useCallback((dirty: boolean, locked: boolean) => { draft.current = {dirty, locked}; onDraftChange(dirty, locked); }, [onDraftChange]);
  const openDetail = (selection: CaseDetailSelection | null) => { if (!detail && selection) returnFocus.current = document.activeElement as HTMLElement; setDetail(selection); };
  const resumeAfterNavigation = useRef(false);
  useLayoutEffect(() => {
    if (navigationBlocked) { resumeAfterNavigation.current = detail?.kind === "review-form" || detail?.kind === "review-close"; setDetail(null); }
    else if (resumeAfterNavigation.current) { resumeAfterNavigation.current = false; setDetail({kind: "review-form"}); }
  }, [navigationBlocked]);
  const closeDetail = () => {
    if (detail?.kind === "review-form" && (draft.current.dirty || draft.current.locked)) setDetail({kind: "review-close"});
    else if (detail?.kind === "review-close") setDetail({kind: "review-form"});
    else setDetail(null);
  };
  const details = {detail: navigationBlocked ? null : detail, openDetail, returnFocus};
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [ai, setAI] = useState<LatestAI | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const title = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!evidence) return;
    title.current?.focus({preventScroll: true});
    if (window.matchMedia("(max-width: 1099px)").matches) title.current?.scrollIntoView({block: "start", behavior: "auto"});
  }, [!!evidence]);
  useEffect(() => {
    const controller = new AbortController(); const path = base(job, id);
    setLoading(true); setError(""); setErrors([]);
    void (async () => {
      try {
        const value = await request<Evidence>(path, controller.signal);
        if (controller.signal.aborted) return;
        if (!validEvidence(value, job, id)) throw new Error("The server returned inconsistent evidence. No review can be submitted.");
        setEvidence(value);
        const results = await Promise.allSettled([
          request<LatestAI>(`${path}/investigations`, controller.signal),
          request<Review>(`${path}/review`, controller.signal),
          request<History>(`${path}/review/history?page=1&page_size=5`, controller.signal),
        ]);
        if (controller.signal.aborted) return;
        const failures: string[] = [];
        const aiResult = results[0];
        if (aiResult.status === "fulfilled" && (aiResult.value.investigation === null || (aiResult.value.investigation.job_id === job && aiResult.value.investigation.discrepancy_id === id))) setAI(aiResult.value);
        else { setAI(null); failures.push(`AI retrieval: ${aiResult.status === "rejected" ? message(aiResult.reason) : "Unexpected scope."}`); }
        const reviewResult = results[1];
        if (reviewResult.status === "fulfilled" && reviewResult.value.job_id === job && reviewResult.value.discrepancy_id === id && Number.isInteger(reviewResult.value.revision) && reviewResult.value.evidence_digest === value.evidence_digest) setReview(reviewResult.value);
        else { setReview(null); failures.push(`Current review: ${reviewResult.status === "rejected" ? message(reviewResult.reason) : "Evidence changed; refresh before reviewing."}`); }
        const historyResult = results[2];
        if (historyResult.status === "fulfilled") setHistory(historyResult.value);
        else { setHistory(null); failures.push(`Decision history: ${message(historyResult.reason)}`); }
        setErrors(failures);
      } catch (reason) { if (!controller.signal.aborted) { setError(message(reason)); setReview(null); setAI(null); } }
      finally { if (!controller.signal.aborted) setLoading(false); }
    })();
    return () => controller.abort();
  }, [job, id, refresh]);
  return <Dialog open={!!detail && !navigationBlocked} onOpenChange={open => {if (!open) closeDetail();}}><div className="investigation-detail min-w-0" ref={title} tabIndex={-1} aria-label="Selected discrepancy">
    <div className="surface-section case-toolbar"><Button asChild variant="outline"><Link to={{pathname: "/investigate", search: investigateSearch(search, "table")}}>Back to cases</Link></Button>{navigation}</div>
    {loading && <p role="status" className="surface-section">Refreshing authoritative evidence and review…</p>}
    {error && <div className="surface-section" role="alert"><p className="notice-error">{error}</p><Button className="mt-3" variant="outline" onClick={() => setRefresh(v => v + 1)}>Retry selected evidence</Button></div>}
    {!evidence && !loading && !error && <p className="surface-section">No evidence was returned.</p>}
    {evidence && <><header className="surface-section case-header" data-case-id={evidence.discrepancy_id}><div><p className="text-sm text-muted-foreground">{fieldLabels[evidence.field]}</p><h2 className="mt-2 break-words text-3xl font-semibold">Flight {evidence.flight}</h2><p className="mt-3 text-sm">{caseFindings(evidence).join(" · ")}</p></div><Badge>{review ? review.stale ? "Previous review is stale" : readable(review.state) : "Review status unavailable"}</Badge></header><EvidenceView {...details} evidence={evidence} proposedCandidateId={currentProposal(ai, evidence)?.recommendation?.candidate_id} /><ReviewPanel {...details} evidence={evidence} ai={ai} review={review} history={history} errors={errors} ready={!loading && !error} refresh={() => setRefresh(v => v + 1)} setAI={setAI} setHistory={setHistory} onDraftChange={reportDraft} /></>}
  </div></Dialog>;
}
