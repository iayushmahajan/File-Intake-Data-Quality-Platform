import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { type Evidence, readable } from "./contracts";
import {CaseDetailWindow, type CaseDetailActions} from "./CaseDetailWindow";
import {SourceEvidence} from "./SourceEvidence";
export function EvidenceView({ evidence: e, proposedCandidateId, detail, openDetail, returnFocus }: { evidence: Evidence; proposedCandidateId?: string | null } & CaseDetailActions) {
  const selected = detail?.kind === "candidate" ? e.candidates.find(c => c.candidate_id === detail.candidateId) : null;
  return <>
    <section className="surface-section"><h3 className="text-lg font-semibold">What did we find?</h3>
      <p className="mt-2 text-sm">{e.flags.confirmed_conflict ? `${e.candidates.length} supported times were reported. Some source reports contradict one another; the evidence does not establish which time is correct.` : e.candidates.length ? "The supported reports do not establish a confirmed time conflict. Missing information or uncertain interpretations may still need your attention." : "No supported clock value could be established from these reports. The original values remain available below."}</p>
      <p className="mt-2 text-sm text-muted-foreground">{e.observation_count} source records · {e.usable_source_count} reporting sources</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {e.flags.formatting_variation && <Badge>Equivalent formatting</Badge>}{e.flags.has_missing && <Badge>{e.counts.missing} empty reports</Badge>}{e.flags.has_placeholders && <Badge>{e.counts.placeholder} unavailable reports</Badge>}
        {e.flags.has_ambiguous && <Badge variant="warning">{e.counts.ambiguous} ambiguous reports</Badge>}{e.flags.has_unsupported && <Badge variant="warning">{e.counts.unsupported} unsupported reports</Badge>}
        {e.flags.incomparable_supported_values && <Badge variant="warning">Not all times are comparable</Badge>}{e.flags.unusable_source_identity && <Badge variant="warning">Source identity issues</Badge>}{e.flags.insufficient_support && <Badge variant="warning">Limited usable support</Badge>}
      </div>
      {e.internally_inconsistent_source_ids.length > 0 && <p className="mt-3 text-sm text-warning">Some sources contradict their own reports: <span className="raw-value">{e.internally_inconsistent_source_ids.join(" · ")}</span></p>}
    </section>
    <div className="surface-section"><h3 className="text-lg font-semibold">Compare reported values</h3><p className="mt-2 text-sm text-muted-foreground">Possible values from observed claims. Support counts do not establish correctness.</p>
      {!e.candidates.length && <p className="mt-4">No supported clock candidate. Unsupported text is retained below.</p>}
      <div className="reported-values mt-4">{e.candidates.map((c, i) => <section className="reported-value" key={c.candidate_id} aria-label={`Candidate ${c.canonical_clock}`}>
        <p className="sr-only">Possible value {i + 1}</p>{proposedCandidateId === c.candidate_id && <Badge className="mt-2">AI proposal · unapproved</Badge>}<h4 className="mt-2 font-mono text-2xl font-semibold tabular-nums">{c.canonical_clock}</h4>{c.qualifiers.length > 0 && <p className="mt-1 text-xs text-warning">{c.qualifiers.join(", ")}</p>}
        <p className="mt-3 text-sm">Reported by <strong>{c.distinct_source_support_count}</strong> {c.distinct_source_support_count === 1 ? "source" : "sources"}{c.observation_support_count !== c.distinct_source_support_count && <span className="block text-xs mt-1">{c.observation_support_count} reports in total</span>}</p>
        <Button variant="ghost" className="mt-3 px-0" aria-haspopup="dialog" onClick={() => openDetail({kind: "candidate", candidateId: c.candidate_id})}>View supporting reports<span className="sr-only"> for {c.canonical_clock}</span></Button>
      </section>)}</div>
    </div>
    <div className="surface-section case-detail-actions"><Button variant="outline" aria-haspopup="dialog" onClick={() => openDetail({kind: "sources"})}>View source records <span className="text-xs">({e.claims.length})</span></Button><Button variant="ghost" aria-haspopup="dialog" onClick={() => openDetail({kind: "evidence"})}>View evidence details</Button><Button variant="ghost" aria-haspopup="dialog" onClick={() => openDetail({kind: "baseline"})}>View initial assessment</Button></div>
    {detail?.kind === "sources" && <CaseDetailWindow title="Source records" evidence={e} wide resizable returnFocus={returnFocus}><SourceEvidence evidence={e} /></CaseDetailWindow>}
    {detail?.kind === "candidate" && <CaseDetailWindow title={selected ? `Reports for ${selected.canonical_clock}` : "Reported value unavailable"} evidence={e} wide resizable returnFocus={returnFocus}>
      {selected ? <><p className="text-sm mb-5">{selected.observation_support_count} supporting reports from {selected.distinct_source_support_count} sources. Source support does not prove correctness; relationships below come from the current evidence.</p><SourceEvidence evidence={e} candidate={selected} />{[selected].map(c => <div key={c.candidate_id}><dl className="evidence-references mt-3"><dt>Support counts</dt><dd>{c.observation_support_count} source observations · {c.distinct_source_support_count} distinct reporting sources</dd><dt>Time detail</dt><dd>{c.precision} precision</dd><dt>Qualifiers</dt><dd>{c.qualifiers.join(" · ") || "None"}</dd><dt>Policies</dt><dd>{c.normalization_policy} · {c.detection_policy}</dd>
          <dt>Original spellings</dt><dd>{c.raw_values.map(raw => <pre key={raw} className="raw-value">{raw}</pre>)}</dd>
          <dt>Supporting observations</dt><dd>{c.supporting_observation_ids.join(" · ") || "None"}</dd><dt>Supporting sources</dt><dd>{c.supporting_source_ids.join(" · ") || "None"}</dd>
          <dt>Contradicting observations</dt><dd>{c.contradicting_observation_ids.join(" · ") || "None established"}</dd>
          <dt>Contradicting candidates</dt><dd>{c.contradicting_candidate_ids.map(id => e.candidates.find(candidate => candidate.candidate_id === id)?.canonical_clock ?? id).join(" · ") || "None established"}</dd>
          <dt>Incomparable candidates</dt><dd>{c.incomparable_candidate_ids.map(id => e.candidates.find(candidate => candidate.candidate_id === id)?.canonical_clock ?? id).join(" · ") || "None"}</dd>
          <dt>Uncertain / missing context observations</dt><dd>{c.context_observation_ids.join(" · ") || "None"}</dd><dt>Candidate ID</dt><dd>{c.candidate_id}</dd>
        </dl></div>)}</> : <p role="alert">This value is no longer part of the current evidence. Refresh the case.</p>}
    </CaseDetailWindow>}
    {detail?.kind === "evidence" && <CaseDetailWindow title="Evidence details" evidence={e} returnFocus={returnFocus}><dl className="evidence-references text-sm"><dt>Findings</dt><dd>{e.summary}</dd><dt>Evidence digest</dt><dd>{e.evidence_digest}</dd><dt>Case identity</dt><dd>{e.discrepancy_id}</dd><dt>Policies</dt><dd>{e.normalization_policy} · {e.detection_policy}</dd></dl></CaseDetailWindow>}
    {detail?.kind === "baseline" && <CaseDetailWindow title="Initial assessment" evidence={e} returnFocus={returnFocus}><p className="text-sm">{e.baseline.status === "proposal" ? `Candidate proposal: ${e.candidates.find(c => c.candidate_id === e.baseline.candidate_id)?.canonical_clock ?? "Unavailable candidate"}.` : `Abstained: ${e.baseline.abstention_reasons.map(readable).join(", ")}.`}</p><p className="mt-3 text-sm text-muted-foreground">A source-support baseline, not an approved value. {e.baseline.policy_version}.</p></CaseDetailWindow>}
  </>;
}
