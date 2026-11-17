import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Button } from "../ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "../ui/dialog";

const destinations = [["/", "Home"], ["/datasets", "Datasets"], ["/investigate", "Investigate"], ["/history", "History"]] as const;

export function ApplicationLayout() {
  const location = useLocation();
  const home = location.pathname === "/";
  const legacy = location.pathname.startsWith("/legacy/");
  const workspaceSearch = useRef("");
  const query = new URLSearchParams(location.search); query.delete("job");
  const currentFlightSearch = query.size ? `?${query}` : "";
  const navigationSearch = home || legacy ? workspaceSearch.current : currentFlightSearch;
  useEffect(() => { if (!home && !legacy) workspaceSearch.current = currentFlightSearch; }, [home, legacy, currentFlightSearch]);
  const menuLocation = useRef(location.key);
  const menuNavigating = useRef(false);
  const primaryNavigation = useRef<HTMLElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const heading = useRef<HTMLElement>(null);
  const previousPath = useRef(location.pathname);
  const previousJob = useRef(location.search);
  useEffect(() => {
    const titles: Record<string, string> = { "/": "Home", "/datasets": "Datasets", "/investigate": "Investigate", "/history": "History", "/legacy/transactions": "Transactions" };
    document.title = `${titles[location.pathname] ?? "Page not found"} · Reconcile Workbench`;
    const job = location.search;
    if (previousPath.current !== location.pathname || previousJob.current !== job) {
      heading.current?.focus({ preventScroll: true });
      if (previousPath.current !== location.pathname) window.scrollTo?.({ top: 0, behavior: "auto" });
    }
    previousPath.current = location.pathname;
    previousJob.current = job;
  }, [location.pathname, location.search]);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 768px)");
    const closeOnDesktop = () => { if (media.matches) setMenuOpen(false); };
    media.addEventListener("change", closeOnDesktop);
    return () => media.removeEventListener("change", closeOnDesktop);
  }, []);
  const nav = (mobile = false) => destinations.map(([path, label]) => (
    <NavLink key={path} end={path === "/"} to={{ pathname: path, search: path === "/" ? "" : navigationSearch }}
      className={mobile ? "nav-link mobile-nav-link w-full" : "nav-link"}
      onClick={() => { menuNavigating.current = mobile; setMenuOpen(false); }}>
      {label}
    </NavLink>
  ));
  return (
    <div className={`canvas-context ${home ? "home-mode" : "workspace-mode"} flex min-h-screen flex-col`}>
      <a className="skip-link" href="#main-content" onClick={(event) => {
        event.preventDefault();
        heading.current?.focus({ preventScroll: true });
        heading.current?.scrollIntoView({ behavior: "auto", block: "start" });
      }}>Skip to content</a>
      <header className="app-header site-header">
        <Link to="/" className="brand-lockup" aria-label="Reconcile Workbench home">
          <img src="/brand/reconcile-symbol-dark.svg" width="42" height="42" alt="" className="brand-symbol" />
          <span className="brand-name"><img src="/brand/reconcile-wordmark-dark.svg" width="145" height="29" alt="" /><span>Workbench</span></span>
        </Link>
        <nav ref={primaryNavigation} aria-label="Primary" className="desktop-navigation hidden md:flex">{nav()}</nav>
        <Dialog open={menuOpen} onOpenChange={(open) => { if (open) { menuLocation.current = location.key; menuNavigating.current = false; } setMenuOpen(open); }}>
          <DialogTrigger asChild>
            <Button id="mobile-menu-trigger" variant="ghost" className="md:hidden" aria-label="Open navigation" aria-expanded={menuOpen}>
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 6h14M3 10h14M3 14h14" /></svg>
              <span className="sr-only">Menu</span>
            </Button>
          </DialogTrigger>
          <DialogContent className="canvas-context top-4 translate-y-0" onCloseAutoFocus={(event) => {
            if (menuNavigating.current || menuLocation.current !== location.key) {
              event.preventDefault();
              queueMicrotask(() => {
                if (!document.querySelector('[role="dialog"][data-state="open"]')) heading.current?.focus({ preventScroll: true });
              });
            } else if (window.matchMedia("(min-width: 768px)").matches) {
              event.preventDefault();
              (primaryNavigation.current?.querySelector<HTMLAnchorElement>('a[aria-current="page"]') ?? primaryNavigation.current?.querySelector<HTMLAnchorElement>('a'))?.focus();
            }
          }}>
            <div className="mb-4 flex items-center justify-between gap-4">
              <DialogTitle className="text-lg font-semibold">Navigation</DialogTitle>
              <DialogClose asChild><Button variant="ghost" aria-label="Close navigation">Close</Button></DialogClose>
            </div>
            <DialogDescription className="sr-only">Choose a workspace page.</DialogDescription>
            <nav aria-label="Mobile primary" className="flex flex-col gap-1">{nav(true)}</nav>
          </DialogContent>
        </Dialog>
      </header>
      <main id="main-content" ref={heading} tabIndex={-1} className="flex-1 outline-none"><Outlet context={{ workspaceSearch: navigationSearch }} /></main>
      <footer className="app-header site-footer">Reconcile Workbench</footer>
    </div>
  );
}
