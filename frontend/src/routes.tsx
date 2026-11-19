import { useCallback, useRef } from "react";
import { Link, Navigate, type RouteObject, useBlocker, useLocation, useNavigate } from "react-router-dom";
import { InvestigatePage } from "./features/investigate/InvestigatePage";
import { HistoryPage } from "./features/history/HistoryPage";
import { HomePage } from "./features/HomePage";
import { DatasetsPage } from "./features/datasets/DatasetsPage";
import { validJobId } from "./features/datasets/flights";
import { ApplicationLayout } from "./components/layout/ApplicationLayout";
import { AppShell } from "./components/layout/AppShell";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./components/ui/dialog";

function jobFrom(search: string) {
  const value = Number(new URLSearchParams(search).get("job"));
  return Number.isInteger(value) && value > 0 && value <= 2147483647 ? value : null;
}

function HomeRoute() {
  const location = useLocation();
  if (jobFrom(location.search)) return <Navigate to={{ pathname: "/legacy/transactions", search: location.search, hash: location.hash }} replace />;
  return <HomePage />;
}

function DatasetsRoute() {
  const location = useLocation();
  // M9 transaction links must never be interpreted as Flights identifiers.
  if (jobFrom(location.search)) return <Navigate to={{ pathname: "/legacy/transactions", search: location.search, hash: location.hash }} replace />;
  const query = new URLSearchParams(location.search);
  const id = validJobId(query.get("dataset"));
  return <DatasetsPage key={id ?? "new"} datasetId={id} invalidId={query.has("dataset") && id === null} />;
}

function LegacyWorkspace() {
  const location = useLocation();
  const navigate = useNavigate();
  const dirty = useRef(false);
  const returnFocus = useRef<HTMLElement | null>(null);
  const onDraftChange = useCallback((value: boolean) => { dirty.current = value; }, []);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty.current &&
    (currentLocation.pathname !== nextLocation.pathname || jobFrom(currentLocation.search) !== jobFrom(nextLocation.search)));
  const selectJob = (id: number) => {
    const params = new URLSearchParams(location.search);
    params.set("job", String(id));
    navigate({ pathname: "/legacy/transactions", search: `?${params}`, hash: location.hash });
  };
  return <>
    <div className="workspace-container pb-0">
      <div className="flex flex-wrap items-center gap-3 pt-4"><p className="eyebrow">LEGACY / TRANSACTIONS</p><Badge>Existing transaction workflow</Badge></div>
      <p className="mt-3 max-w-3xl text-sm text-muted-foreground">Upload, inspect and correct transaction files using the original application. Flights observations belong in the separate Datasets workspace.</p>
    </div>
    <div className="workspace-container"><div className="working-surface"><AppShell navigation={{ jobId: jobFrom(location.search), selectJob, onDraftChange }} /></div></div>
    <Dialog open={blocker.state === "blocked"} onOpenChange={(open) => { if (!open && blocker.state === "blocked") blocker.reset(); }}>
      <DialogContent onOpenAutoFocus={() => { returnFocus.current = document.activeElement as HTMLElement | null; }}
        onPointerDownOutside={(event) => event.preventDefault()} onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (blocker.state === "proceeding") return;
          queueMicrotask(() => {
            const previous = returnFocus.current;
            const mobileTrigger = document.getElementById("mobile-menu-trigger");
            if (previous?.isConnected && previous.getClientRects().length) previous.focus({ preventScroll: true });
            else if (mobileTrigger?.getClientRects().length) mobileTrigger.focus({ preventScroll: true });
            else document.getElementById("main-content")?.focus({ preventScroll: true });
          });
        }}>
        <DialogTitle className="text-lg font-semibold">Discard unsaved corrections?</DialogTitle>
        <DialogDescription className="mt-3 text-sm text-muted-foreground">Leaving this view will discard your correction draft. Cancel to keep editing.</DialogDescription>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button variant="outline" autoFocus onClick={() => blocker.state === "blocked" && blocker.reset()}>Cancel</Button>
          <Button onClick={() => { if (blocker.state === "blocked") { dirty.current = false; blocker.proceed(); } }}>Discard and continue</Button>
        </div>
      </DialogContent>
    </Dialog>
  </>;
}

function NotFound() {
  const location = useLocation();
  return <section className="workspace-container min-h-[65vh] py-16">
    <p className="eyebrow">404 · PAGE NOT FOUND</p><h1 className="workspace-title mt-4">That page isn’t here.</h1>
    <p className="mt-4 max-w-lg text-muted-foreground">Use the navigation to return to a workspace page.</p>
    <Button asChild className="mt-6"><Link to={{ pathname: "/datasets", search: location.search }}>Open workspace</Link></Button>
  </section>;
}

export const applicationRoutes: RouteObject[] = [{ element: <ApplicationLayout />, children: [
  { index: true, element: <HomeRoute /> },
  { path: "datasets", element: <DatasetsRoute /> },
  { path: "legacy/transactions", element: <LegacyWorkspace /> },
  { path: "investigate", element: <InvestigatePage /> },
  { path: "history", element: <HistoryPage /> },
  { path: "*", element: <NotFound /> },
] }];
