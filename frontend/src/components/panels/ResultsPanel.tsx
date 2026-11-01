import { RecordExplorer } from "./RecordExplorer";
import { useEffect, useState } from "react";
import { isActive, statusClass } from "../../lib/job-state";
import { api, downloadUrl } from "../../lib/api";
import type { AiReport, JobDetail } from "../../types/jobs";
import { SectionCard } from "../layout/SectionCard";
import { AnalysisView } from "../analytics/AnalysisView";

export function ResultsPanel({
  jobId,
  isLoading = false,
  onTerminal,
  onSelect,
  onDraftChange,
}: {
  jobId: number | null;
  isLoading?: boolean;
  onTerminal?: () => void;
  onSelect?: (id: number) => void;
  onDraftChange?: (hasDrafts: boolean) => void;
}) {
  const [category, setCategory] = useState("");
  const [categoryChange, setCategoryChange] = useState(0);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    setJob(null);
    setCategory("");
    setError("");
    if (jobId === null) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let active = true;
    const load = async () => {
      setLoading(true);
      try {
        const data = await api<JobDetail>(`/api/v1/jobs/${jobId}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setJob(data);
        setError("");
        active = isActive(data.status);
        if (active) timer = setTimeout(load, 1500);
        else onTerminal?.();
      } catch (failure) {
        if (!controller.signal.aborted) {
          if (active) timer = setTimeout(load, 3000);
          setError(
            failure instanceof Error ? failure.message : "Could not load job.",
          );
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [jobId, retry, onTerminal]);
  return (
    <SectionCard
      title="Job workspace"
      description="Persisted results, quality measurements and actionable exceptions."
    >
      {error && (
        <div role="alert" className="notice-error">
          {error}{" "}
          <button
            className="underline"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry
          </button>
        </div>
      )}
      {isLoading || (loading && !job) ? (
        <div role="status" className="space-y-4 py-8">
          <p className="text-sm text-textMuted">
            {isLoading ? "Uploading your file…" : "Loading job details…"}
          </p>
          <div className="h-20 animate-pulse rounded-xl bg-surfaceSoft" />
          <p className="text-xs text-textMuted">
            Results appear when validation and report generation finish.
          </p>
        </div>
      ) : !job ? (
        <div className="empty-state py-16">
          <p className="mb-2 text-lg text-textMain">
            Your next dataset, understood.
          </p>
          <p>Upload a CSV or open a historical job to inspect its quality.</p>
          <p className="mt-3 text-xs">
            12 required fields · Row-level validation · Downloadable reports
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">JOB #{job.id}</p>
              <h2 className="mt-1 break-all text-lg font-medium">
                {job.filename_original}
              </h2>
              <p className="mt-1 text-xs text-textMuted">
                {job.file_size === null
                  ? "Size unavailable"
                  : `${(job.file_size / 1024).toFixed(1)} KB`}{" "}
                ·{" "}
                {isActive(job.status) || job.duration_ms === null
                  ? "Processing duration available on completion"
                  : `${job.duration_ms} ms`}{" "}
                ·{" "}
                {new Date(
                  job.created_at.endsWith("Z")
                    ? job.created_at
                    : job.created_at + "Z",
                ).toLocaleString()}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {job.status === "completed" && (
                <a className="button-secondary" href="#history">
                  View history ↓
                </a>
              )}
              <span className={`status-badge ${statusClass(job.status)}`}>
                {job.status}
              </span>
            </div>
          </div>
          {job.error_message && (
            <p className="notice-error mt-4" role="alert">
              {job.error_message}
            </p>
          )}
          {isActive(job.status) ? (
            <section
              role="status"
              aria-live="polite"
              className="subcard my-5 space-y-3"
            >
              <h3 className="font-medium">
                {job.status === "pending"
                  ? "Waiting for dispatch"
                  : job.status === "queued"
                    ? "Queued for a worker"
                    : "Processing your CSV"}
              </h3>
              <ol
                className="flex flex-wrap gap-4 text-xs text-textMuted"
                aria-label="Processing lifecycle"
              >
                <li>1. Upload accepted</li>
                <li>2. Queued</li>
                <li>3. Processing</li>
                <li>4. Results ready</li>
              </ol>
              <p className="text-sm text-textMuted">
                {job.status === "processing"
                  ? `Validation, normalization and analysis are running (attempt ${job.attempts ?? 1}).`
                  : "The file is safely stored. This page will update automatically when a worker completes the job."}{" "}
                You can refresh or return through processing history.
              </p>
            </section>
          ) : (
            <>
              <div className="my-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {[
                  [
                    "Quality score",
                    job.status === "completed"
                      ? (job.analysis?.quality?.score ?? "—")
                      : "—",
                  ],
                  ["Total records", job.total_rows],
                  ["Accepted", job.valid_rows],
                  ["Rejected", job.invalid_rows],
                  [
                    "Validation issues",
                    job.analysis?.validation_issue_count ??
                      Object.values(job.error_breakdown).reduce(
                        (a, b) => a + b,
                        0,
                      ),
                  ],
                  ["Anomaly signals", job.analysis?.anomaly_count ?? "—"],
                ].map(([name, value]) => (
                  <div key={name} className="subcard">
                    <p className="text-xs text-textMuted">{name}</p>
                    <p className="mt-2 tabular-nums text-3xl font-semibold">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    ["input", "Original CSV", job.filename_input_saved],
                    ["clean", "Cleaned CSV", job.filename_cleaned],
                    ["errors", "Error CSV", job.filename_error_report],
                  ] as const
                ).map(
                  ([kind, title, filename]) =>
                    filename && (
                      <a
                        key={kind}
                        className="button-secondary"
                        href={downloadUrl(job.id, kind)}
                      >
                        {title} ↓
                      </a>
                    ),
                )}
              </div>
              {job.parent_summary && (
                <section
                  className="subcard my-5"
                  aria-label="Correction comparison"
                >
                  <h3 className="font-medium">Correction results</h3>
                  <p className="mt-2 text-sm">
                    Accepted: {job.parent_summary.valid_rows} → {job.valid_rows}{" "}
                    · Rejected: {job.parent_summary.invalid_rows} →{" "}
                    {job.invalid_rows}
                  </p>
                  <p className="mt-1 text-sm">
                    Quality score: {job.parent_summary.score ?? "—"} →{" "}
                    {job.analysis?.quality?.score ?? "—"}
                  </p>
                  <button
                    className="mt-3 text-xs text-accentSoft underline"
                    onClick={() => onSelect?.(job.parent_summary!.id)}
                  >
                    Open original job #{job.parent_summary.id}
                  </button>
                  <details className="mt-3 text-xs">
                    <summary className="cursor-pointer">
                      View saved corrections
                    </summary>
                    {Object.entries(job.corrections ?? {}).map(
                      ([row, changes]) => (
                        <div className="mt-2" key={row}>
                          <strong>Record {row}</strong>
                          {Object.entries(changes).map(([field, change]) => (
                            <p className="break-all" key={field}>
                              {field}: {change.before || "(empty)"} →{" "}
                              {change.after || "(empty)"}
                            </p>
                          ))}
                        </div>
                      ),
                    )}
                  </details>
                </section>
              )}
              {!!job.child_job_ids?.length && (
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  Correction jobs:{" "}
                  {job.child_job_ids.map((id) => (
                    <button
                      key={id}
                      className="text-accentSoft underline"
                      onClick={() => onSelect?.(id)}
                    >
                      Open correction #{id}
                    </button>
                  ))}
                </div>
              )}
              {job.import_options?.template_id && (
                <p className="mt-3 text-xs text-textMuted">
                  Import template #{job.import_options.template_id} · version{" "}
                  {job.import_options.template_version} (saved snapshot)
                </p>
              )}
              <AnalysisView
                key={job.id}
                job={job}
                onExplore={
                  job.records_available
                    ? (value) => {
                        setCategory(value);
                        setCategoryChange((count) => count + 1);
                        document
                          .getElementById(`records-${job.id}`)
                          ?.scrollIntoView({ behavior: "smooth" });
                      }
                    : undefined
                }
              />
              {job.records_available && (
                <RecordExplorer
                  key={`records-${job.id}`}
                  job={job}
                  category={category}
                  categoryChange={categoryChange}
                  onCreated={onSelect}
                  onDraftChange={onDraftChange}
                />
              )}
              {job.status === "completed" && !job.records_available && (
                <p className="mt-4 text-xs text-textMuted">
                  This historical job has no record index. Upload its original
                  CSV again to explore and correct records.
                </p>
              )}
              <AiInsights key={`ai-${job.id}`} job={job} />
            </>
          )}
        </>
      )}
    </SectionCard>
  );
}

function AiInsights({ job }: { job: JobDetail }) {
  const [report, setReport] = useState<AiReport | null>(job.ai_report);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generate = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api<{
        report: AiReport | null;
        error: string | null;
      }>(`/api/v1/jobs/${job.id}/ai-analysis`, { method: "POST" });
      setReport(result.report);
      setError(result.error ?? "");
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "AI request failed.",
      );
    } finally {
      setBusy(false);
    }
  };
  const download = () => {
    if (!report) return;
    const text = `# AI interpretation — job ${job.id}\n\n${report.executive_summary}\n\n## Issues\n${report.key_issues.map((item) => `- ${item}`).join("\n")}\n\n## Actions\n${report.recommended_actions.map((item) => `- ${item}`).join("\n")}\n\n## Business impact\n${report.business_impact}\n`;
    const url = URL.createObjectURL(
      new Blob([text], { type: "text/markdown" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `job-${job.id}-ai-report.md`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section className="mt-6 border-t border-borderSoft pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-medium">
            AI interpretation{" "}
            <span className="text-xs text-textMuted">/ Optional</span>
          </h3>
          <p className="mt-1 text-xs text-textMuted">
            Aggregates only. No raw records or customer identifiers are sent.
            The platform score above is deterministic.
          </p>
        </div>
        {!report && (
          <button
            className="button-secondary"
            onClick={generate}
            disabled={busy || job.status !== "completed"}
          >
            {busy ? "Generating…" : "Generate insights"}
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-warning">
          {error}
        </p>
      )}
      {report && (
        <div className="mt-4 space-y-4 text-sm">
          <p>{report.executive_summary}</p>
          <p className="text-xs text-textMuted">
            AI-assessed severity: {report.severity} · AI-assessed score:{" "}
            {report.quality_score}/100
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <h4 className="mb-2 font-medium">Key issues</h4>
              <ul className="list-inside list-disc space-y-2 text-textMuted">
                {report.key_issues.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="mb-2 font-medium">Recommended actions</h4>
              <ul className="list-inside list-disc space-y-2 text-textMuted">
                {report.recommended_actions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
          <p className="text-textMuted">{report.business_impact}</p>
          <button className="button-secondary" onClick={download}>
            Download interpretation ↓
          </button>
        </div>
      )}
    </section>
  );
}
