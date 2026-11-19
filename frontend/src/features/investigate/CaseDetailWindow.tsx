import {useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject} from "react";
import {DialogClose, DialogContent, DialogDescription, DialogTitle} from "../../components/ui/dialog";
import {Button} from "../../components/ui/button";
import {type Evidence, fieldLabels} from "./contracts";

export type CaseDetailSelection = {kind: "sources" | "evidence" | "baseline" | "ai" | "review" | "history" | "review-form" | "review-close"} | {kind: "candidate"; candidateId: string};
export interface CaseDetailActions {
  detail: CaseDetailSelection | null;
  openDetail: (selection: CaseDetailSelection | null) => void;
  returnFocus: RefObject<HTMLElement>;
}

// A single case-local Dialog root owns these windows. This is not a second modal system.
export function CaseDetailWindow({title, evidence, wide = false, resizable = false, fullScreenMobile = false, returnFocus, children}: {
  title: string; evidence: Evidence; wide?: boolean; resizable?: boolean; fullScreenMobile?: boolean; returnFocus: RefObject<HTMLElement>; children: ReactNode;
}) {
  const closeButton = useRef<HTMLButtonElement>(null);
  const [viewport, setViewport] = useState(window.innerWidth);
  const [width, setWidth] = useState(1060);
  const drag = useRef<{id: number; x: number; width: number} | null>(null);
  const bounds = sourcePanelBounds(viewport);
  const visibleWidth = Math.min(bounds.max, Math.max(bounds.min, width));
  useEffect(() => {
    const resize = () => { setViewport(window.innerWidth); drag.current = null; };
    window.addEventListener("resize", resize); return () => window.removeEventListener("resize", resize);
  }, []);
  const adjust = (next: number) => setWidth(Math.min(bounds.max, Math.max(bounds.min, next)));
  return <DialogContent style={resizable && viewport >= 768 ? {"--case-panel-width": `${visibleWidth}px`} as CSSProperties : undefined} onOpenAutoFocus={event => {event.preventDefault(); closeButton.current?.focus({preventScroll: true});}} className={`case-detail-window focused-case investigation-detail ${wide ? "case-detail-sheet" : ""} ${fullScreenMobile ? "case-review-window" : ""}`} onCloseAutoFocus={event => {
    event.preventDefault();
    queueMicrotask(() => {
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      if (returnFocus.current?.isConnected) returnFocus.current.focus({preventScroll: true});
      else document.getElementById("main-content")?.focus({preventScroll: true});
    });
  }}>
    {resizable && wide && <div role="separator" tabIndex={0} aria-label="Resize source panel" aria-orientation="vertical" aria-valuemin={bounds.min} aria-valuemax={bounds.max} aria-valuenow={visibleWidth} aria-valuetext={`${Math.round(visibleWidth)} pixels`} className="case-resize-handle"
      onPointerDown={event => { if (viewport < 768 || event.button !== 0) return; event.preventDefault(); event.currentTarget.focus({preventScroll: true}); event.currentTarget.setPointerCapture(event.pointerId); drag.current = {id: event.pointerId, x: event.clientX, width: visibleWidth}; }}
      onPointerMove={event => { const start = drag.current; if (start && start.id === event.pointerId) adjust(start.width + start.x - event.clientX); }}
      onPointerUp={event => { if (drag.current?.id === event.pointerId) { drag.current = null; event.currentTarget.releasePointerCapture(event.pointerId); } }}
      onLostPointerCapture={() => { drag.current = null; }}
      onKeyDown={event => { if (viewport < 768) return; const next = event.key === "ArrowLeft" ? visibleWidth + 32 : event.key === "ArrowRight" ? visibleWidth - 32 : event.key === "Home" ? bounds.min : event.key === "End" ? bounds.max : null; if (next !== null) { event.preventDefault(); adjust(next); } }} />}
    <div className="case-window-heading"><div className="min-w-0"><DialogTitle className="text-xl font-semibold">{title}</DialogTitle><DialogDescription className="mt-2 text-sm text-muted-foreground">Flight {evidence.flight} · {fieldLabels[evidence.field]}</DialogDescription></div>
      <DialogClose asChild><Button ref={closeButton} variant="outline" aria-label="Close details" autoFocus>Close</Button></DialogClose>
    </div>
    <div className="case-window-body">{children}</div>
  </DialogContent>;
}

export function sourcePanelBounds(viewport: number) {
  const max = Math.min(1280, Math.max(0, viewport - 32));
  return {min: Math.min(680, max), max};
}
