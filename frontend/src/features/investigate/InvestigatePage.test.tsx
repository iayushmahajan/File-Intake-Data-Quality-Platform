import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { applicationRoutes } from "../../routes";
import fixture from "../../../scripts/fixtures/investigation.json";
import { type Decision, type Evidence, type Investigation, type LatestAI, type Review, type ReviewRequest, currentProposal } from "./contracts";
const evidence = fixture as unknown as Evidence;
const id = evidence.discrepancy_id;
const path = `/investigate?dataset=7&discrepancy=${id}`;
const summary = {...evidence, candidate_count: evidence.candidates.length};
const second = {...evidence, discrepancy_id: "second-discrepancy", flight: "ZZ-2-CCC-DDD", evidence_digest: `sha256:${"b".repeat(64)}`};
const job = {id: 7, job_kind: "raha_flights_v1", contract_version: 1, status: "completed", filename_original: "synthetic-flights.csv", observation_count: 26, issues: []};
const emptyReview = (): Review => ({job_id: 7, discrepancy_id: id, evidence_digest: evidence.evidence_digest, state: "unreviewed", stale: false, revision: 0, decision: null, resolution: null, reviewer_identity_verified: false});
const proposal = (status: Investigation["status"] = "proposed"): Investigation => ({id: "investigation-1", request_id: "test-request-1", job_id: 7, discrepancy_id: id, evidence_digest: evidence.evidence_digest, status, stored_status: status, current: status !== "stale", authoritative: false,
  recommendation: status === "proposed" || status === "stale" ? {recommendation: "propose", candidate_id: evidence.candidates[0].candidate_id, supporting_claim_ids: ["claim-one"], contradicting_claim_ids: ["claim-two"], explanation: "Synthetic model explanation, not ground truth.", uncertainty: "Sources may share errors."} : status === "abstained" ? {recommendation: "abstain", candidate_id: null, supporting_claim_ids: [], contradicting_claim_ids: [], explanation: "The supplied evidence is insufficient.", uncertainty: "No reliable distinction."} : null,
  claim_references: [{claim_id: "claim-one", observation_id: "synthetic-0", source_id: "source-0"}, {claim_id: "claim-two", observation_id: "synthetic-2", source_id: "source-2"}], provider: "synthetic-provider", model: "synthetic-model", resolved_model: null, usage: {total_tokens: 80}, error_code: status === "unavailable" ? "unconfigured" : status === "invalid_response" ? "invalid_response" : status === "failed" ? "provider_timeout" : null,
  policy_version: "flight_investigation_v1", prompt_version: "flight_investigation_prompt_v1", schema_version: "flight_recommendation_v1", created_at: "2026-01-01", completed_at: "2026-01-01"});
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {"Content-Type": "application/json"}});
let current: Review; let ai: LatestAI; let events: Decision[];
let custom: ((url: URL, options?: RequestInit) => Promise<Response | null> | Response | null) | null;
let routers: ReturnType<typeof createMemoryRouter>[] = [];
function mount(url = path) {
  const router = createMemoryRouter(applicationRoutes, {initialEntries: [url], future: {v7_relativeSplatPath: true}}); routers.push(router);
  return {router, ...render(<RouterProvider router={router} future={{v7_startTransition: true}} />)};
}
const postCalls = (suffix: string) => vi.mocked(fetch).mock.calls.filter(([url, options]) => String(url).endsWith(suffix) && options?.method === "POST");
function record(body: ReviewRequest): Decision {
  const c = evidence.candidates.find(c => c.candidate_id === body.candidate_id) ?? evidence.candidates[0];
  return {id: `decision-${events.length + 1}`, request_id: body.request_id, job_id: 7, discrepancy_id: id, flight: evidence.flight, field: evidence.field, evidence_digest: evidence.evidence_digest, revision: current.revision + 1, action: body.action,
    candidate_id: body.action === "unresolved" || body.manual_value ? null : c.candidate_id, investigation_id: body.investigation_id ?? null, manual_value: body.manual_value ?? null,
    resolution: body.action === "accept" || body.action === "override" ? {origin: body.manual_value ? "human_assertion" : "observed_candidate", canonical_clock: body.manual_value ? "14:40" : c.canonical_clock, precision: "minute", qualifiers: [], supporting_observation_ids: body.manual_value ? [] : c.supporting_observation_ids, supporting_source_ids: body.manual_value ? [] : c.supporting_source_ids} : null,
    rationale: body.rationale, reviewer_label: body.reviewer_label, created_at: "2026-01-01"};
}
beforeEach(() => {
  current = emptyReview(); ai = {status: "not_requested", investigation: null}; events = []; custom = null;
  vi.stubGlobal("matchMedia", vi.fn(() => ({matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn()})));
  vi.stubGlobal("scrollTo", vi.fn()); Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (input: string, options?: RequestInit) => {
    const url = new URL(input); const intercepted = await custom?.(url, options); if (intercepted) return intercepted;
    if (url.pathname === "/api/v1/flights/jobs") return json({jobs: [job], total: 1, page: 1, page_size: 15});
    if (url.pathname.endsWith("/exports/snapshot")) return json({job_id: 7, snapshot_digest: evidence.evidence_digest, field_count: 40, ungroupable_observation_count: 1});
    if (url.pathname.endsWith("/exports")) return json({exports: [], total: 0, page: 1, page_size: 5});
    if (/\/jobs\/7$/.test(url.pathname)) return json(job);
    if (/\/discrepancies$/.test(url.pathname) && url.searchParams.get("page_size") === "1") return json({job_id: 7, discrepancies: [summary], total: url.searchParams.get("kind") === "all" ? 40 : 31, page: 1, page_size: 1, ungroupable_observation_count: 1});
    if (/\/discrepancies$/.test(url.pathname)) return json({job_id: 7, discrepancies: [summary, {...summary, ...second, candidate_count: 2}], total: 31, page: Number(url.searchParams.get("page")), page_size: 15, ungroupable_observation_count: 1, raw_observations_url: "unused"});
    if (url.pathname.endsWith("/review/history")) return json({events, total: events.length, page: Number(url.searchParams.get("page")), page_size: 5});
    if (url.pathname.endsWith("/review")) {
      if (options?.method === "POST") {
        const body = JSON.parse(options.body as string) as ReviewRequest; const event = record(body); events.push(event);
        current = {...current, revision: event.revision, state: ({accept: "accepted", override: "overridden", reject: "rejected", unresolved: "unresolved"} as const)[body.action], decision: event, resolution: event.resolution};
        return json(event);
      }
      return json(current);
    }
    if (url.pathname.endsWith("/investigations")) {
      if (options?.method === "POST") {ai = {status: "proposed", investigation: proposal()}; return json(ai.investigation);}
      return json(ai);
    }
    if (url.pathname.includes("/investigations/")) return json(ai.investigation);
    return json(url.pathname.endsWith("second-discrepancy") ? second : evidence);
  }));
});
afterEach(() => {routers.forEach(r => r.dispose()); routers = []; vi.useRealTimers(); vi.unstubAllGlobals(); Reflect.deleteProperty(Element.prototype, "scrollIntoView");});
function closeDetails() {
  const button = screen.queryByRole("button", {name: "Close details"}); if (button) fireEvent.click(button);
  const keep = screen.queryByRole("button", {name: "Keep draft and view case"}); if (keep) fireEvent.click(keep);
}
function openControls() {
  if (screen.queryByRole("heading", {name: "Record your review"})) return;
  closeDetails(); const node = screen.queryByRole("button", {name: /^(Record a review|Resume review)$/}); if (node) fireEvent.click(node);
}
function openAI() { closeDetails(); fireEvent.click(screen.getByRole("button", {name: "View AI assessment"})); }
function openReviewDetails() { closeDetails(); fireEvent.click(screen.getByRole("button", {name: "View review details"})); }
function openSources() { closeDetails(); fireEvent.click(screen.getByRole("button", {name: /View source records/})); }
function aiButton() { closeDetails(); return screen.getByRole("button", {name: "Investigate with AI"}); }
async function modelExplanation() { openAI(); await screen.findByText(/Synthetic model explanation/); closeDetails(); }
async function ready() {await screen.findByText("Your review", {selector: "h3"}); openControls(); await waitFor(() => expect(screen.getByRole("button", {name: "Save review"})).toBeEnabled());}
function reviewer() {openControls(); fireEvent.change(screen.getByLabelText(/Reviewer name or label/), {target: {value: "Local analyst"}});}
function rationale() {openControls(); fireEvent.change(screen.getByLabelText(/Rationale/), {target: {value: "Reviewed the source evidence."}});}

it("opens missing/invalid context without fetching and accepts a durable Flights import ID", async () => {
  const {router} = mount("/investigate?dataset=bad&job=1");
  expect(screen.getByRole("alert")).toHaveTextContent("identifier is invalid"); expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Flights import number"), {target: {value: "7"}});
  fireEvent.click(screen.getByRole("button", {name: "Open investigation workspace"}));
  await screen.findByRole("heading", {name: "Flights dataset"}); expect(router.state.location.search).toBe("?dataset=7");
});
it.each(["pending", "queued", "processing", "failed"])("does not request a discrepancy queue for a %s dataset", async status => {
  custom = url => /\/jobs\/7$/.test(url.pathname) ? json({...job, status, error_message: status === "failed" ? "Import validation failed." : null}) : null;
  mount(); await screen.findByRole("heading", {name: status === "failed" ? "This import failed." : "The dataset is not ready for investigation."});
  expect(vi.mocked(fetch).mock.calls).toHaveLength(1);
});
it.each([404, 409, 503])("shows dataset HTTP %s as an error, never an empty queue", async status => {
  custom = url => /\/jobs\/7$/.test(url.pathname) ? json({detail: "Dataset unavailable or unsupported."}, status) : null;
  mount(); expect(await screen.findByRole("alert")).toHaveTextContent("Dataset unavailable"); expect(screen.queryByText(/No fields match/)).not.toBeInTheDocument();
});
it("paginates/filters on the server, selects in the URL and supports back/forward", async () => {
  const {router} = mount("/investigate?dataset=7&view=table");
  await screen.findByRole("heading", {name: "Cases"}); await screen.findByText("Page 1 · 31 matching cases");
  fireEvent.change(screen.getByLabelText("Finding"), {target: {value: "conflict"}});
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("kind=conflict&page=1&page_size=15"), expect.anything()));
  fireEvent.change(screen.getByLabelText("Time field"), {target: {value: "act_arr_time"}});
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("field=act_arr_time"), expect.anything()));
  fireEvent.click(screen.getByRole("button", {name: "Next cases"})); await screen.findByText("Page 2 · 31 matching cases");
  fireEvent.click(within(screen.getByRole("table", {name: "Cases"})).getByRole("link", {name: /Open case for ZZ-1/})); await ready();
  expect(router.state.location.search).toContain(`discrepancy=${id}`);
  await act(async () => {await router.navigate(-1);}); expect(screen.queryByRole("button", {name: "Save review"})).not.toBeInTheDocument();
  await act(async () => {await router.navigate(1);}); await ready();
});
it.each([false, true])("distinguishes a filtered empty queue from request failure (%s)", async fail => {
  custom = url => url.pathname.endsWith("/discrepancies") ? fail ? json({detail: "Projection ceiling exceeded."}, 409) : json({job_id: 7, discrepancies: [], total: 0, page: 1, page_size: 15, ungroupable_observation_count: 0}) : null;
  mount("/investigate?dataset=7&view=table");
  if (fail) expect(await screen.findByRole("alert")).toHaveTextContent("Projection ceiling exceeded"); else await screen.findByText(/No cases match these filters/);
});
it("renders raw source strings, equivalent candidates, all uncertainty statuses and provenance safely", async () => {
  mount(); await ready();
  openSources();
  const table = screen.getByRole("region", {name: "Source evidence table"});
  expect(within(table).getByText(evidence.claims[6].normalization.raw, {exact: true})).toBeInTheDocument();
  expect(table.querySelector("img")).toBeNull();
  for (const status of ["parsed", "ambiguous", "missing", "placeholder", "unsupported"]) expect(within(table).getAllByText(status).length).toBeGreaterThan(0);
  expect(screen.getAllByText("09:22 AM").length).toBeGreaterThan(0);
  expect(evidence.candidates).toHaveLength(2);
  expect(screen.getByText(/Sources disagree/)).toBeInTheDocument();
  expect(screen.getByText("Equivalent formatting")).toBeInTheDocument();
  closeDetails(); fireEvent.click(screen.getAllByRole("button", {name: /View supporting reports/})[0]);
  expect(screen.getAllByText(/synthetic-0/).length).toBeGreaterThan(0);
});
it("does not post AI or review on load and provides human review without configured AI", async () => {
  ai = {status: "unavailable", investigation: proposal("unavailable")}; mount(); await ready();
  expect(postCalls("/investigations")).toHaveLength(0); expect(postCalls("/review")).toHaveLength(0);
  expect(screen.queryByRole("option", {name: "Accept current AI proposal"})).not.toBeInTheDocument();
  reviewer(); fireEvent.click(screen.getByRole("button", {name: "Save review"}));
  await screen.findByText(/Review saved/); expect(events[0].action).toBe("unresolved"); expect(events[0].candidate_id).toBeNull();
});
it("requests AI explicitly with a digest/request ID, then accepts only the current proposal", async () => {
  mount(); await ready(); fireEvent.click(aiButton());
  await modelExplanation();
  const body = JSON.parse(postCalls("/investigations")[0][1]!.body as string);
  expect(body).toEqual({expected_evidence_digest: evidence.evidence_digest, request_id: expect.any(String)});
  openAI(); expect(screen.getByText(/Observation synthetic-0 · Source source-0/)).toBeInTheDocument();
  closeDetails(); openControls(); fireEvent.change(screen.getByLabelText("Review action"), {target: {value: "accept"}}); reviewer(); fireEvent.click(screen.getByRole("button", {name: "Save review"}));
  await screen.findByText(/Review saved/);
  const decision = JSON.parse(postCalls("/review")[0][1]!.body as string);
  expect(decision).toMatchObject({action: "accept", investigation_id: "investigation-1", expected_revision: 0, expected_evidence_digest: evidence.evidence_digest}); expect(decision).not.toHaveProperty("candidate_id");
  openReviewDetails(); await waitFor(() => expect(screen.getByText(/Server revision 1/)).toBeInTheDocument());
});
it.each(["abstained", "unavailable", "invalid_response", "failed", "stale", "ineligible"] as const)("keeps AI %s distinct and prevents accepting it", async status => {
  ai = {status, investigation: proposal(status)}; mount(); await ready();
  expect(screen.queryByRole("option", {name: "Accept current AI proposal"})).not.toBeInTheDocument();
  expect(screen.getAllByText(status.replace(/_/g, " ")).length).toBeGreaterThan(0);
  if (status === "abstained") expect(screen.getByText(/Not enough evidence to suggest a value/)).toBeInTheDocument();
});
it("polls a running investigation with GET only and stops at completion", async () => {
  vi.useFakeTimers(); ai = {status: "running", investigation: proposal("running")}; mount(); await act(async () => {}); openControls();
  expect(aiButton()).toBeDisabled();
  ai = {status: "proposed", investigation: proposal()}; await act(async () => {await vi.advanceTimersByTimeAsync(2000);});
  openAI(); expect(screen.getByText(/Synthetic model explanation/)).toBeInTheDocument(); closeDetails();
  const count = vi.mocked(fetch).mock.calls.length; await act(async () => {await vi.advanceTimersByTimeAsync(10000);}); expect(vi.mocked(fetch).mock.calls).toHaveLength(count); expect(postCalls("/investigations")).toHaveLength(0);
});
it.each(["candidate", "manual"])("submits a %s override with provenance and re-review revision", async origin => {
  current = {...current, revision: 2, state: "unresolved"}; ai = {status: "abstained", investigation: proposal("abstained")}; mount(); await ready();
  fireEvent.change(screen.getByLabelText("Review action"), {target: {value: "override"}}); reviewer(); rationale();
  if (origin === "manual") {fireEvent.change(screen.getByLabelText("Replacement origin"), {target: {value: "manual"}}); fireEvent.change(screen.getByLabelText("Manual clock"), {target: {value: " 2:40 p.m. "}});}
  else fireEvent.change(screen.getByLabelText("Supported candidate"), {target: {value: evidence.candidates[1].candidate_id}});
  fireEvent.click(screen.getByRole("button", {name: "Save review"})); await screen.findByText(/Review saved/);
  const sent = JSON.parse(postCalls("/review")[0][1]!.body as string);
  expect(sent).toMatchObject({action: "override", expected_revision: 2, rationale: "Reviewed the source evidence."}); expect(sent).not.toHaveProperty("investigation_id");
  if (origin === "manual") expect(sent.manual_value).toBe(" 2:40 p.m. "); else expect(sent.candidate_id).toBe(evidence.candidates[1].candidate_id);
  openReviewDetails(); await waitFor(() => expect(screen.getByText(/Server revision 3/)).toBeInTheDocument()); closeDetails(); fireEvent.click(screen.getByRole("button", {name: "View review history (1)"})); expect(screen.getByText(/Revision 3 · override/)).toBeInTheDocument();
});
it("rejects a proposal without showing an approved value", async () => {
  ai = {status: "proposed", investigation: proposal()}; mount(); await ready(); reviewer(); fireEvent.change(screen.getByLabelText("Review action"), {target: {value: "reject"}}); rationale();
  fireEvent.click(screen.getByRole("button", {name: "Save review"})); await screen.findByText(/Review saved/); expect(events[0].resolution).toBeNull(); await screen.findByText(/No current approved value/);
});
it("keeps a rejected ambiguous manual clock and server validation message for correction", async () => {
  custom = (url, options) => options?.method === "POST" && url.pathname.endsWith("/review") ? json({detail: "Manual replacement requires an explicit supported clock under normalization v1."}, 422) : null;
  mount(); await ready(); reviewer(); fireEvent.change(screen.getByLabelText("Review action"), {target: {value: "override"}}); rationale(); fireEvent.change(screen.getByLabelText("Replacement origin"), {target: {value: "manual"}}); fireEvent.change(screen.getByLabelText("Manual clock"), {target: {value: "9:22"}});
  fireEvent.click(screen.getByRole("button", {name: "Save review"})); await screen.findByText(/Manual replacement requires/); expect(screen.getByLabelText("Manual clock")).toHaveValue("9:22"); expect(screen.queryByText(/Review saved/)).not.toBeInTheDocument();
});
it("holds an ambiguous review response for exact same-ID retry without optimistic approval", async () => {
  let attempts = 0;
  custom = (url, options) => {if (options?.method === "POST" && url.pathname.endsWith("/review") && ++attempts === 1) throw new TypeError("disconnected"); return null;};
  mount(); await ready(); reviewer(); fireEvent.click(screen.getByRole("button", {name: "Save review"}));
  await screen.findByText(/outcome is uncertain/); expect(screen.getByLabelText(/Reviewer name or label/)).toBeDisabled(); expect(events).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", {name: "Retry exact review request"})); await screen.findByText(/Review saved/);
  expect(postCalls("/review")[0][1]!.body).toBe(postCalls("/review")[1][1]!.body);
});
it("refreshes after revision conflict without silently resubmitting or clearing rationale", async () => {
  let conflict = true;
  custom = (url, options) => {if (options?.method === "POST" && url.pathname.endsWith("/review") && conflict) {conflict = false; current = {...current, revision: 3}; return json({detail: "Decision revision changed."}, 409);} return null;};
  mount(); await ready(); reviewer(); rationale(); fireEvent.click(screen.getByRole("button", {name: "Save review"}));
  await screen.findByText(/inspect the current state/); await ready(); openReviewDetails(); expect(screen.getByText(/Server revision 3/)).toBeInTheDocument(); closeDetails(); openControls(); expect(screen.getByLabelText(/Rationale/)).toHaveValue("Reviewed the source evidence."); expect(postCalls("/review")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", {name: "Save review"})); await screen.findByText(/Review saved/); expect(JSON.parse(postCalls("/review")[1][1]!.body as string).expected_revision).toBe(3);
});
it("retries uncertain AI with the same ID and blocks duplicate clicks while waiting", async () => {
  let reject!: (error: Error) => void;
  custom = (url, options) => url.pathname.endsWith("/investigations") && options?.method === "POST" ? new Promise((_resolve, fail) => {reject = fail;}) : null;
  mount(); await ready(); const button = aiButton(); fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(postCalls("/investigations")).toHaveLength(1)); await act(async () => reject(new TypeError("disconnected")));
  custom = null; fireEvent.click(screen.getByRole("button", {name: "Retry same AI request"})); await modelExplanation();
  expect(postCalls("/investigations")[0][1]!.body).toBe(postCalls("/investigations")[1][1]!.body);
});
it("shows capacity/stale AI errors truthfully without submitting a review", async () => {
  custom = (url, options) => url.pathname.endsWith("/investigations") && options?.method === "POST" ? json({detail: "AI capacity exhausted. Retry later."}, 429) : null;
  mount(); await ready(); fireEvent.click(aiButton()); await screen.findByText(/capacity exhausted/); expect(postCalls("/review")).toHaveLength(0); openControls(); expect(screen.getByRole("button", {name: "Save review"})).toBeEnabled();
});
it("ignores delayed evidence after selection changes and aborts requests on unmount", async () => {
  let resolve!: (response: Response) => void; let signal: AbortSignal | null | undefined;
  custom = (url, options) => url.pathname.endsWith(id) ? new Promise(done => {resolve = done; signal = options?.signal;}) : null;
  const {router, unmount} = mount(); await waitFor(() => expect(resolve).toBeDefined());
  await act(async () => {await router.navigate("/investigate?dataset=7&discrepancy=second-discrepancy");});
  await screen.findByRole("heading", {name: "Flight ZZ-2-CCC-DDD"}); expect(signal?.aborted).toBe(true);
  await act(async () => resolve(json(evidence))); expect(screen.queryByRole("heading", {name: `Flight ${evidence.flight}`})).not.toBeInTheDocument(); unmount();
});
it("refuses cross-scope or digest-mismatched AI proposals as current", () => {
  const valid = proposal(); expect(currentProposal({status: "proposed", investigation: valid}, evidence)).toEqual(valid);
  for (const change of [{job_id: 8}, {discrepancy_id: "other"}, {evidence_digest: "wrong"}, {current: false}, {recommendation: {...valid.recommendation!, candidate_id: "other-candidate"}}]) expect(currentProposal({status: "proposed", investigation: {...valid, ...change}}, evidence)).toBeNull();
});

it("disables writes when current review cannot be loaded while keeping evidence readable", async () => {
  custom = url => url.pathname.endsWith("/review") ? json({detail: "Review storage unavailable."}, 503) : null;
  mount(); await screen.findByText(/Review storage unavailable/);
  openControls(); openSources(); expect(screen.getByRole("region", {name: "Source evidence table"})).toBeInTheDocument(); closeDetails(); openControls(); expect(screen.getByRole("button", {name: "Save review"})).toBeDisabled();
});
it("handles a corrupt/unknown detail without displaying another field's evidence", async () => {
  custom = url => url.pathname.endsWith(id) ? json({...evidence, job_id: 8}) : null;
  mount(); await screen.findByText(/server returned inconsistent evidence/); expect(screen.queryByRole("region", {name: "Source evidence table"})).not.toBeInTheDocument();
});
it("bounds running GET polling and allows explicit server refresh without another provider call", async () => {
  vi.useFakeTimers(); ai = {status: "running", investigation: proposal("running")}; mount(); await act(async () => {});
  await act(async () => {await vi.advanceTimersByTimeAsync(92000);});
  expect(screen.getByText(/Automatic investigation checks stopped/)).toBeInTheDocument();
  const count = vi.mocked(fetch).mock.calls.length; await act(async () => {await vi.advanceTimersByTimeAsync(20000);}); expect(vi.mocked(fetch).mock.calls).toHaveLength(count); expect(postCalls("/investigations")).toHaveLength(0);
});
it("times out hung read requests and never invents an empty queue", async () => {
  vi.useFakeTimers(); custom = (url, options) => /\/jobs\/7$/.test(url.pathname) ? new Promise((_resolve, reject) => options?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))) : null;
  mount(); await act(async () => {}); await act(async () => {await vi.advanceTimersByTimeAsync(15000);});
  expect(screen.getByRole("alert")).toHaveTextContent("timed out"); expect(screen.queryByRole("heading", {name: "Discrepancy queue"})).not.toBeInTheDocument();
});
it("handles timed out writes as uncertain and retains their request identity", async () => {
  vi.useFakeTimers(); custom = (url, options) => url.pathname.endsWith("/review") && options?.method === "POST" ? new Promise((_resolve, reject) => options.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))) : null;
  mount(); await act(async () => {}); openControls(); reviewer(); fireEvent.click(screen.getByRole("button", {name: "Save review"})); await act(async () => {});
  await act(async () => {await vi.advanceTimersByTimeAsync(45000);});
  expect(screen.getByRole("button", {name: "Retry exact review request"})).toBeEnabled(); expect(events).toHaveLength(0);
  custom = null; fireEvent.click(screen.getByRole("button", {name: "Retry exact review request"})); await act(async () => {});
  expect(postCalls("/review")[0][1]!.body).toBe(postCalls("/review")[1][1]!.body); expect(events).toHaveLength(1);
});
it("refreshes changed evidence after an AI 409 without retrying the provider automatically", async () => {
  let changed = false; const newDigest = `sha256:${"f".repeat(64)}`;
  custom = (url, options) => {
    if (url.pathname.endsWith("/investigations") && options?.method === "POST") {changed = true; return json({detail: "Evidence changed."}, 409);}
    if (changed && url.pathname.endsWith(id)) return json({...evidence, evidence_digest: newDigest});
    if (changed && options?.method !== "POST" && url.pathname.endsWith("/review")) return json({...current, evidence_digest: newDigest});
    return null;
  };
  mount(); await ready(); fireEvent.click(aiButton()); await screen.findByText("Evidence changed."); await ready();
  expect(postCalls("/investigations")).toHaveLength(1); reviewer(); fireEvent.click(screen.getByRole("button", {name: "Save review"})); await screen.findByText(/Review saved/);
  expect(JSON.parse(postCalls("/review")[0][1]!.body as string).expected_evidence_digest).toBe(newDigest);
});
it("displays paginated decision history including superseded events", async () => {
  const historical = record({action: "unresolved", reviewer_label: "Past local analyst", rationale: "Insufficient evidence.", expected_evidence_digest: evidence.evidence_digest, expected_revision: 0, request_id: "historical-request"});
  custom = url => url.pathname.endsWith("/review/history") ? json({events: [historical], total: 8, page: Number(url.searchParams.get("page")), page_size: 5}) : null;
  mount(); await ready(); closeDetails(); fireEvent.click(screen.getByRole("button", {name: "View review history (8)"})); expect(screen.getByText(/Past local analyst/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: "Next history page"})); await screen.findByText("Page 2 · 5 events per page");
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("history?page=2&page_size=5"), expect.anything());
});
it("disables an ineligible agreement case without calling the provider", async () => {
  custom = url => url.pathname.endsWith(id) ? json({...evidence, flags: {...evidence.flags, confirmed_conflict: false, has_ambiguous: false, has_unsupported: false, incomparable_supported_values: false}}) : null;
  mount(); await ready(); expect(aiButton()).toBeDisabled(); expect(screen.getByText(/not eligible for AI investigation/)).toBeInTheDocument(); expect(postCalls("/investigations")).toHaveLength(0);
});
it("protects a pending AI request from navigation and never mixes its output", async () => {
  let resolve!: (response: Response) => void; let signal: AbortSignal | null | undefined;
  custom = (url, options) => url.pathname.endsWith("/investigations") && options?.method === "POST" ? new Promise(done => {resolve = done; signal = options.signal;}) : null;
  const {router} = mount(); await ready(); fireEvent.click(aiButton()); await waitFor(() => expect(resolve).toBeDefined());
  await act(async () => {await router.navigate("/investigate?dataset=7&discrepancy=second-discrepancy");}); await screen.findByRole("dialog"); expect(signal?.aborted).toBe(false);
  expect(screen.queryByRole("button", {name: "Discard changes and leave"})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: "Continue editing"}));
  await act(async () => resolve(json(proposal()))); await modelExplanation();
  await act(async () => {await router.navigate("/investigate?dataset=7&discrepancy=second-discrepancy");});
  await screen.findByRole("heading", {name: `Flight ${second.flight}`}); expect(screen.queryByText(/Synthetic model explanation/)).not.toBeInTheDocument();
});

it("opens a focused case with records, AI controls and the review form collapsed initially", async () => {
  mount(); await screen.findByRole("heading", {name: `Flight ${evidence.flight}`});
  expect(screen.queryByRole("heading", {name: "Discrepancy queue"})).not.toBeInTheDocument();
  expect(screen.getByRole("heading", {name: "Compare reported values"})).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("button", {name: "Record a review"})).toHaveAttribute("aria-haspopup", "dialog");
  expect(postCalls("/investigations")).toHaveLength(0);
});

it("follows filtered server order across both page boundaries and preserves browser/table context", async () => {
  const rows = Array.from({length: 17}, (_, n) => ({...summary, discrepancy_id: n === 14 ? id : `case-${n}`, flight: `ZZ-${n}`}));
  custom = (url, options) => {
    if (url.pathname.endsWith("/discrepancies")) { const page = Number(url.searchParams.get("page")); return json({job_id: 7, discrepancies: rows.slice((page - 1) * 15, page * 15), total: rows.length, page, page_size: 15, ungroupable_observation_count: 0}); }
    const found = rows.find(row => url.pathname.endsWith(`/discrepancies/${row.discrepancy_id}`));
    if (found) return json({...evidence, discrepancy_id: found.discrepancy_id, flight: found.flight});
    const selected = rows.find(row => url.pathname.includes(`/discrepancies/${row.discrepancy_id}/`));
    if (selected && url.pathname.endsWith("/review") && options?.method !== "POST") return json({...current, discrepancy_id: selected.discrepancy_id});
    return null;
  };
  const {router} = mount(`${path}&view=case&kind=conflict&field=act_dep_time&page=1`);
  await screen.findByText("Case 15 of 17 in this selection");
  fireEvent.click(screen.getByRole("button", {name: "Next case"}));
  await screen.findByText("Case 16 of 17 in this selection");
  expect(router.state.location.search).toContain("page=2"); expect(router.state.location.search).toContain("kind=conflict"); expect(router.state.location.search).toContain("field=act_dep_time");
  expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).includes("kind=conflict&page=2&page_size=15"))).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", {name: "Next case"})); await screen.findByText("Case 17 of 17 in this selection"); expect(screen.getByRole("button", {name: "Next case"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button", {name: "Previous case"})); await screen.findByText("Case 16 of 17 in this selection");
  fireEvent.click(screen.getByRole("button", {name: "Previous case"})); await screen.findByText("Case 15 of 17 in this selection");
  await act(async () => { await router.navigate(-1); }); await screen.findByText("Case 16 of 17 in this selection");
  await act(async () => { await router.navigate(1); }); await screen.findByText("Case 15 of 17 in this selection");
  closeDetails(); fireEvent.click(screen.getByRole("link", {name: "Back to cases"})); await screen.findByRole("table", {name: "Cases"});
  expect(router.state.location.search).not.toContain("discrepancy="); expect(router.state.location.search).toContain("kind=conflict"); expect(postCalls("/review")).toHaveLength(0);
});

it("does not invent neighbors for a bookmarked case outside the confirmed page", async () => {
  custom = url => url.pathname.endsWith("/discrepancies") ? json({job_id: 7, discrepancies: [], total: 0, page: 1, page_size: 15, ungroupable_observation_count: 0}) : null;
  mount(); await ready(); closeDetails(); expect(screen.getByRole("button", {name: "Previous case"})).toBeDisabled(); expect(screen.getByRole("button", {name: "Next case"})).toBeDisabled();
  expect(screen.getByText(/Case position unavailable/)).toBeInTheDocument(); expect(screen.getByRole("link", {name: "Back to cases"})).toBeInTheDocument();
});

it("paginates original claims locally without losing raw values or making extra API requests", async () => {
  const claims = Array.from({length: 23}, (_, n) => ({...evidence.claims[0], tuple_id: `record-${n}`, row_number: n + 1, normalization: {...evidence.claims[0].normalization, raw: ` raw ${n}\n `}}));
  custom = url => url.pathname.endsWith(id) ? json({...evidence, claims, observation_count: 23}) : null;
  mount(); await ready(); openSources();
  const count = vi.mocked(fetch).mock.calls.length;
  expect(screen.getByText("Records 1–10 of 23")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: "Next source records"})); expect(screen.getByText("Records 11–20 of 23")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: "Next source records"})); expect(screen.getByText("Records 21–23 of 23")).toBeInTheDocument();
  expect(screen.getByRole("region", {name: "Source evidence table"}).textContent).toContain(" raw 22\n "); expect(fetch).toHaveBeenCalledTimes(count);
});

it.each(["/investigate?dataset=7&view=table", "/investigate?dataset=8", "/history?dataset=7", "/investigate?dataset=7&discrepancy=second-discrepancy"])("protects unfinished review on navigation to %s", async destination => {
  const {router} = mount(); await ready(); reviewer(); rationale();
  const unload = new Event("beforeunload", {cancelable: true}); window.dispatchEvent(unload); expect(unload.defaultPrevented).toBe(true);
  await act(async () => { await router.navigate(destination); });
  expect(await screen.findByRole("dialog")).toHaveTextContent("Leave your unfinished review?");
  fireEvent.click(screen.getByRole("button", {name: "Continue editing"}));
  expect(router.state.location.search).toBe(new URL(`http://test${path}`).search); expect(screen.getByLabelText(/Rationale/)).toHaveValue("Reviewed the source evidence.");
  expect(postCalls("/review")).toHaveLength(0);
  await act(async () => { await router.navigate(destination); }); fireEvent.click(screen.getByRole("button", {name: "Discard changes and leave"}));
  await waitFor(() => expect(router.state.location.pathname + router.state.location.search).toBe(destination));
});

it("protects browser Back and clears the draft guard after a successful review", async () => {
  const {router} = mount("/investigate?dataset=7&view=table"); await screen.findByRole("table", {name: "Cases"});
  fireEvent.click(screen.getByRole("link", {name: /Open case for ZZ-1/})); await ready(); reviewer();
  await act(async () => { await router.navigate(-1); }); await screen.findByRole("dialog"); fireEvent.click(screen.getByRole("button", {name: "Continue editing"}));
  expect(screen.getByLabelText(/Reviewer name or label/)).toHaveValue("Local analyst");
  await waitFor(() => expect(screen.getByRole("dialog")).toContainElement(document.activeElement as HTMLElement));
  fireEvent.click(screen.getByRole("button", {name: "Save review"})); await screen.findByText(/Review saved/); await ready();
  const unload = new Event("beforeunload", {cancelable: true}); window.dispatchEvent(unload); expect(unload.defaultPrevented).toBe(false);
  closeDetails(); fireEvent.click(screen.getByRole("link", {name: "Back to cases"})); await screen.findByRole("table", {name: "Cases"}); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("keeps the first case bounded and refuses an inconsistent adjacent page", async () => {
  const rows = Array.from({length: 15}, (_, n) => ({...summary, discrepancy_id: n === 0 ? id : `edge-${n}`}));
  custom = url => {
    if (!url.pathname.endsWith("/discrepancies")) return null;
    const page = Number(url.searchParams.get("page"));
    return json({job_id: 7, discrepancies: page === 1 ? rows : [{...summary, discrepancy_id: "changed-result"}], total: page === 1 ? 16 : 17, page, page_size: 15, ungroupable_observation_count: 0});
  };
  const {router} = mount(`${path}&page=1`); await ready();
  await screen.findByText("Case 1 of 16 in this selection"); closeDetails(); expect(screen.getByRole("button", {name: "Previous case"})).toBeDisabled();
  await act(async () => {await router.navigate("/investigate?dataset=7&page=1&discrepancy=edge-14");});
  await screen.findByText("Case 15 of 16 in this selection"); fireEvent.click(screen.getByRole("button", {name: "Next case"}));
  await screen.findByText(/The case selection changed/); expect(router.state.location.search).toContain("discrepancy=edge-14"); expect(postCalls("/review")).toHaveLength(0);
});

it("explains unresolved and selected-value actions while keeping technical revision out of the primary review", async () => {
  mount(); await ready();
  expect(screen.getByText("Save this case as unresolved without approving a value.")).toBeVisible();
  expect(screen.getAllByText("unreviewed")).toHaveLength(1);
  expect(screen.queryByText("Server revision 0")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Review action"), {target: {value: "override"}});
  expect(screen.getByText(/Choose a reported value or enter a clock/)).toBeVisible();
  expect(screen.getByLabelText("Supported candidate")).toHaveValue("");
  expect(screen.getByLabelText("Reviewer name or label")).toBeRequired();
  expect(screen.getByLabelText(/Rationale/)).toBeRequired();
  expect(postCalls("/review")).toHaveLength(0);
});

it("opens contextual evidence without changing the URL or losing a retained review draft, and restores trigger focus", async () => {
  const {router} = mount(); await ready(); reviewer(); rationale();
  const before = router.state.location.search;
  closeDetails(); const trigger = screen.getByRole("button", {name: /View source records/}); trigger.focus(); fireEvent.click(trigger);
  const dialog = await screen.findByRole("dialog"); expect(dialog).toHaveTextContent(`Flight ${evidence.flight}`);
  expect(within(dialog).getByRole("region", {name: "Source evidence table"})).toBeInTheDocument();
  expect(router.state.location.search).toBe(before); expect(screen.getAllByRole("dialog")).toHaveLength(1);
  closeDetails(); await waitFor(() => expect(trigger).toHaveFocus());
  openControls(); expect(screen.getByLabelText(/Rationale/)).toHaveValue("Reviewed the source evidence.");
  expect(screen.getByLabelText(/Reviewer name or label/)).toHaveValue("Local analyst");
  closeDetails(); fireEvent.click(screen.getAllByRole("button", {name: /View supporting reports/})[0]);
  const candidate = screen.getByRole("dialog"); expect(candidate).toHaveTextContent(`Reports for ${evidence.candidates[0].canonical_clock}`);
  expect(candidate).toHaveTextContent("Supports selected value"); expect(candidate).toHaveTextContent("Conflicts with selected value");
  closeDetails(); expect(postCalls("/review")).toHaveLength(0); expect(postCalls("/investigations")).toHaveLength(0);
});

it("closes read-only detail before a browser-history draft warning, retaining only one modal and the same draft", async () => {
  const {router} = mount("/investigate?dataset=7&view=table"); await screen.findByRole("table", {name: "Cases"});
  fireEvent.click(screen.getByRole("link", {name: /Open case for ZZ-1/})); await ready(); reviewer(); rationale();
  openSources(); await screen.findByRole("dialog");
  await act(async () => {await router.navigate(-1);});
  await waitFor(() => expect(screen.getAllByRole("dialog")).toHaveLength(1));
  expect(screen.getByRole("dialog")).toHaveTextContent("Leave your unfinished review?");
  fireEvent.click(screen.getByRole("button", {name: "Continue editing"}));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); openControls();
  expect(screen.getByLabelText(/Rationale/)).toHaveValue("Reviewed the source evidence.");
  expect(screen.getByRole("dialog")).toHaveTextContent("Record your review"); expect(postCalls("/review")).toHaveLength(0);
});

it("shows not-requested AI in a contextual view without calling a provider or mounting nested details", async () => {
  mount(); await ready(); openAI();
  expect(screen.getByRole("dialog")).toHaveTextContent("No AI assessment has been requested for this case.");
  expect(screen.getByRole("dialog").querySelector("details")).toBeNull(); closeDetails();
  expect(postCalls("/investigations")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", {name: "View review history (0)"}));
  expect(screen.getByRole("dialog")).toHaveTextContent("No human decisions recorded."); closeDetails();
  openControls(); expect(screen.getByRole("button", {name: "Save review"})).toBeEnabled();
});

it("distinguishes unavailable history from an empty history without retrying on panel open", async () => {
  custom = url => url.pathname.endsWith("/review/history") ? json({detail: "History read unavailable."}, 503) : null;
  mount(); await ready(); closeDetails(); const count = vi.mocked(fetch).mock.calls.length;
  fireEvent.click(screen.getByRole("button", {name: "View review history"}));
  expect(screen.getByRole("dialog")).toHaveTextContent("Review history is unavailable.");
  expect(screen.queryByText("No human decisions recorded.")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(count); closeDetails();
  openControls(); expect(screen.getByRole("button", {name: "Save review"})).toBeEnabled();
});

it("opens review with case/value context and closes an untouched form without saving", async () => {
  const {router} = mount(); await ready(); const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveAccessibleName("Record your review"); expect(dialog).toHaveTextContent(evidence.flight);
  for (const c of evidence.candidates) expect(dialog).toHaveTextContent(c.canonical_clock);
  expect(dialog).toHaveTextContent("Current review: unreviewed"); expect(dialog).toHaveTextContent("Leave unresolved");
  fireEvent.click(screen.getByRole("button", {name: "Close details"})); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(router.state.location.search).toBe(new URL('http://test'+path).search); expect(postCalls('/review')).toHaveLength(0);
});

it("offers continue, explicit discard and safe evidence inspection when closing a modified review", async () => {
  mount(); await ready(); reviewer(); rationale();
  fireEvent.click(screen.getByRole("button", {name: "Close details"}));
  expect(screen.getAllByRole("dialog")).toHaveLength(1); expect(screen.getByRole("dialog")).toHaveTextContent("Leave your unfinished review?");
  fireEvent.click(screen.getByRole("button", {name: "Continue editing"})); expect(screen.getByLabelText(/Rationale/)).toHaveValue("Reviewed the source evidence.");
  fireEvent.click(screen.getByRole("button", {name: "Close details"})); fireEvent.click(screen.getByRole("button", {name: "Keep draft and view case"}));
  expect(screen.getByRole("button", {name: "Resume review"})).toBeInTheDocument(); openSources(); closeDetails(); openControls();
  expect(screen.getByLabelText(/Reviewer name or label/)).toHaveValue("Local analyst");
  fireEvent.click(screen.getByRole("button", {name: "Close details"})); fireEvent.click(screen.getByRole("button", {name: "Discard draft"}));
  openControls(); expect(screen.getByLabelText(/Rationale/)).toHaveValue(""); expect(screen.getByLabelText(/Reviewer name or label/)).toHaveValue("");
  expect(postCalls('/review')).toHaveLength(0);
});

it("keeps uncertain review request identity protected when closing its dialog", async () => {
  custom = (url, options) => url.pathname.endsWith('/review') && options?.method === 'POST' ? Promise.reject(new TypeError('Disconnected')) : null;
  mount(); await ready(); reviewer(); fireEvent.click(screen.getByRole('button', {name:'Save review'})); await screen.findByRole('button', {name:'Retry exact review request'});
  fireEvent.click(screen.getByRole('button', {name:'Close details'}));
  expect(screen.getByRole('dialog')).toHaveTextContent('A request still needs confirmation');
  expect(screen.queryByRole('button', {name:'Discard draft'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Continue editing'})); custom = null;
  fireEvent.click(screen.getByRole('button', {name:'Retry exact review request'})); await screen.findByText(/Review saved/);
  expect(postCalls('/review')[0][1]!.body).toBe(postCalls('/review')[1][1]!.body);
  fireEvent.click(screen.getByRole('button', {name:'Close details'})); expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
