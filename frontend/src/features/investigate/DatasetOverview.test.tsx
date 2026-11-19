import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { applicationRoutes } from "../../routes";
import { investigateSearch, investigateView } from "./contracts";

const job = {id: 7, job_kind: "raha_flights_v1", contract_version: 1, status: "completed", filename_original: "reports.csv", observation_count: 37};
const totals: Record<string, number> = {all: 24, attention: 19, conflict: 12, missing: 17, uncertain: 9};
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {"Content-Type": "application/json"}});
function count(url: URL, total = totals[url.searchParams.get("kind")!]) {
  return {job_id: 7, total, page: 1, page_size: 1, discrepancies: total ? [{}] : [], ungroupable_observation_count: 1};
}
let routers: ReturnType<typeof createMemoryRouter>[] = [];
let custom: ((url: URL, options?: RequestInit) => Promise<Response | null> | Response | null) | null;
beforeEach(() => {
  custom = null;
  vi.stubGlobal("matchMedia", vi.fn(() => ({matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn()})));
  vi.stubGlobal("scrollTo", vi.fn()); Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (input: string, options?: RequestInit) => {
    const url = new URL(input); const result = await custom?.(url, options); if (result) return result;
    return response(url.pathname.endsWith("/discrepancies") ? url.searchParams.get("page_size") === "1" ? count(url) : {job_id: 7, total: 0, page: 1, page_size: 15, discrepancies: [], ungroupable_observation_count: 1} : job);
  }));
});
afterEach(() => {routers.forEach(r => r.dispose()); routers = []; vi.unstubAllGlobals(); Reflect.deleteProperty(Element.prototype, "scrollIntoView");});
function mount(url = "/investigate?dataset=7") {
  const router = createMemoryRouter(applicationRoutes, {initialEntries: [url], future: {v7_relativeSplatPath: true}}); routers.push(router);
  render(<RouterProvider router={router} future={{v7_startTransition: true}} />); return router;
}
async function loaded() {await screen.findByText("24 cases across four time fields. Flags describe findings, not review progress."); await waitFor(() => expect(screen.queryByText("Loading dataset summary…")).not.toBeInTheDocument());}

it.each([
  ["?dataset=7", "overview"], ["?dataset=7&view=overview&kind=missing", "overview"],
  ["?dataset=7&view=table", "table"], ["?dataset=7&view=case", "table"],
  ["?dataset=7&kind=conflict", "table"], ["?dataset=7&field=act_dep_time", "table"], ["?dataset=7&page=2", "table"],
  ["?dataset=7&discrepancy=original", "case"], ["?dataset=7&view=overview&discrepancy=original", "case"],
  ["?dataset=7&view=unknown&kind=missing", "overview"],
])("resolves compatible view state for %s", (search, view) => expect(investigateView(search)).toBe(view));

it("preserves filter and unrelated URL context, removing selected case and transaction IDs when leaving detail", () => {
  const value = investigateSearch("?dataset=7&kind=missing&page=3&discrepancy=old&job=2&keep=yes", "overview");
  const q = new URLSearchParams(value); expect(q.get("view")).toBe("overview"); expect(q.get("page")).toBe("3"); expect(q.get("kind")).toBe("missing"); expect(q.get("keep")).toBe("yes"); expect(q.has("discrepancy")).toBe(false); expect(q.has("job")).toBe(false);
});

it("uses server totals rather than response-page length, keeps units honest and performs only five bounded summary GETs", async () => {
  mount(); await loaded();
  const metrics = screen.getByText("Flights", {exact: true}).closest("dl")!;
  expect(within(metrics).getByText("6", {exact: true})).toBeInTheDocument();
  expect(within(metrics).getByText("37", {exact: true})).toBeInTheDocument(); expect(within(metrics).getByText("19", {exact: true})).toBeInTheDocument();
  expect(screen.getByText(/could not be grouped/)).toBeInTheDocument(); expect(screen.getByText("Counts refer to cases. Categories can overlap.")).toBeInTheDocument();
  expect(screen.queryByRole("heading", {name: "Cases"})).not.toBeInTheDocument();
  const calls = vi.mocked(fetch).mock.calls; expect(calls).toHaveLength(6);
  expect(calls.every(([, options]) => !options?.method || options.method === "GET")).toBe(true);
  expect(calls.filter(([url]) => String(url).includes("/discrepancies?")).every(([url]) => String(url).includes("page_size=1"))).toBe(true);
  expect(calls.some(([url]) => /investigations|\/review|observations|exports/.test(String(url)))).toBe(false);
  expect(screen.queryByText(/reviewed cases|completion percentage|remaining cases/i)).not.toBeInTheDocument();
});

it("keeps overview counts unfiltered and supports cases, back/forward, category links and original records", async () => {
  const router = mount("/investigate?dataset=7&view=overview&kind=missing&page=3&keep=yes"); await loaded();
  expect(vi.mocked(fetch).mock.calls.some(([u]) => String(u).includes("kind=all&page=1&page_size=1"))).toBe(true);
  fireEvent.click(screen.getByRole("link", {name: "Review cases"}));
  await screen.findByRole("heading", {name: "Cases"}); expect(router.state.location.search).toContain("view=table"); expect(router.state.location.search).toContain("kind=attention"); expect(router.state.location.search).toContain("page=1"); expect(router.state.location.search).toContain("keep=yes");
  await act(async () => {await router.navigate(-1);}); await loaded();
  await act(async () => {await router.navigate(1);}); await screen.findByRole("heading", {name: "Cases"});
  fireEvent.click(within(screen.getByRole("navigation", {name: "Dataset views"})).getByRole("link", {name: "Overview"})); await loaded();
  expect(screen.getAllByRole("link", {name: "All source records"}).every(a => a.getAttribute("href") === "/datasets?dataset=7&view=records")).toBe(true);
  fireEvent.click(screen.getByRole("link", {name: "Different reported times"})); await screen.findByRole("heading", {name: "Cases"}); expect(router.state.location.search).toContain("kind=conflict");
});

it("shows partial failure as unavailable and retries only that count", async () => {
  let failed = true;
  custom = url => url.searchParams.get("kind") === "missing" && failed ? response({detail: "Projection temporarily unavailable."},503) : null;
  mount(); await loaded(); expect(screen.getByRole("alert")).toHaveTextContent("Projection temporarily unavailable");
  expect(within(screen.getByText("Missing or unavailable information").closest("div")!).getByText("Unavailable")).toBeInTheDocument();
  const before = vi.mocked(fetch).mock.calls.length; failed = false; fireEvent.click(screen.getByRole("button", {name: "Retry missing or unavailable information"}));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument()); expect(vi.mocked(fetch).mock.calls).toHaveLength(before + 1);
});

it.each([-1, 1.5, 25])("refuses to derive a flight count from inconsistent total %s", async total => {
  custom = url => url.searchParams.get("kind") === "all" ? response(count(url,total)) : null;
  mount(); await screen.findByRole("alert"); expect(within(screen.getByText("Flights", {exact:true}).parentElement!).getByText("Unavailable")).toBeInTheDocument();
});

it("renders a truthful zero-case state without describing source values as correct", async () => {
  custom = url => url.pathname.endsWith("/discrepancies") ? response({...count(url,0),ungroupable_observation_count:37}) : null;
  mount(); await screen.findByText(/No grouped flight\/field cases/); expect(screen.getByText(/does not establish that every reported value is correct/)).toBeInTheDocument();
  expect(screen.getByRole("link", {name: "Explore cases"})).toHaveAttribute("href", expect.stringContaining("kind=all"));
});

it("bounds summary concurrency at two and aborts obsolete reads on dataset replacement", async () => {
  let active = 0, peak = 0; const release: (() => void)[] = []; const signals: AbortSignal[] = [];
  custom = async (url, options) => {
    if (!url.pathname.endsWith("/discrepancies")) return null;
    active++; peak=Math.max(peak,active); signals.push(options!.signal!);
    await new Promise<void>(resolve => release.push(resolve)); active--; return response(count(url));
  };
  const router = mount(); await waitFor(() => expect(release).toHaveLength(2)); expect(peak).toBe(2);
  await act(async () => {await router.navigate("/investigate?dataset=bad");}); expect(signals.every(s => s.aborted)).toBe(true);
  await act(async () => {release.forEach(r=>r());}); expect(release).toHaveLength(2);
  expect(screen.queryByText("reports.csv")).not.toBeInTheDocument();
});
