import { Link } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { type Kind, type QueuePage, type Summary, fieldLabels, fields, investigateSearch } from "./contracts";

export function caseFindings(item: Pick<Summary, "flags" | "requires_attention">): string[] {
  const flags = item.flags;
  const findings: string[] = [];
  if (flags.confirmed_conflict) findings.push("Sources disagree");
  if (flags.has_missing || flags.has_placeholders) findings.push("Missing or unavailable information");
  if (flags.has_ambiguous || flags.has_unsupported || flags.incomparable_supported_values || flags.unusable_source_identity || flags.internal_source_conflict || flags.insufficient_support) findings.push("Uncertain evidence");
  if (!findings.length) findings.push(item.requires_attention ? "Needs closer inspection" : "No detected issue");
  return findings;
}

export function CaseTable({job, filename, search, data, loading, error, kind, field, page, update, retry}: {
  job: number; filename: string; search: string; data: QueuePage | null; loading: boolean; error: string;
  kind: Kind; field: string; page: number; update: (values: Record<string, string | null>) => void; retry: () => void;
}) {
  return <section className="working-surface cases-panel" aria-labelledby="cases-title" aria-busy={loading}>
    <div className="surface-section cases-heading"><div><h2 id="cases-title" className="text-2xl font-semibold">Cases</h2><p className="mt-2 break-words text-sm text-muted-foreground">{filename} · Import #{job}</p></div><p className="text-sm text-muted-foreground">Each case checks one time field for a flight.</p></div>
    <div className="cases-filters surface-section">
      <label className="text-sm font-medium">Finding<select className="field mt-2" value={kind} onChange={event => update({kind: event.target.value, page: null})}>
        <option value="attention">Flagged cases</option><option value="conflict">Sources disagree</option><option value="missing">Missing or unavailable information</option><option value="uncertain">Uncertain evidence</option><option value="all">All cases</option>
      </select></label>
      <label className="text-sm font-medium">Time field<select className="field mt-2" value={field} onChange={event => update({field: event.target.value || null, page: null})}><option value="">All time fields</option>{fields.map(value => <option key={value} value={value}>{fieldLabels[value]}</option>)}</select></label>
    </div>
    {loading && <p role="status" className="surface-section text-sm">Loading cases…</p>}
    {error && <div role="alert" className="surface-section"><p className="notice-error">{error}</p><Button className="mt-3" variant="outline" onClick={retry}>Retry cases</Button></div>}
    {!loading && !error && data && <>
      {data.ungroupable_observation_count > 0 && <p className="px-6 pb-4 text-sm text-warning">{data.ungroupable_observation_count.toLocaleString()} source records could not be grouped. They remain available in All source records.</p>}
      {!data.discrepancies.length ? <p className="surface-section text-sm">{page > 1 ? "No cases on this page. Return to an earlier page." : "No cases match these filters. Try All cases; no detected issue does not establish correctness."}</p> :
        <div className="cases-table-container"><table className="cases-table" role="table" aria-label="Cases"><caption className="sr-only">Flight time-field cases for import {job}. Findings do not represent human review decisions.</caption>
          <thead role="rowgroup"><tr role="row">{["Flight", "Information", "Finding", "Reports", "Open"].map(label => <th key={label} role="columnheader" scope="col">{label}</th>)}</tr></thead>
          <tbody role="rowgroup">{data.discrepancies.map(item => <tr role="row" key={item.discrepancy_id}>
            <td role="cell" className="case-flight">{item.flight}</td><td role="cell" className="case-field">{fieldLabels[item.field]}</td>
            <td role="cell" className="case-finding">{caseFindings(item).map((finding, index) => <span key={finding} className={index ? "mt-1 block text-xs text-muted-foreground" : "block"}>{finding}</span>)}</td>
            <td role="cell" className="case-reports"><span className="block">{item.observation_count.toLocaleString()} reports</span><span className="mt-1 block text-xs text-muted-foreground">{item.candidate_count ? `${item.candidate_count} possible ${item.candidate_count === 1 ? "time" : "times"}` : "No supported times"}</span></td>
            <td role="cell" className="case-open"><Link aria-label={`Open case for ${item.flight}, ${fieldLabels[item.field]}`} to={{pathname: "/investigate", search: investigateSearch(search, "case", {discrepancy: item.discrepancy_id})}}>Open case</Link></td>
          </tr>)}</tbody>
        </table></div>}
      <div className="cases-pagination surface-section"><p className="text-sm">Page {page} · {data.total.toLocaleString()} matching cases</p><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={page === 1} onClick={() => update({page: String(page - 1)})}>Previous cases</Button><Button variant="outline" disabled={page * 15 >= data.total} onClick={() => update({page: String(page + 1)})}>Next cases</Button></div></div>
      <p className="px-6 pb-6 text-xs text-muted-foreground">Review status is available inside each case. No detected issue does not mean a value is verified.</p>
    </>}
  </section>;
}
