import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ApiError } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import {CaseDetailWindow, type CaseDetailActions} from "./CaseDetailWindow";
import { type Action, type Decision, type Evidence, type History, type Investigation, type LatestAI, type Review, type ReviewRequest, base, currentProposal, message, readable, request } from "./contracts";

export function ReviewPanel({ evidence, ai, review, history, errors, ready, refresh, setAI, setHistory, onDraftChange, detail, openDetail, returnFocus }: {
  evidence: Evidence; ai: LatestAI | null; review: Review | null; history: History | null; errors: string[]; ready: boolean;
  refresh: () => void; setAI: (ai: LatestAI) => void; setHistory: (history: History) => void; onDraftChange: (dirty: boolean, locked: boolean) => void;
} & CaseDetailActions) {
  const path = base(evidence.job_id, evidence.discrepancy_id);
  const controller = useRef(new AbortController());
  useEffect(() => { controller.current = new AbortController(); return () => controller.current.abort(); }, []);
  const [aiBusy, setAIBusy] = useState(false);
  const [aiError, setAIError] = useState("");
  const [aiPaused, setAIPaused] = useState(false);
  const aiRequest = useRef<{expected_evidence_digest: string; request_id: string} | null>(null);
  const [aiUncertain, setAIUncertain] = useState(false);
  const [action, setAction] = useState<Action>("unresolved");
  const [override, setOverride] = useState("candidate");
  const [candidate, setCandidate] = useState("");
  const [manual, setManual] = useState("");
  const [rationale, setRationale] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const [notice, setNotice] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef<ReviewRequest | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const proposal = currentProposal(ai, evidence);
  const aiResult = ai?.investigation;
  const eligible = evidence.candidates.length > 0 && (evidence.flags.confirmed_conflict || evidence.flags.has_ambiguous || evidence.flags.has_unsupported || evidence.flags.incomparable_supported_values);
  const freshReview = ready && review?.evidence_digest === evidence.evidence_digest;
  const locked = busy || uncertain;
  const signature = JSON.stringify([action, override, candidate, manual, rationale, reviewer]);
  const saved = useRef(signature);
  useLayoutEffect(() => { onDraftChange(signature !== saved.current, locked || aiBusy || aiUncertain); }, [signature, locked, aiBusy, aiUncertain, onDraftChange]);
  useLayoutEffect(() => () => onDraftChange(false, false), [onDraftChange]);
  const discardDraft = () => {
    const values = JSON.parse(saved.current) as [Action, string, string, string, string, string];
    setAction(values[0]); setOverride(values[1]); setCandidate(values[2]); setManual(values[3]); setRationale(values[4]); setReviewer(values[5]);
    setReviewError(""); setNotice(""); openDetail(null);
  };
  // Bounded GET-only polling never incurs another provider request.
  useEffect(() => {
    if (aiResult?.status !== "running") return;
    const abort = new AbortController(); let timer: ReturnType<typeof setTimeout>; let count = 0;
    setAIPaused(false);
    const poll = async () => {
      try {
        const result = await request<Investigation>(`${path}/investigations/${encodeURIComponent(aiResult.id)}`, abort.signal);
        if (abort.signal.aborted) return;
        if (result.job_id !== evidence.job_id || result.discrepancy_id !== evidence.discrepancy_id || result.id !== aiResult.id) throw new Error("Unexpected investigation scope. Refresh authoritative evidence.");
        setAI({status: result.status, investigation: result}); count++;
        if (result.status === "running") { if (count < 45) timer = setTimeout(poll, 2000); else setAIPaused(true); }
      } catch (error) { if (!abort.signal.aborted) { setAIError(message(error)); setAIPaused(true); } }
    };
    timer = setTimeout(poll, 2000);
    return () => { abort.abort(); clearTimeout(timer); };
  }, [aiResult?.id, aiResult?.status, path]);
  const investigate = async () => {
    if (aiBusy || aiResult?.status === "running") return;
    const body = aiRequest.current ?? {expected_evidence_digest: evidence.evidence_digest, request_id: crypto.randomUUID()};
    aiRequest.current = body; setAIBusy(true); setAIError("");
    try {
      const result = await request<Investigation>(`${path}/investigations`, controller.current.signal, body);
      if (controller.current.signal.aborted) return;
      if (result.job_id !== evidence.job_id || result.discrepancy_id !== evidence.discrepancy_id) throw new Error("Unexpected investigation response. Refresh before continuing.");
      setAI({status: result.status, investigation: result}); aiRequest.current = null; setAIUncertain(false);
    } catch (error) {
      if (controller.current.signal.aborted) return;
      const ambiguous = !(error instanceof ApiError) || error.status >= 500;
      setAIUncertain(ambiguous);
      setAIError(message(error) + (ambiguous ? " The outcome is uncertain. Retry uses the same request identifier." : ""));
      if (!ambiguous) aiRequest.current = null;
      if (error instanceof ApiError && error.status === 409) refresh();
    } finally { if (!controller.current.signal.aborted) setAIBusy(false); }
  };
  const submit = async () => {
    if (busy || !freshReview) return;
    let body = pending.current;
    if (!body) {
      if (!reviewer.trim() || ((action === "override" || action === "reject") && !rationale.trim())) { setReviewError("Enter a reviewer name or label and explain any value selection or rejection."); return; }
      if ((action === "accept" || action === "reject") && !proposal) { setReviewError("A current validated AI proposal is required for this action."); return; }
      if (action === "override" && (override === "candidate" ? !evidence.candidates.some(c => c.candidate_id === candidate) : !manual.trim())) { setReviewError("Select a current supported candidate or enter a manual clock."); return; }
      body = {action, expected_evidence_digest: evidence.evidence_digest, expected_revision: review!.revision, request_id: crypto.randomUUID(), reviewer_label: reviewer, rationale,
        ...(action === "accept" || action === "reject" ? {investigation_id: proposal!.id} : {}),
        ...(action === "override" ? override === "candidate" ? {candidate_id: candidate} : {manual_value: manual} : {})};
      pending.current = body;
    }
    setBusy(true); setReviewError(""); setNotice("");
    try {
      const result = await request<Decision>(`${path}/review`, controller.current.signal, body);
      if (controller.current.signal.aborted) return;
      if (result.job_id !== evidence.job_id || result.discrepancy_id !== evidence.discrepancy_id || result.request_id !== body.request_id) throw new Error("Unexpected decision receipt. Retrieve current server state before continuing.");
      saved.current = JSON.stringify([action, override, candidate, "", "", reviewer]);
      pending.current = null; setUncertain(false); setRationale(""); setManual("");
      setNotice("Review saved. Refreshing the current decision and history."); refresh();
    } catch (error) {
      if (controller.current.signal.aborted) return;
      const ambiguous = !(error instanceof ApiError) || error.status >= 500;
      setUncertain(ambiguous);
      setReviewError(message(error) + (ambiguous ? " The outcome is uncertain. Inputs are held for an exact same-ID retry." : ""));
      if (!ambiguous) pending.current = null;
      if (error instanceof ApiError && error.status === 409) {
        setReviewError(message(error) + " Refreshing evidence and decision revision. Your text is preserved; inspect the current state before explicitly submitting again."); refresh();
      }
    } finally { if (!controller.current.signal.aborted) setBusy(false); }
  };
  const loadHistory = async (page: number) => {
    setHistoryBusy(true); setHistoryError("");
    try { const value = await request<History>(`${path}/review/history?page=${page}&page_size=5`, controller.current.signal); if (!controller.current.signal.aborted) setHistory(value); }
    catch (error) { if (!controller.current.signal.aborted) setHistoryError(message(error)); }
    finally { if (!controller.current.signal.aborted) setHistoryBusy(false); }
  };
  return <>
    <section className="surface-section" aria-labelledby="ai-title"><div className="mt-2 flex flex-wrap items-center gap-3"><h3 id="ai-title" className="text-lg font-semibold">AI assistance</h3><Badge variant={ai?.status === "invalid_response" || ai?.status === "failed" ? "error" : ai?.status === "stale" || ai?.status === "unavailable" || ai?.status === "ineligible" ? "warning" : "default"}>{aiBusy ? "Request in progress" : ai ? readable(ai.status) : "Status unavailable"}</Badge></div>
      {errors.map(error => <p key={error} className="notice-error mt-3" role="alert">{error}</p>)}
      {proposal && <p className="mt-3 text-sm">Suggested value: <strong>{evidence.candidates.find(c => c.candidate_id === proposal.recommendation?.candidate_id)?.canonical_clock}</strong> · not approved</p>}
      {aiResult?.status === "abstained" && <p className="mt-3 text-sm">Not enough evidence to suggest a value. Your review is still available.</p>}
      {aiResult && (!aiResult.current || aiResult.evidence_digest !== evidence.evidence_digest) && <p className="mt-3 text-sm text-warning">This assessment uses historical or stale evidence.</p>}
      <p className="mt-3 text-sm text-muted-foreground">{ai?.status === "not_requested" ? "AI assessment not yet requested. " : ""}Optional assistance, not a decision. Requests may use a paid model service.</p>
      <Button variant="ghost" className="mt-2 px-0" aria-haspopup="dialog" onClick={() => openDetail({kind: "ai"})}>View AI assessment</Button>
      {detail?.kind === "ai" && <CaseDetailWindow title="AI assessment" evidence={evidence} wide={!!aiResult?.recommendation} returnFocus={returnFocus}>
        {!aiResult && <p className="text-sm">{ai?.status === "not_requested" ? "No AI assessment has been requested for this case." : "An assessment could not be retrieved. Refresh the server state before relying on it."}</p>}
      {aiResult && <div className="mt-4 space-y-3 text-sm">
        <p>{aiResult.status === "proposed" ? `Proposed candidate: ${evidence.candidates.find(c => c.candidate_id === aiResult.recommendation?.candidate_id)?.canonical_clock ?? "Historical / unavailable candidate"}` : aiResult.status === "abstained" ? "The model declined to select a candidate. Human review remains available." : `AI state: ${readable(aiResult.status)}. Deterministic evidence remains usable.`}</p>
        {(!aiResult.current || aiResult.evidence_digest !== evidence.evidence_digest) && <p className="text-warning">Historical or stale evidence. This recommendation cannot be accepted.</p>}
        {aiResult.error_code && <p className="text-warning">Reason: {readable(aiResult.error_code)}</p>}
        {aiResult.recommendation && <><p><strong>Model explanation:</strong> {aiResult.recommendation.explanation}</p><p><strong>Model uncertainty:</strong> {aiResult.recommendation.uncertainty}</p>
          <div><h4 className="font-semibold">Cited observations and provider</h4><div className="mt-3 space-y-2 evidence-references">
            {([['Supporting', aiResult.recommendation.supporting_claim_ids], ['Contradicting', aiResult.recommendation.contradicting_claim_ids]] as const).map(([label, ids]) => <div key={label}><strong>{label}:</strong>{ids.length ? <ul>{ids.map(id => { const ref = aiResult.claim_references.find(r => r.claim_id === id); return <li key={id}>{ref ? `Observation ${ref.observation_id} · Source ${ref.source_id}` : `Historical reference ${id}`}</li>; })}</ul> : " None cited"}</div>)}
            <p>Provider: {aiResult.provider ?? "Not reported"} · Model: {aiResult.resolved_model ?? aiResult.model ?? "Not reported"}</p><p>Reported usage: {Object.entries(aiResult.usage).map(([key, value]) => `${readable(key)} ${value}`).join(" · ") || "Not reported"}</p>
          </div></div></>}
      </div>}
      </CaseDetailWindow>}
      {!eligible && <p className="mt-3 text-sm">This evidence is not eligible for AI investigation: it has no supported candidate or no comparable disagreement/interpretation uncertainty. Human review is still available.</p>}
      {aiError && <p role="alert" className="notice-error mt-4">{aiError}</p>}{aiPaused && <p className="mt-3 text-sm">Automatic investigation checks stopped. Refresh status explicitly.</p>}
      <div className="mt-4 flex flex-wrap gap-3"><Button variant="outline" disabled={!ready || aiBusy || aiResult?.status === "running" || (!aiUncertain && !eligible)} onClick={() => void investigate()}>{aiBusy ? "Waiting for AI response…" : aiUncertain ? "Retry same AI request" : "Investigate with AI"}</Button><Button variant="ghost" disabled={aiBusy || busy || !ready} onClick={refresh}>Refresh server state</Button></div>
    </section>
    <section className="surface-section" aria-labelledby="review-title"><h3 id="review-title" className="mt-2 text-xl font-semibold">Your review</h3><p className="mt-2 text-sm text-muted-foreground">Choose a value only if the evidence supports your decision. Leaving this case unresolved is a valid outcome.</p>
      <div className="mt-3" aria-live="polite">{review ? <>
        {review.stale && <p className="text-sm text-warning">The earlier decision uses different evidence. Review the current reports before saving again.</p>}
        <p className="text-sm">{review.resolution && !review.stale ? `Reviewed value: ${review.resolution.canonical_clock} · ${review.resolution.origin === "human_assertion" ? "human-entered value" : "source-supported value"}` : "No current approved value"}</p>

      </> : <p>Current review unavailable. Writes are disabled until it can be retrieved.</p>}</div>
      <div className="mt-4 flex flex-wrap gap-3"><Button variant="outline" aria-haspopup="dialog" onClick={() => openDetail({kind: "review-form"})}>{signature !== saved.current ? "Resume review" : "Record a review"}</Button><Button variant="ghost" aria-haspopup="dialog" onClick={() => openDetail({kind: "review"})}>View review details</Button><Button variant="ghost" aria-haspopup="dialog" onClick={() => openDetail({kind: "history"})}>View review history{history ? ` (${history.total})` : ""}</Button></div>
      {detail?.kind === "review" && <CaseDetailWindow title="Review details" evidence={evidence} returnFocus={returnFocus}>{review ? <>        <p className="mt-2">Server revision {review.revision}</p>{review.decision && <p className="mt-2">Reviewer: {review.decision.reviewer_label} (unverified label) · {review.decision.created_at}<br />{review.decision.rationale}</p>}</> : <p>Current review unavailable.</p>}</CaseDetailWindow>}
      {detail?.kind === "review-form" && <CaseDetailWindow title="Record your review" evidence={evidence} fullScreenMobile returnFocus={returnFocus}>
        <p className="text-sm">Current review: {review ? review.stale ? "earlier decision is stale" : readable(review.state) : "unavailable"}. Current reviewed value: {review?.resolution && !review.stale ? review.resolution.canonical_clock : "none"}.</p>
        <p className="mt-3 text-sm font-medium">Reported values</p><ul className="review-value-reference mt-2">{evidence.candidates.map(c => <li key={c.candidate_id}><strong className="font-mono">{c.canonical_clock}</strong> · {c.distinct_source_support_count} sources{c.qualifiers.length ? ` · ${c.qualifiers.join(", ")}` : ""}</li>)}</ul>
        {!evidence.candidates.length && <p className="text-sm">No supported clock values were found.</p>}
        <p className="mt-3 text-sm text-muted-foreground">Source support does not verify a historical time. Leave unresolved when the evidence is insufficient.</p>
        <form id="case-review-form" className="review-form mt-5" onSubmit={event => { event.preventDefault(); void submit(); }}>
        <fieldset disabled={locked || !freshReview} className="min-w-0 space-y-4"><legend className="sr-only">Human review decision</legend>
          <label className="block text-sm font-medium">Review action<select className="field mt-2" value={action} onChange={event => setAction(event.target.value as Action)}>
            <option value="unresolved">Leave unresolved</option><option value="override">Choose a value</option>{proposal && <><option value="accept">Accept current AI proposal</option><option value="reject">Reject current AI proposal</option></>}</select></label>
          {action === "unresolved" && <p className="text-sm text-muted-foreground">Save this case as unresolved without approving a value.</p>}
          {action === "override" && <p className="text-sm text-muted-foreground">Choose a reported value or enter a clock supported by information you trust. Explain your choice.</p>}
          {(action === "accept" || action === "reject") && <p className="text-sm">{proposal ? `${action === "accept" ? "Accept" : "Reject"} AI candidate ${evidence.candidates.find(c => c.candidate_id === proposal.recommendation?.candidate_id)?.canonical_clock}. ${action === "reject" ? "Rejection leaves no approved value." : "Submission explicitly approves this observed candidate."}` : "The selected action requires a current validated AI proposal."}</p>}
          {action === "override" && <><label className="block text-sm font-medium">Replacement origin<select className="field mt-2" value={override} onChange={event => setOverride(event.target.value)}><option value="candidate">Observed supported candidate</option><option value="manual">Human-entered clock</option></select></label>
            {override === "candidate" ? <label className="block text-sm font-medium">Supported candidate<select className="field mt-2" value={candidate} onChange={event => setCandidate(event.target.value)}><option value="">Select a candidate</option>{evidence.candidates.map(c => <option key={c.candidate_id} value={c.candidate_id}>{c.canonical_clock} · {c.precision} · {c.distinct_source_support_count} sources</option>)}</select></label> : <label className="block text-sm font-medium">Manual clock<input aria-label="Manual clock" className="field mt-2" value={manual} maxLength={160} onChange={event => setManual(event.target.value)} aria-describedby="manual-guidance" /><span id="manual-guidance" className="mt-2 block text-xs font-normal text-muted-foreground">A human assertion, not a source claim. Use an explicit clock (for example 2:40 p.m. or 14:40). The server validates normalization v1; ambiguous values are rejected.</span></label>}</>}
          <label className="block text-sm font-medium">Reviewer name or label<input aria-label="Reviewer name or label" aria-describedby="reviewer-guidance" className="field mt-2" required maxLength={80} value={reviewer} onChange={event => setReviewer(event.target.value)} /><span className="mt-2 block text-xs font-normal text-muted-foreground" id="reviewer-guidance">Local attribution, not a verified identity.</span></label>
          <label className="block text-sm font-medium">Rationale{action === "override" || action === "reject" ? " (required)" : " (optional)"}<textarea className="field mt-2 min-h-24" maxLength={1000} required={action === "override" || action === "reject"} value={rationale} onChange={event => setRationale(event.target.value)} /></label>
        </fieldset>
        {reviewError && <p role="alert" className="notice-error mt-4">{reviewError}</p>}{notice && <p role="status" className="mt-4 text-sm text-success">{notice}</p>}
        <Button className="mt-5" variant="accent" type="submit" disabled={busy || !freshReview || (!uncertain && (action === "accept" || action === "reject") && !proposal)}>{busy ? "Submitting decision…" : uncertain ? "Retry exact review request" : "Save review"}</Button>
        {uncertain && <p className="mt-3 text-xs">Do not submit a different decision until this request is reconciled. Refreshing reads does not resubmit it.</p>}
      </form></CaseDetailWindow>}
      <p className="mt-4 text-xs text-muted-foreground">Decisions preserve the original observations and earlier review history.</p>
    </section>
    {detail?.kind === "review-close" && <CaseDetailWindow title={locked || aiBusy || aiUncertain ? "A request still needs confirmation" : "Leave your unfinished review?"} evidence={evidence} returnFocus={returnFocus}>
      <p className="text-sm">{locked || aiBusy || aiUncertain ? "Return to the form and confirm the request outcome with the existing exact retry before leaving." : "Continue editing, keep the draft while inspecting evidence, or explicitly discard your changes. Nothing is saved by closing this dialog."}</p>
      <div className="mt-5 flex flex-wrap gap-3"><Button autoFocus variant="outline" onClick={() => openDetail({kind: "review-form"})}>Continue editing</Button>
        {!(locked || aiBusy || aiUncertain) && <><Button variant="outline" onClick={() => openDetail(null)}>Keep draft and view case</Button><Button onClick={discardDraft}>Discard draft</Button></>}
      </div>
    </CaseDetailWindow>}
    {detail?.kind === "history" && <CaseDetailWindow title="Review history" evidence={evidence} wide={!!history?.total} returnFocus={returnFocus}>
      {!history && <p role="status" className="text-sm">Review history is unavailable. Close this view and refresh the server state to retry.</p>}
      {historyError && <p role="alert" className="notice-error mt-3">{historyError}</p>}
      {history && <><ol className="mt-4 space-y-4">{history.events.map(event => <li key={event.id} className="text-sm"><strong>Revision {event.revision} · {readable(event.action)}</strong><p>{event.resolution?.canonical_clock ?? "No approved value"} · {event.reviewer_label} (local label)</p><p className="text-xs">{event.created_at}</p><p className="mt-1 raw-value">{event.rationale}</p>{event.manual_value !== null && <p className="mt-1 raw-value">Original manual entry: {event.manual_value}</p>}<div className="mt-2 text-xs"><h4 className="font-semibold">Decision provenance</h4><dl className="evidence-references mt-2"><dt>Event</dt><dd>{event.id}</dd><dt>Evidence</dt><dd>{event.evidence_digest}</dd><dt>Candidate</dt><dd>{event.candidate_id ?? "None"}</dd><dt>Investigation</dt><dd>{event.investigation_id ?? "None"}</dd><dt>Supporting observations</dt><dd>{event.resolution?.supporting_observation_ids.join(" · ") || "None"}</dd></dl></div></li>)}</ol>
      {!history.total && <p className="mt-3 text-sm">No human decisions recorded.</p>}{history.total > 0 && <div className="mt-4 flex flex-wrap items-center gap-3"><Button variant="outline" disabled={historyBusy || history.page === 1} onClick={() => void loadHistory(history.page - 1)}>Earlier history page</Button><span className="text-xs">Page {history.page} · 5 events per page</span><Button variant="outline" disabled={historyBusy || history.page * history.page_size >= history.total} onClick={() => void loadHistory(history.page + 1)}>Next history page</Button></div>}</>}
    </CaseDetailWindow>}
  </>;
}
