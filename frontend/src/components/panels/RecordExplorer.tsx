import { useEffect, useRef, useState } from "react";
import { api, API_BASE_URL } from "../../lib/api";
import type { JobDetail, UploadResult } from "../../types/jobs";
import {
  FIELDS,
  fieldLabel,
  type DatasetRecord,
  type RecordPage,
  type Issue,
} from "../../types/imports";

type Validation = {
  valid: boolean;
  rows: { row_number: number; issues: Issue[] }[];
  message: string;
};
export function RecordExplorer({
  job,
  category = "",
  categoryChange = 0,
  onCreated,
  onDraftChange,
}: {
  job: Pick<JobDetail, "id" | "error_breakdown">;
  category?: string;
  categoryChange?: number;
  onCreated?: (id: number) => void;
  onDraftChange?: (hasDrafts: boolean) => void;
}) {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [errorCategory, setErrorCategory] = useState(category);
  const [sort, setSort] = useState("row_number");
  const [direction, setDirection] = useState("asc");
  const [visible, setVisible] = useState<string[]>([
    "customer_id",
    "email",
    "country",
    "currency",
    "order_amount",
  ]);
  const [data, setData] = useState<RecordPage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<DatasetRecord | null>(null);
  const [patches, setPatches] = useState<
    Record<string, Record<string, string>>
  >({});
  const [validation, setValidation] = useState<Validation | null>(null);
  const [busy, setBusy] = useState(false);
  const [child, setChild] = useState<number | null>(null);
  const editor = useRef<HTMLDivElement>(null);
  const active = useRef(false);
  useEffect(() => {
    // ResultsPanel keys each explorer by job; navigation ends this instance's lifetime.
    active.current = true;
    return () => { active.current = false; };
  }, []);
  const draftCount = Object.keys(patches).length;
  useEffect(() => {
    onDraftChange?.(draftCount > 0);
    return () => onDraftChange?.(false);
  }, [draftCount, onDraftChange]);
  useEffect(() => {
    setErrorCategory(category);
    setPage(1);
    setStatus(category ? "rejected" : "all");
  }, [category, categoryChange]);
  useEffect(() => {
    if (!draftCount) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [draftCount]);
  const params = new URLSearchParams({
    page: String(page),
    page_size: "25",
    status,
    search,
    category: errorCategory,
    sort,
    direction,
  });
  const query = params.toString();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      api<RecordPage>(`/api/v1/jobs/${job.id}/records?${query}`, {
        signal: controller.signal,
      })
        .then((value) => {
          if (!controller.signal.aborted) setData(value);
        })
        .catch((failure) => {
          if (!controller.signal.aborted) setError((failure as Error).message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [job.id, query, reload]);
  const resetFilters = () => {
    setPage(1);
    setStatus("all");
    setSearch("");
    setErrorCategory("");
    setSort("row_number");
    setDirection("asc");
  };
  const changeCell = (field: string, value: string) => {
    if (!selected) return;
    setPatches((current) => {
      const next = { ...current };
      const row = { ...next[selected.row_number] };
      if (value === selected.values[field]) delete row[field];
      else row[field] = value;
      if (Object.keys(row).length) next[selected.row_number] = row;
      else delete next[selected.row_number];
      return next;
    });
    setValidation(null);
    setChild(null);
  };
  const validate = async () => {
    setBusy(true);
    setError("");
    setValidation(null);
    try {
      setValidation(
        await api<Validation>(`/api/v1/jobs/${job.id}/corrections/validate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ patches }),
        }),
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const reprocess = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api<UploadResult>(
        `/api/v1/jobs/${job.id}/corrections`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ patches }),
        },
      );
      // The child stays saved, but a departed workspace must not notify or navigate.
      if (!active.current) return;
      setChild(result.job_id);
      setPatches({});
      setValidation(null);
      setSelected(null);
      // Submission has saved these changes before navigation to the child job.
      onDraftChange?.(false);
      onCreated?.(result.job_id);
    } catch (failure) {
      if (active.current) setError((failure as Error).message);
    } finally {
      if (active.current) setBusy(false);
    }
  };
  const selectedIssues = selected
    ? (validation?.rows.find((row) => row.row_number === selected.row_number)
        ?.issues ?? selected.issues)
    : [];
  return (
    <section
      id={`records-${job.id}`}
      className="mt-7 min-w-0 border-t border-borderSoft pt-5"
      aria-label="Dataset explorer"
    >
      <h3 className="font-medium">Dataset explorer</h3>
      <p className="mt-1 text-xs text-textMuted">
        Search the complete result. Values are the mapped source values;
        normalized output remains available in Cleaned CSV. Field sorting is
        alphabetical.
      </p>
      <div className="my-4 grid gap-3 sm:grid-cols-2">
        <label className="text-xs">
          Search all records
          <input
            className="field mt-1"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Value, record number or error"
          />
        </label>
        <label className="text-xs">
          Record status
          <select
            className="field mt-1"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">All records</option>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
        <label className="text-xs">
          Error category
          <select
            className="field mt-1"
            value={errorCategory}
            onChange={(e) => {
              setErrorCategory(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            {Object.keys(job.error_breakdown).map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs">
            Sort by
            <select
              className="field mt-1"
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
            >
              {["row_number", "status", ...FIELDS].map((f) => (
                <option key={f} value={f}>
                  {fieldLabel(f)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs">
            Direction
            <select
              className="field mt-1"
              value={direction}
              onChange={(e) => {
                setDirection(e.target.value);
                setPage(1);
              }}
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </label>
        </div>
      </div>
      <button
        className="button-secondary mb-3"
        onClick={resetFilters}
      >
        Reset Filters
      </button>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <details className="text-xs">
          <summary className="cursor-pointer">Visible columns</summary>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {FIELDS.map((f) => (
              <label key={f}>
                <input
                  type="checkbox"
                  checked={visible.includes(f)}
                  onChange={(e) =>
                    setVisible((current) =>
                      e.target.checked
                        ? [...current, f]
                        : current.filter((k) => k !== f),
                    )
                  }
                />{" "}
                {fieldLabel(f)}
              </label>
            ))}
          </div>
        </details>
        <a
          className="button-secondary"
          href={`${API_BASE_URL}/api/v1/jobs/${job.id}/records/export?${query}`}
        >
          Export filtered CSV
        </a>
      </div>
      {error && (
        <div className="notice-error" role="alert">
          {error}{" "}
          <button className="underline" onClick={() => setReload((v) => v + 1)}>
            Retry records
          </button>
        </div>
      )}
      {loading && (
        <p role="status" className="py-2 text-xs text-textMuted">
          Loading records…
        </p>
      )}
      <div
        className="max-w-full overflow-x-auto rounded-lg border border-borderSoft"
        aria-busy={loading}
      >
        <table className="data-table">
          <thead>
            <tr>
              <th>Record</th>
              <th>Status</th>
              {visible.map((f) => (
                <th key={f}>{fieldLabel(f)}</th>
              ))}
              <th>Issues</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {data?.records.map((row) => (
              <tr
                key={row.row_number}
                className={
                  selected?.row_number === row.row_number ? "bg-accent/10" : ""
                }
              >
                <td>
                  {row.row_number}
                  {patches[row.row_number] && (
                    <span className="ml-1 text-warning">edited</span>
                  )}
                </td>
                <td>
                  <span
                    className={
                      row.status === "accepted"
                        ? "text-success"
                        : "text-danger"
                    }
                  >
                    {row.status}
                  </span>
                </td>
                {visible.map((field) => (
                  <td
                    key={field}
                    className={
                      row.issues.some((i) => i.fields.includes(field))
                        ? "bg-danger/5 text-danger"
                        : ""
                    }
                  >
                    <span
                      className="block max-w-48 truncate"
                      title={
                        patches[row.row_number]?.[field] ?? row.values[field]
                      }
                    >
                      {(patches[row.row_number]?.[field] ??
                        row.values[field]) ||
                        "—"}
                    </span>
                  </td>
                ))}
                <td>{row.issues.length}</td>
                <td>
                  <button
                    className="text-accentSoft underline"
                    disabled={busy}
                    onClick={() => {
                      setSelected(row);
                      setTimeout(
                        () =>
                          editor.current?.scrollIntoView?.({
                            behavior: "smooth",
                            block: "nearest",
                          }),
                        0,
                      );
                    }}
                  >
                    {row.status === "rejected"
                      ? `Correct record ${row.row_number}`
                      : `Inspect record ${row.row_number}`}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && !data?.records.length && (
          <p className="empty-state">No matching records.</p>
        )}
      </div>
      <div className="my-3 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span>
          {data?.total ?? 0} matching records · Page {page} of{" "}
          {Math.max(1, Math.ceil((data?.total ?? 0) / 25))}
        </span>
        <div className="flex gap-2">
          <button
            className="button-secondary"
            disabled={page === 1 || loading}
            onClick={() => setPage((v) => v - 1)}
          >
            Previous records
          </button>
          <button
            className="button-secondary"
            disabled={loading || page * 25 >= (data?.total ?? 0)}
            onClick={() => setPage((v) => v + 1)}
          >
            Next records
          </button>
        </div>
      </div>
      {selected && (
        <div
          ref={editor}
          className="subcard my-4"
          role="region"
          aria-label={`Record ${selected.row_number} details`}
        >
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-medium">
              Record {selected.row_number} · {selected.status}
            </h4>
            <button
              className="text-xs underline"
              onClick={() => setSelected(null)}
            >
              Close record
            </button>
          </div>
          {selectedIssues.length > 0 && (
            <ul className="my-3 space-y-1 text-xs text-warning">
              {selectedIssues.map((issue, i) => (
                <li key={i}>{issue.message}</li>
              ))}
            </ul>
          )}
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {FIELDS.map((field) => {
              const messages = selectedIssues.filter((i) =>
                i.fields.includes(field),
              );
              const readonly =
                selected.status !== "rejected" ||
                selected.issues.some((i) => i.category === "CSV Structure");
              return (
                <label key={field} className="min-w-0 text-xs capitalize">
                  {fieldLabel(field)}
                  <input
                    aria-label={`Record ${selected.row_number} ${field}`}
                    aria-invalid={messages.length > 0}
                    aria-describedby={
                      messages.length
                        ? `issue-${selected.row_number}-${field}`
                        : undefined
                    }
                    className={`field mt-1 ${messages.length ? "border-danger/50" : ""}`}
                    readOnly={readonly}
                    disabled={busy}
                    value={
                      patches[selected.row_number]?.[field] ??
                      selected.values[field] ??
                      ""
                    }
                    onChange={(e) => changeCell(field, e.target.value)}
                  />
                  {messages.length > 0 && (
                    <span
                      id={`issue-${selected.row_number}-${field}`}
                      className="mt-1 block normal-case text-danger"
                    >
                      {messages.map((i) => i.message).join("; ")}
                    </span>
                  )}
                </label>
              );
            })}
          </div>
          {selected.status === "rejected" && (
            <button
              className="mt-3 text-xs underline"
              disabled={busy}
              onClick={() => {
                setPatches((current) => {
                  const next = { ...current };
                  delete next[selected.row_number];
                  return next;
                });
                setValidation(null);
              }}
            >
              Undo this record
            </button>
          )}
          {selected.issues.some((i) => i.category === "CSV Structure") && (
            <p className="mt-3 text-xs text-warning">
              This record has a column-count error. Repair the source CSV and
              upload it again.
            </p>
          )}
        </div>
      )}
      {draftCount > 0 && (
        <div className="subcard space-y-3 border-accent/40">
          <p className="text-sm font-medium">
            {draftCount} record{draftCount === 1 ? "" : "s"} with unsaved
            corrections
          </p>
          <p className="text-xs text-textMuted">
            Changes stay in this workspace until submitted. Originals remain
            unchanged. Up to 200 records per correction batch.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              className="button-secondary"
              disabled={busy}
              onClick={() => void validate()}
            >
              Validate corrections
            </button>
            <button
              className="button-primary"
              disabled={busy || !validation?.valid}
              onClick={() => void reprocess()}
            >
              Reprocess corrected dataset
            </button>
            <button
              className="button-secondary"
              disabled={busy}
              onClick={() => {
                setPatches({});
                setValidation(null);
              }}
            >
              Undo all corrections
            </button>
          </div>
          {validation && (
            <div
              role="status"
              className={`text-xs ${validation.valid ? "text-success" : "text-warning"}`}
            >
              <p>
                {validation.valid
                  ? "Field validation passed."
                  : "Some corrected fields still need attention."}
              </p>
              <p className="mt-1">{validation.message}</p>
              {validation.rows
                .filter((row) => row.issues.length)
                .map((row) => (
                  <p key={row.row_number}>
                    Record {row.row_number}:{" "}
                    {row.issues.map((i) => i.message).join("; ")}
                  </p>
                ))}
            </div>
          )}
        </div>
      )}
      {child && (
        <p role="status" className="text-sm text-success">
          Correction job #{child} created.
        </p>
      )}
    </section>
  );
}
