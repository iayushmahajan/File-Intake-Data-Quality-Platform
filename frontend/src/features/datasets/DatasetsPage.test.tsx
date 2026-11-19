import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { applicationRoutes } from "../../routes";
import { FLIGHT_FIELDS, localPreview, MAX_POLLS, type FlightsJob, POLL_INTERVAL } from "./flights";

const job: FlightsJob = { id: 7, job_kind: "raha_flights_v1", contract_version: 1, status: "completed",
  filename_original: "observations.csv", filename_input_saved: "owned.csv", input_sha256: "a".repeat(64), file_size: 160,
  created_at: "2026-01-01", processed_at: "2026-01-01", attempts: 1, duration_ms: 15, observation_count: 26,
  observations_available: true, issues: [], error_message: null };
const observation = { row_number: 2, tuple_id: "opaque-1", src: "source-A", flight: "ZZ-1-AAA-BBB", sched_dep_time: "9:22 a.m.",
  act_dep_time: "", sched_arr_time: "Contact Airline", act_arr_time: "<untrusted source text>", issues: [] };
let routers: ReturnType<typeof createMemoryRouter>[] = [];
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const csv = [FLIGHT_FIELDS.join(","), ...Array.from({ length: 9 }, (_, i) => `opaque-${i},source-A,ZZ-1-AAA-BBB,"9:22 a.m.",,Contact Airline,"literal, source"`)].join("\r\n");
function mount(path = "/datasets") {
  const router = createMemoryRouter(applicationRoutes, { initialEntries: [path], future: { v7_relativeSplatPath: true } });
  routers.push(router);
  const view = render(<RouterProvider router={router} future={{ v7_startTransition: true }} />);
  return { ...view, router };
}
beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.stubGlobal("scrollTo", vi.fn());
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    const url = new URL(input);
    if (url.pathname.endsWith("/observations")) {
      const page = Number(url.searchParams.get("page"));
      return json({ job_id: 7, page, page_size: 25, total: 26, observations: [{ ...observation, tuple_id: `opaque-${page}`, row_number: page + 1 }] });
    }
    if (url.pathname.endsWith("/uploads")) return json({ job_id: 7, status: "queued", message: "Accepted", status_url: "/api/v1/flights/jobs/7" }, 202);
    return json(job);
  }));
});
afterEach(() => { routers.forEach(router => router.dispose()); routers = []; vi.useRealTimers(); vi.unstubAllGlobals(); Reflect.deleteProperty(Element.prototype, "scrollIntoView"); });

it("shows the supported schema and bounded raw local preview without legacy or automatic API requests", async () => {
  mount();
  expect(screen.queryByText("+ New processing job")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Import observations" })).toBeDisabled();
  expect(screen.getByText("Required columns:")).toBeInTheDocument();
  expect(screen.getByText("raha_flights_v1")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Flights observation CSV"), { target: { files: [new File([csv], "observations.csv", { type: "text/csv" })] } });
  const table = await screen.findByRole("region", { name: "Local CSV preview" });
  expect(within(table).getAllByRole("row")).toHaveLength(6);
  expect(within(table).getAllByText("9:22 a.m.")).toHaveLength(5);
  expect(within(table).getAllByText("literal, source")).toHaveLength(5);
  expect(fetch).not.toHaveBeenCalled();
});

it("submits the original File multipart, then retrieves real status and bounded persisted observations", async () => {
  const { router } = mount();
  const file = new File([csv], "observations.csv", { type: "text/csv" });
  fireEvent.change(screen.getByLabelText("Flights observation CSV"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Import observations" }));
  await screen.findByRole("heading", { name: "Raw observations" });
  expect(router.state.location.search).toBe("?dataset=7");
  const options = vi.mocked(fetch).mock.calls.find(([path]) => String(path).endsWith("/flights/uploads"))![1]!;
  expect(options.method).toBe("POST"); expect(options.body).toBeInstanceOf(FormData);
  expect((options.body as FormData).get("file")).toBe(file); expect(options.headers).toBeUndefined();
  expect(screen.getByText(/Upload accepted · Import #7/)).toBeInTheDocument();
  const table = screen.getByRole("region", { name: "Persisted observations table" });
  await within(table).findByText("<untrusted source text>");
  expect(within(table).getByText("9:22 a.m.")).toBeInTheDocument();
  expect(within(table).getByLabelText("Empty string")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Investigate evidence/ })).toHaveAttribute("href", "/investigate?dataset=7");
  fireEvent.click(screen.getByRole("button", { name: "Next observations" }));
  await screen.findByText("opaque-2");
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("page=2&page_size=25"), expect.anything());
  expect(screen.getByRole("button", { name: "Next observations" })).toBeDisabled();
});

it("distinguishes HTTP 202 acceptance, queued/processing states and failure without fabricated observations", async () => {
  vi.useFakeTimers();
  let stage = 0;
  vi.mocked(fetch).mockImplementation(async (input) => String(input).endsWith("/uploads") ? json({ job_id: 7 }, 202) : json({ ...job,
    status: ["queued", "processing", "failed"][Math.min(stage++, 2)], observation_count: 0, observations_available: false,
    error_message: stage >= 3 ? "Observation identifier occurs more than once." : null,
    issues: stage >= 3 ? [{ code: "duplicate_tuple_id", field: "tuple_id", row_number: 3, message: "Duplicate tuple_id." }] : [] }));
  mount("/datasets?dataset=7");
  await act(async () => {});
  expect(screen.getByText("queued")).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL); });
  expect(screen.getByText("processing")).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL); });
  expect(screen.getByText("failed")).toBeInTheDocument();
  expect(screen.getByText("Observation identifier occurs more than once.")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Raw observations" })).not.toBeInTheDocument();
  const calls = vi.mocked(fetch).mock.calls.length;
  await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL * 2); });
  expect(fetch).toHaveBeenCalledTimes(calls);
});

it("caps polling, exposes explicit refresh, and stops requests on unmount", async () => {
  vi.useFakeTimers();
  vi.mocked(fetch).mockResolvedValue(json({ ...job, status: "pending", observation_count: 0, observations_available: false }));
  // Each call needs a fresh Response body.
  vi.mocked(fetch).mockImplementation(async () => json({ ...job, status: "pending", observation_count: 0, observations_available: false }));
  const { unmount } = mount("/datasets?dataset=7");
  await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL * MAX_POLLS); });
  expect(fetch).toHaveBeenCalledTimes(MAX_POLLS);
  expect(screen.getByText(/Automatic checks paused/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Check status again" }));
  await act(async () => {});
  expect(fetch).toHaveBeenCalledTimes(MAX_POLLS + 1);
  const signal = vi.mocked(fetch).mock.calls.at(-1)![1]!.signal!;
  unmount(); expect(signal.aborted).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL * 5); });
  expect(fetch).toHaveBeenCalledTimes(MAX_POLLS + 1);
});

it("shows backend/network failures as errors and never as an empty successful dataset", async () => {
  vi.mocked(fetch).mockRejectedValue(new TypeError("Failed to fetch"));
  mount("/datasets?dataset=7");
  expect(await screen.findByRole("alert")).toHaveTextContent("backend could not be reached");
  expect(screen.queryByText("completed", { exact: true })).not.toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Retry status" })).toBeEnabled();
});

it("preserves structured upload errors and cancels an in-flight upload on navigation/unmount", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(json({ detail: { code: "evaluation_reference", message: "Evaluation reference cannot be imported." } }, 422));
  const { unmount } = mount();
  fireEvent.change(screen.getByLabelText("Flights observation CSV"), { target: { files: [new File([csv], "flights.csv")] } });
  fireEvent.click(screen.getByRole("button", { name: "Import observations" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Evaluation reference cannot be imported.");
  vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
  fireEvent.click(screen.getByRole("button", { name: "Import observations" }));
  expect(screen.getByRole("button", { name: "Uploading original CSV…" })).toBeDisabled();
  const signal = vi.mocked(fetch).mock.calls.at(-1)![1]!.signal!;
  unmount(); expect(signal.aborted).toBe(true);
});

it("rejects invalid dataset URL IDs without querying any job and retains multiline raw strings", async () => {
  mount("/datasets?dataset=-2");
  expect(screen.getByRole("alert")).toHaveTextContent("dataset identifier is invalid");
  expect(fetch).not.toHaveBeenCalled();
  const value = await localPreview(new File([`${FLIGHT_FIELDS.join(",")}\n0007, source ,ZZ-1-AAA-BBB,"line one\nline two",,,`], "quoted.csv"), new AbortController().signal);
  expect(value.rows[0][3]).toBe("line one\nline two");
  expect(value.rows[0][0]).toBe("0007");
  expect(value.rows[0][1]).toBe(" source ");
  expect(value.rows[0][4]).toBe("");
});

it("allows original-file submission when the local preview is unavailable", async () => {
  mount();
  const malformed = new File([`${FLIGHT_FIELDS.join(",")}\nopaque,source,ZZ-1-AAA-BBB,"unterminated`], "original.csv");
  fireEvent.change(screen.getByLabelText("Flights observation CSV"), { target: { files: [malformed] } });
  expect(await screen.findByText(/bounded preview could not read complete quoted records/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Import observations" })).toBeEnabled();
  const long = new File([`${FLIGHT_FIELDS.join(",")}\nopaque,source,ZZ-1-AAA-BBB,13:00,,,${"x".repeat(70000)}`], "large.csv");
  const preview = await localPreview(long, new AbortController().signal);
  expect(preview.prefixLimited).toBe(true);
  expect(preview.rows).toEqual([]); // The cut record is not falsely displayed as a complete raw value.
});

it("times out a hung status request with a truthful retry state", async () => {
  vi.useFakeTimers();
  vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
  mount("/datasets?dataset=7");
  await act(async () => { await vi.advanceTimersByTimeAsync(15000); });
  expect(screen.getByRole("alert")).toHaveTextContent("status request timed out");
  expect(vi.mocked(fetch).mock.calls[0][1]!.signal!.aborted).toBe(true);
  expect(screen.queryByText("completed", { exact: true })).not.toBeInTheDocument();
});

it("separates observation retrieval failure from import completion and offers a bounded retry", async () => {
  const ordinary = vi.mocked(fetch).getMockImplementation()!;
  let fail = true;
  vi.mocked(fetch).mockImplementation((input, init) => String(input).includes("/observations") && fail
    ? Promise.resolve(json({ detail: "Observation storage is unavailable." }, 503)) : ordinary(input, init));
  mount("/datasets?dataset=7");
  expect(await screen.findByRole("alert")).toHaveTextContent("Observation storage is unavailable.");
  expect(screen.getByText("completed", { exact: true })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Persisted observations table" })).not.toBeInTheDocument();
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry observations" }));
  await screen.findByText("opaque-1");
});

it("opens a selected import in source-record mode without displaying upload controls or requiring an import number", async () => {
  mount("/datasets?dataset=7&view=records");
  expect(screen.getByRole("heading", {name: "Source records"})).toBeInTheDocument();
  expect(screen.queryByLabelText("Flights observation CSV")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Open an existing Flights import")).not.toBeInTheDocument();
  const table = await screen.findByRole("region", {name: "Persisted observations table"});
  await within(table).findByText("opaque-1");expect(within(table).getByLabelText("Empty string")).toBeInTheDocument();
  expect(screen.getByText("Import details").closest("details")).not.toHaveAttribute("open");
  fireEvent.click(screen.getByText("Import details"));expect(screen.getByText("a".repeat(64))).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: "Next observations"}));await within(await screen.findByRole("region", {name: "Persisted observations table"})).findByText("opaque-2");
  expect(screen.getByRole("button", {name: "Next observations"})).toBeDisabled();
  expect(screen.getByRole("link", {name: "Back to cases"})).toHaveAttribute("href", "/investigate?dataset=7&view=table");
  expect(vi.mocked(fetch).mock.calls.every(([,options]) => !options?.method || options.method === "GET")).toBe(true);
});

it("preserves selected-import case filters in source-record return navigation and rejects another dataset's context", async () => {
  const {router} = mount("/datasets?dataset=7&view=records");
  await act(async () => {await router.navigate("/datasets?dataset=7&view=records", {state: {investigateReturn: "?dataset=7&view=case&kind=conflict&page=2&field=act_dep_time&discrepancy=old"}});});
  const link = screen.getByRole("link", {name: "Back to cases"});
  const query = new URL(link.getAttribute("href")!, "http://local").searchParams;
  expect(query.get("dataset")).toBe("7");expect(query.get("kind")).toBe("conflict");expect(query.get("page")).toBe("2");expect(query.get("field")).toBe("act_dep_time");expect(query.get("view")).toBe("table");expect(query.has("discrepancy")).toBe(false);
  await act(async () => {await router.navigate("/datasets?dataset=7&view=records", {state: {investigateReturn: "?dataset=99&view=case&job=123&page=2"}});});
  expect(screen.getByRole("link", {name: "Back to cases"})).toHaveAttribute("href", "/investigate?dataset=7&view=table");
});
