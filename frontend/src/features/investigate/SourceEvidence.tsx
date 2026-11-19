import {useId, useState} from "react";
import {Button} from "../../components/ui/button";
import {Badge} from "../../components/ui/badge";
import {type Candidate, type Evidence} from "./contracts";

export function SourceEvidence({evidence: e, candidate}: {evidence: Evidence; candidate?: Candidate}) {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const prefix = useId();
  return <><p className="text-sm text-muted-foreground">Original decoded strings, including whitespace. ∅ denotes an empty string. Interpretation is separate from the raw claim.</p>
      {!e.claims.length && <p className="mt-3 text-sm">No source records were returned for this case.</p>}
      <p className="mt-3 text-xs text-muted-foreground">Showing records {e.claims.length ? (page - 1) * 10 + 1 : 0}–{Math.min(page * 10, e.claims.length)} of {e.claims.length}</p>
      <div tabIndex={0} role="region" aria-label="Source evidence table" className="source-evidence table-scroll mt-4"><table className="flight-table"><caption className="sr-only">Raw source claims and normalization for the selected field</caption><colgroup><col className="source-column" /><col className="claim-column" /><col className="interpretation-column" /><col className="limitations-column" /></colgroup><thead><tr>{["Source / observation", "Original claim", "Interpretation", "Candidate / limitations"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{e.claims.slice((page - 1) * 10, page * 10).map((c, index) => {
        const detailId = `${prefix}-record-${index}`;
        const open = expanded === c.tuple_id;
        return <tr key={c.tuple_id} data-expanded={open}>
          <td className="source-record-identity"><div><span className="raw-value font-medium">{c.src || "∅ (blank source)"}</span>{candidate && <p className="mt-1 text-xs font-medium">{candidate.supporting_observation_ids.includes(c.tuple_id) ? "Supports selected value" : candidate.contradicting_observation_ids.includes(c.tuple_id) ? "Conflicts with selected value" : candidate.context_observation_ids.includes(c.tuple_id) ? "Missing or uncertain context" : "Other / not established as comparable"}</p>}</div>
            <Button type="button" variant="outline" className="source-record-toggle" aria-label={`${open ? "Hide" : "Show"} details for source record ${c.tuple_id}`} aria-expanded={open} aria-controls={`${detailId}-identity ${detailId}-interpretation ${detailId}-limitations`} onClick={() => setExpanded(open ? null : c.tuple_id)}>{open ? "Close" : "Details"}</Button>
            <div id={`${detailId}-identity`} className="source-extra"><span className="mt-1 block raw-value">Observation: {c.tuple_id}</span><span className="mt-1 block text-xs">Record {c.row_number} · {c.source_usable ? "usable source ID" : "unusable source ID"}</span></div>
          </td>
          <td className="source-record-value"><span className="mobile-evidence-label">Original value</span><pre className="raw-value">{c.normalization.raw === "" ? "∅" : c.normalization.raw}</pre></td>
          <td className="source-record-interpretation"><Badge variant={c.normalization.status === "ambiguous" || c.normalization.status === "unsupported" ? "warning" : "default"}>{{parsed: "Usable time", missing: "Empty", placeholder: "Unavailable", ambiguous: "Uncertain interpretation", unsupported: "Could not interpret"}[c.normalization.status]}</Badge>
            <div id={`${detailId}-interpretation`} className="source-extra"><p className="mt-2 text-xs">Interpretation status: <span>{c.normalization.status}</span></p><p className="mt-2 text-xs">Interpreted time</p><p className="font-mono">{c.normalization.canonical_clock ?? "Not established"}</p>{c.normalization.precision && <p className="text-xs">{c.normalization.precision} precision</p>}</div>
          </td>
          <td id={`${detailId}-limitations`} className="source-extra source-record-limitations"><span className="mobile-evidence-label">Supported value and limitations</span><p>{e.candidates.filter(candidate => candidate.supporting_observation_ids.includes(c.tuple_id)).map(candidate => candidate.canonical_clock).join(" · ") || "No supported candidate"}</p><p className="mt-1 text-xs">{c.normalization.reason}</p><p className="mt-1 text-xs">{c.normalization.qualifiers.join(" · ")}</p>{c.identity_issues.map((issue, index) => <p key={index} className="mt-1 text-xs text-warning">{issue.code}: {issue.message}</p>)}</td>
        </tr>;
      })}</tbody></table></div>
      <div className="mt-4 flex flex-wrap items-center gap-3"><Button variant="outline" disabled={page === 1} onClick={() => { setExpanded(null); setPage(p => p - 1); }}>Previous source records</Button><span className="text-xs">Records {e.claims.length ? (page - 1) * 10 + 1 : 0}–{Math.min(page * 10, e.claims.length)} of {e.claims.length}</span><Button variant="outline" disabled={page * 10 >= e.claims.length} onClick={() => { setExpanded(null); setPage(p => p + 1); }}>Next source records</Button></div>
  </>;
}
