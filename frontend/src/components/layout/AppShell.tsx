import { useCallback, useEffect, useRef, useState } from "react";
import { preferredScrollBehavior } from "../../lib/utils";
import { JobsPanel } from "../panels/JobsPanel";
import { ResultsPanel } from "../panels/ResultsPanel";
import { UploadPanel } from "../panels/UploadPanel";

interface WorkspaceNavigation {
  jobId: number | null;
  selectJob: (id: number) => void;
  onDraftChange: (dirty: boolean) => void;
}

export function AppShell({ navigation }: { navigation?: WorkspaceNavigation } = {}) {
  const [localJobId, setJobId] = useState<number | null>(() => {
    const value = Number(
      new URLSearchParams(window.location.search).get("job"),
    );
    return Number.isInteger(value) && value > 0 && value <= 2147483647
      ? value
      : null;
  });
  const jobId = navigation ? navigation.jobId : localJobId;
  const routeDraftChange = navigation?.onDraftChange;
  const unsavedDrafts = useRef(false);
  const onDraftChange = useCallback((hasDrafts: boolean) => {
    unsavedDrafts.current = hasDrafts;
    routeDraftChange?.(hasDrafts);
  }, [routeDraftChange]);
  const [pendingJob, setPendingJob] = useState<number | null>(null);
  const navigationDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = navigationDialog.current;
    if (pendingJob !== null) {
      if (!dialog?.open) dialog?.showModal();
    } else if (dialog?.open) {
      dialog.close();
    }
  }, [pendingJob]);
  const selectJob = (id: number) => {
    if (id === jobId) return true;
    if (navigation) {
      navigation.selectJob(id);
      return !unsavedDrafts.current;
    }
    if (unsavedDrafts.current) {
      setPendingJob(id);
      return false;
    }
    setPendingJob(null);
    setJobId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("job", String(id));
    window.history.replaceState(null, "", url);
    return true;
  };
  const [isProcessing, setIsProcessing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const onTerminal = useCallback(() => setRefreshKey((key) => key + 1), []);
  const resultsRef = useRef<HTMLDivElement>(null);
  return (
    <div
      id="dashboard"
      className="workspace-container"
    >
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-borderSoft pb-6">
        <div>
          <p className="eyebrow">DATA WORKSPACE</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            Legacy transaction workspace
          </h1>
          <p className="mt-2 text-sm text-textMuted">
            Import, review and refine your transaction data.
          </p>
        </div>
        <a className="button-primary" href="#new-job" onClick={(event) => {
          event.preventDefault();
          document.getElementById("new-job")?.scrollIntoView({
            behavior: preferredScrollBehavior(),
            block: "start",
          });
        }}>
          + New processing job
        </a>
      </header>
      <div className="space-y-6">
        <div className="grid items-start gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div id="new-job">
            <UploadPanel
              onUploadStart={() => setIsProcessing(true)}
              onUploadError={() => setIsProcessing(false)}
              onUploadComplete={(result) => {
                selectJob(result.job_id);
                setIsProcessing(false);
                setRefreshKey((key) => key + 1);
              }}
            />
          </div>
          <div id="workspace" ref={resultsRef} className="min-w-0 scroll-mt-4">
            <ResultsPanel
              jobId={jobId}
              isLoading={isProcessing && !unsavedDrafts.current}
              onDraftChange={onDraftChange}
              onTerminal={onTerminal}
              onSelect={(id) => {
                selectJob(id);
                setRefreshKey((key) => key + 1);
              }}
            />
          </div>
        </div>
        <div id="history">
          <JobsPanel
            refreshKey={refreshKey}
            selectedId={jobId}
            onSelect={(id) => {
              if (selectJob(id))
                resultsRef.current?.scrollIntoView({
                  behavior: preferredScrollBehavior(),
                  block: "start",
                });
            }}
          />
        </div>
      </div>
      <dialog
        ref={navigationDialog}
        onCancel={() => setPendingJob(null)}
        aria-labelledby="draft-navigation-title"
        aria-describedby="draft-navigation-description"
        className="w-[95vw] max-w-md rounded-2xl border border-borderSoft bg-surface p-6 text-textMain backdrop:bg-black/70"
      >
        <h2 id="draft-navigation-title" className="text-lg font-medium">
          Discard unsaved corrections?
        </h2>
        <p id="draft-navigation-description" className="mt-3 text-sm text-textMuted">
          Switching to job #{pendingJob} will discard your unsaved corrections.
          Cancel to keep editing the current job.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button className="button-secondary" onClick={() => setPendingJob(null)}>
            Cancel
          </button>
          <button
            className="button-primary"
            onClick={() => {
              if (pendingJob === null) return;
              unsavedDrafts.current = false;
              selectJob(pendingJob);
              resultsRef.current?.scrollIntoView({ behavior: preferredScrollBehavior(), block: "start" });
            }}
          >
            Discard
          </button>
        </div>
      </dialog>
      <footer className="py-8 text-xs text-textMuted">
        Deterministic validation · Local file storage · Optional AI
        interpretation
      </footer>
    </div>
  );
}
