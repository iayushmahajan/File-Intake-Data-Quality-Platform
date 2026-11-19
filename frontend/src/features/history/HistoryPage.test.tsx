import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { applicationRoutes } from "../../routes";
import evidence from "../../../scripts/fixtures/investigation.json";
import { type ReviewedExport } from "./contracts";
const digest = `sha256:${"b".repeat(64)}`;
const job = {id: 7, job_kind: "raha_flights_v1", contract_version: 1, status: "completed", filename_original: "synthetic.csv", created_at: "2026-01-01", processed_at: "2026-01-01", observation_count: 7, file_size: 100, input_sha256: "a".repeat(64), attempts: 1, duration_ms: 1, issues: [], error_message: null};
const id = evidence.discrepancy_id;
const exported = (request_id = "request-export-1"): ReviewedExport => ({id: "c".repeat(32), request_id, job_id: 7, snapshot_digest: digest, input_sha256: "a".repeat(64), policy_version: "flight_reviewed_export_v1", created_at: "2026-01-01", artifacts: {reviewed: {sha256: "d".repeat(64), bytes: 3}, exceptions: {sha256: "e".repeat(64), bytes: 3}, provenance: {sha256: "f".repeat(64), bytes: 3}}});
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {"Content-Type": "application/json"}});
let entries: ReviewedExport[]; let total: number;
let custom: ((url: URL, options?: RequestInit) => Response | null | Promise<Response | null>) | null;
let routers: ReturnType<typeof createMemoryRouter>[] = [];
function mount(url = "/history?dataset=7") {const router = createMemoryRouter(applicationRoutes, {initialEntries: [url], future: {v7_relativeSplatPath: true}}); routers.push(router); return {router, ...render(<RouterProvider router={router} future={{v7_startTransition: true}} />)};}
const posts = () => vi.mocked(fetch).mock.calls.filter(([, options]) => options?.method === "POST");
beforeEach(() => {
  entries = []; total = 31; custom = null;
  vi.stubGlobal("matchMedia", vi.fn(() => ({matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn()})));
  vi.stubGlobal("scrollTo", vi.fn()); Element.prototype.scrollIntoView = vi.fn();
  URL.createObjectURL = vi.fn(() => "blob:synthetic-export"); URL.revokeObjectURL = vi.fn(); vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  vi.stubGlobal("fetch", vi.fn(async (input: string, options?: RequestInit) => {
    const url = new URL(input); const response = await custom?.(url, options); if (response) return response;
    if (url.pathname === "/api/v1/flights/jobs") return json({jobs: [job], total, page: Number(url.searchParams.get("page")), page_size: 15});
    if (url.pathname.endsWith("/snapshot")) return json({job_id: 7, snapshot_digest: digest, field_count: 4, ungroupable_observation_count: 1});
    if (url.pathname.includes("/download/")) return new Response("abc");
    if (url.pathname.endsWith("/exports")) {
      if (options?.method === "POST") {const item = exported(JSON.parse(options.body as string).request_id); entries.unshift(item); return json(item);}
      return json({exports: entries, total: entries.length, page: Number(url.searchParams.get("page")), page_size: 5});
    }
    if (url.pathname.endsWith("/discrepancies")) return json({job_id: 7, discrepancies: [evidence], total: 1, page: Number(url.searchParams.get("page")), page_size: 15, ungroupable_observation_count: 1});
    if (url.pathname.endsWith("/review/history")) return json({events: [], total: 0, page: 1, page_size: 5});
    if (url.pathname.endsWith("/review")) return json({job_id: 7, discrepancy_id: id, evidence_digest: evidence.evidence_digest, state: "unreviewed", stale: false, revision: 0, decision: null, resolution: null, reviewer_identity_verified: false});
    return json(job);
  }));
});
afterEach(() => {routers.forEach(r => r.dispose()); routers = []; vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); Reflect.deleteProperty(Element.prototype, "scrollIntoView");});
async function ready() {await screen.findByText(/Current snapshot: 4 fields/);}
function acknowledge() {fireEvent.click(screen.getByRole("checkbox", {name: /I understand/}));}
it("loads bounded Flights history, filters and paginates using URLs", async () => {
  const {router} = mount("/history"); await screen.findByRole("button", {name: "#7 · synthetic.csv"});
  expect(screen.getByRole("button", {name: "Previous imports"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button", {name: "Next imports"})); await screen.findByText("Page 2 · 31 imports");
  fireEvent.change(screen.getByLabelText("Processing status"), {target: {value: "failed"}}); await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("page=1&page_size=15&status=failed"), expect.anything()));
  fireEvent.click(screen.getByRole("button", {name: "#7 · synthetic.csv"})); await ready(); expect(router.state.location.search).toContain("dataset=7");
});
it("distinguishes loading, empty history and absence of benchmark claims", async () => {
  custom = url => url.pathname === "/api/v1/flights/jobs" ? json({jobs: [], total: 0, page: 1, page_size: 15}) : null;
  mount("/history"); expect(screen.getByRole("status")).toHaveTextContent("Loading Flights"); await screen.findByText(/No datasets yet/);
  expect(screen.queryByText(/accuracy|precision|F1/i)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", {name: "Previous imports"})).not.toBeInTheDocument();
  expect(screen.queryByRole("button", {name: "Next imports"})).not.toBeInTheDocument();
  expect(posts()).toHaveLength(0);
});
it.each([401, 403, 404, 429, 503])("does not turn HTTP %s into empty history", async status => {
  custom = url => url.pathname === "/api/v1/flights/jobs" ? json({detail: `History unavailable ${status}`}, status) : null;
  mount("/history"); expect(await screen.findByRole("alert")).toHaveTextContent(`History unavailable ${status}`); expect(screen.queryByText(/No datasets yet/)).not.toBeInTheDocument();
});
it("handles network errors, malformed responses and invalid dataset IDs", async () => {
  custom = url => {if (url.pathname === "/api/v1/flights/jobs") throw new TypeError("offline"); return null;}; mount("/history?dataset=bad&job=1");
  await screen.findByText(/backend could not be reached/); expect(screen.getByText(/Invalid dataset identifier/)).toBeInTheDocument();
  custom = url => url.pathname === "/api/v1/flights/jobs" ? json({jobs: "not a list"}) : null;
  fireEvent.click(screen.getByRole("button", {name: "Refresh imports"})); await screen.findByText("Inconsistent Flights history response.");
});
it.each(["pending", "queued", "processing", "failed"])("shows %s as an import state without creating exports", async status => {
  custom = url => /\/jobs\/7$/.test(url.pathname) ? json({...job, status, error_message: status === "failed" ? "Invalid observation IDs." : null}) : null;
  mount(); await screen.findByText("Review and export creation require a completed import."); expect(screen.queryByRole("button", {name: "Create frozen export"})).not.toBeInTheDocument(); expect(posts()).toHaveLength(0);
});
it("requires explicit acknowledgement and submits a snapshot digest/request ID", async () => {
  mount(); await ready(); const button = screen.getByRole("button", {name: "Create frozen export"}); expect(button).toBeDisabled(); expect(posts()).toHaveLength(0);
  acknowledge(); fireEvent.click(button); fireEvent.click(button); await screen.findByText(/server recorded a frozen export/); expect(posts()).toHaveLength(1);
  expect(JSON.parse(posts()[0][1]!.body as string)).toEqual({expected_snapshot_digest: digest, request_id: expect.any(String)});
  expect(await screen.findByText("1 frozen exports · Page 1")).toBeInTheDocument();
});
it("retries an uncertain export with the exact same payload and disables acknowledgement changes", async () => {
  let count = 0; custom = (url, options) => {if (url.pathname.endsWith("/exports") && options?.method === "POST" && ++count === 1) throw new TypeError("offline"); return null;};
  mount(); await ready(); acknowledge(); fireEvent.click(screen.getByRole("button", {name: "Create frozen export"})); await screen.findByText(/outcome is uncertain/); expect(screen.getByRole("checkbox")).toBeDisabled();
  fireEvent.click(screen.getByRole("button", {name: "Retry exact export request"})); await screen.findByText(/server recorded a frozen export/); expect(posts()[0][1]!.body).toBe(posts()[1][1]!.body);
});
it("refreshes a stale snapshot without resubmitting and requires fresh acknowledgement", async () => {
  custom = (url, options) => url.pathname.endsWith("/exports") && options?.method === "POST" ? json({detail: "Reviews changed during export generation."}, 409) : null;
  mount(); await ready(); acknowledge(); fireEvent.click(screen.getByRole("button", {name: "Create frozen export"})); await screen.findByText(/acknowledge again/); await ready();
  expect(screen.getByRole("checkbox")).not.toBeChecked(); expect(screen.getByRole("button", {name: "Create frozen export"})).toBeDisabled(); expect(posts()).toHaveLength(1);
});
it("keeps failed creation separate from success and permits existing export access when snapshot is unavailable", async () => {
  entries = [exported()]; custom = url => url.pathname.endsWith("/snapshot") ? json({detail: "Snapshot exceeds projection ceiling."}, 409) : null;
  mount(); await screen.findByRole("button", {name: "Reviewed CSV"}); await screen.findByText(/Snapshot exceeds projection ceiling/); expect(screen.getByRole("button", {name: "Create frozen export"})).toBeDisabled();
});
it("paginates immutable exports and exposes full provenance through disclosure", async () => {
  entries = [exported()]; custom = url => url.pathname.endsWith("/exports") ? json({exports: entries, total: 6, page: Number(url.searchParams.get("page")), page_size: 5}) : null;
  mount(); await ready(); fireEvent.click(screen.getByRole("button", {name: "Next exports"})); await screen.findByText("6 frozen exports · Page 2"); expect(fetch).toHaveBeenCalledWith(expect.stringContaining("exports?page=2&page_size=5"), expect.anything());
  fireEvent.click(screen.getByText("Inspect export 1 metadata")); expect(screen.getByText("c".repeat(32))).toBeInTheDocument();
});
it.each(["Reviewed CSV", "Exceptions CSV", "Provenance JSON"])("downloads %s using backend URLs without POST or regeneration", async label => {
  entries = [exported()]; mount(); await ready(); fireEvent.click(screen.getByRole("button", {name: label})); await screen.findByText(/download prepared/);
  expect(URL.createObjectURL).toHaveBeenCalled(); expect(HTMLAnchorElement.prototype.click).toHaveBeenCalled(); expect(posts()).toHaveLength(0);
});
it.each([404, 409, 503])("handles artifact HTTP %s without claiming a download", async status => {
  entries = [exported()]; custom = url => url.pathname.includes("/download/") ? json({detail: "Artifact unavailable or corrupt."}, status) : null;
  mount(); await ready(); fireEvent.click(screen.getByRole("button", {name: "Reviewed CSV"})); await screen.findByText("Artifact unavailable or corrupt."); expect(URL.createObjectURL).not.toHaveBeenCalled();
});
it("rejects inconsistent artifact bytes and traversal metadata", async () => {
  entries = [exported()]; custom = url => url.pathname.includes("/download/") ? new Response("wrong bytes") : null;
  mount(); await ready(); fireEvent.click(screen.getByRole("button", {name: "Reviewed CSV"})); await screen.findByText(/Artifact size differs/); expect(URL.createObjectURL).not.toHaveBeenCalled();
  entries = [{...exported(), id: "../private"}]; fireEvent.click(screen.getByRole("button", {name: "Refresh export state"})); await screen.findByText(/Inconsistent export metadata/);
});
it("retrieves one selected field's current review and superseded history", async () => {
  const event = {id: "event-old", job_id: 7, discrepancy_id: id, action: "unresolved", revision: 1, resolution: null, reviewer_label: "Local analyst", rationale: "Previous uncertainty", created_at: "2026-01-01", evidence_digest: evidence.evidence_digest, candidate_id: null, investigation_id: null, manual_value: null};
  custom = url => url.pathname.endsWith("/review/history") ? json({events: [event], total: 1, page: 1, page_size: 5}) : url.pathname.endsWith("/review") ? json({job_id: 7, discrepancy_id: id, state: "overridden", stale: false, revision: 2, evidence_digest: evidence.evidence_digest, decision: {...event, id: "current"}, resolution: {canonical_clock: "14:40"}}) : null;
  const {router} = mount(`/history?dataset=7&discrepancy=${id}`); await screen.findByText("Superseded event"); expect(screen.getByText("overridden")).toBeInTheDocument(); expect(screen.getByText("Revision 2 · 14:40")).toBeInTheDocument();
  expect(screen.getByRole("link", {name: "Inspect evidence or revise this field"})).toHaveAttribute("href", `/investigate?dataset=7&discrepancy=${id}`);
  expect(router.state.location.search).toContain(id);
});
it("aborts abandoned dataset requests and does not display stale responses", async () => {
  let signal: AbortSignal | null | undefined;
  custom = (url, options) => /\/jobs\/7$/.test(url.pathname) ? new Promise((_resolve, reject) => {signal = options?.signal; signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));}) : null;
  const {unmount} = mount(); await waitFor(() => expect(signal).toBeDefined()); unmount(); expect(signal?.aborted).toBe(true);
});
it("does not label a newly arrived concurrent revision as superseded", async () => {
  custom = url => url.pathname.endsWith('/review/history') ? json({events: [{id: 'new', job_id: 7, discrepancy_id: id, action: 'unresolved', revision: 2, resolution: null, reviewer_label: 'Local analyst', rationale: '', created_at: '2026-01-01', manual_value: null}], total: 1, page: 1, page_size: 5}) : null;
  mount(`/history?dataset=7&discrepancy=${id}`); await screen.findByText('Newer event · refresh review'); expect(screen.queryByText('Superseded event')).not.toBeInTheDocument();
});
