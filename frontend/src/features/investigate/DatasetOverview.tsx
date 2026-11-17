import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { type FlightsJob } from "../datasets/flights";
import { type Kind, type QueuePage, base, fields, investigateSearch, message, request } from "./contracts";

const kinds = ["all", "attention", "conflict", "missing", "uncertain"] as const;
type CountKind = typeof kinds[number];
interface Count { total?: number; ungroupable?: number; error?: string }
type Counts = Partial<Record<CountKind, Count>>;

function validateCount(value: QueuePage, job: number): Count {
  if (value?.job_id !== job || value.page !== 1 || value.page_size !== 1 ||
      !Number.isSafeInteger(value.total) || value.total < 0 || !Array.isArray(value.discrepancies) ||
      value.discrepancies.length !== Math.min(1, value.total) ||
      !Number.isSafeInteger(value.ungroupable_observation_count) || value.ungroupable_observation_count < 0) {
    throw new Error("The case summary is inconsistent. Refresh before using this count.");
  }
  return {total: value.total, ungroupable: value.ungroupable_observation_count};
}

export function DatasetOverview({job, search}: {job: FlightsJob; search: string}) {
  const [counts, setCounts] = useState<Counts>({});
  const [retry, setRetry] = useState<CountKind | null>(null);
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const pending = retry ? [retry] : [...kinds];
    if (!retry) setCounts({});
    else setCounts(previous => ({...previous, [retry]: undefined}));
    // Two workers bound concurrency; each total is fetched once, never polled.
    async function load() {
      while (pending.length && !controller.signal.aborted) {
        const kind = pending.shift()!;
        try {
          const value = await request<QueuePage>(`${base(job.id)}/discrepancies?kind=${kind}&page=1&page_size=1`, controller.signal);
          const count = validateCount(value, job.id);
          if (!controller.signal.aborted) setCounts(previous => ({...previous, [kind]: count}));
        } catch (error) {
          if (!controller.signal.aborted) setCounts(previous => ({...previous, [kind]: {error: message(error)}}));
        }
      }
    }
    void Promise.all([load(), load()]);
    return () => controller.abort();
  }, [job.id, retry, generation]);
  const retryCount = (kind: CountKind) => {setRetry(kind); setGeneration(value => value + 1);};
  const display = (kind: CountKind) => {
    const count = counts[kind];
    return count?.error ? "Unavailable" : count?.total === undefined ? "…" : count.total.toLocaleString();
  };
  const all = counts.all;
  // v1 produces exactly one case for each of the four fields in every flight group.
  const flights = job.job_kind === "raha_flights_v1" && job.contract_version === 1 &&
    all?.total !== undefined && all.total % fields.length === 0 ? all.total / fields.length : null;
  const records = Number.isSafeInteger(job.observation_count) && job.observation_count >= 0 ? job.observation_count : null;
  const reviewing = investigateSearch(search, "table", {kind: counts.attention?.total === 0 ? "all" : "attention", field: null, page: "1"});
  const issueRows: [CountKind, string, Kind][] = [
    ["conflict", "Different reported times", "conflict"],
    ["missing", "Missing or unavailable information", "missing"],
    ["uncertain", "Unclear or unsupported evidence", "uncertain"],
  ];
  const errors = kinds.filter(kind => counts[kind]?.error);
  const complete = kinds.every(kind => counts[kind] !== undefined);
  return <section aria-labelledby="dataset-overview-title" className="dataset-overview">
    <div className="overview-heading">
      <div><p className="text-sm text-muted-foreground">Import #{job.id}</p><h2 id="dataset-overview-title" className="mt-2 text-3xl font-semibold tracking-tight">Flights dataset</h2><p className="mt-2 break-words text-sm text-muted-foreground">{job.filename_original}</p></div>
      <Badge variant="success">{job.status}</Badge>
    </div>
    <p className="mt-3 text-muted-foreground">See what was imported, then explore the cases that were flagged.</p>
    <dl className="overview-metrics">
      <div><dt>Flights</dt><dd>{flights !== null ? flights.toLocaleString() : all === undefined ? "…" : "Unavailable"}</dd></div>
      <div><dt>Source records</dt><dd>{records?.toLocaleString() ?? "Unavailable"}</dd></div>
      <div><dt>Flagged cases</dt><dd>{display("attention")}</dd></div>
    </dl>
    <p className="text-sm text-muted-foreground">{display("all")} cases across four time fields. Flags describe findings, not review progress.</p>
    {!complete && <p role="status" className="mt-3 text-sm text-muted-foreground">Loading dataset summary…</p>}
    {all?.total !== undefined && flights === null && <p role="alert" className="notice-error mt-4">The case count does not match the four-field Flights contract. Flight count is unavailable.</p>}
    {all?.ungroupable !== undefined && all.ungroupable > 0 && <p className="canvas-notice mt-4">{all.ungroupable.toLocaleString()} source records could not be grouped into flights. They remain available in All source records.</p>}
    {errors.length > 0 && <div className="mt-4 space-y-3" role="alert">{errors.map(kind => <div key={kind} className="text-sm"><p>{kind === "all" ? "Case totals" : kind === "attention" ? "Flagged cases" : issueRows.find(row => row[0] === kind)?.[1]}: {counts[kind]!.error}</p><Button className="mt-2" variant="outline" size="sm" disabled={!complete} onClick={() => retryCount(kind)}>Retry {kind === "all" ? "case totals" : kind === "attention" ? "flagged cases" : issueRows.find(row => row[0] === kind)?.[1].toLowerCase()}</Button></div>)}</div>}
    <div className="overview-actions">
      <Button asChild variant="accent"><Link to={{pathname: "/investigate", search: reviewing}}>{counts.attention?.total === 0 ? "Explore cases" : "Review cases"}</Link></Button>
    </div>
    <section className="working-surface overview-findings" aria-labelledby="overview-findings-title">
      <div className="surface-section"><h3 id="overview-findings-title" className="text-xl font-semibold">What was found</h3>
        <dl className="overview-issues">{issueRows.map(([key, label, kind]) => <div key={key}><dt><Link to={{pathname: "/investigate", search: investigateSearch(search, "table", {kind, field: null, page: "1"})}}>{label}</Link></dt><dd>{display(key)}</dd></div>)}</dl>
        <p className="mt-4 text-sm text-muted-foreground">Counts refer to cases. Categories can overlap.</p>
      </div>
    </section>
    {counts.attention?.total === 0 && <p className="mt-5 text-sm">No cases were flagged for attention. This does not establish that every reported value is correct.</p>}
    {all?.total === 0 && <p className="mt-3 text-sm">No grouped flight/field cases are available. You can still inspect the original source records.</p>}
    <details className="mt-6 text-sm"><summary>Dataset details</summary><dl className="evidence-references mt-3"><dt>Supported format</dt><dd>{job.job_kind} · version {job.contract_version}</dd><dt>Case</dt><dd>One flight and one time field. Each grouped flight has four cases.</dd><dt>Source record</dt><dd>One original report. Source records and review cases are different units.</dd><dt>Grouping</dt><dd>Flight identifiers apply within this benchmark snapshot. Source agreement does not establish correctness.</dd></dl></details>
  </section>;
}
