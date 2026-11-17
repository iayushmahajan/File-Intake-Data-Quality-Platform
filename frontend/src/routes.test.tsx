import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { applicationRoutes } from "./routes";
import { preferredScrollBehavior } from "./lib/utils";

const jobs = ["original.csv", "other.csv"].map((filename, index) => ({
  id: index + 1, filename_original: filename, status: "completed", created_at: "2026-04-01T12:00:00",
  total_rows: 1, valid_rows: 0, invalid_rows: 1, file_size: 100, duration_ms: 1,
  error_breakdown: { Email: 1 }, analysis: null, ai_report: null, records_available: true,
}));
let routers: ReturnType<typeof createMemoryRouter>[] = [];
beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.stubGlobal("scrollTo", vi.fn());
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    const path = new URL(input).pathname;
    let data: unknown;
    if (path.endsWith("/templates")) data = [];
    else if (path.endsWith("/corrections/validate")) data = { valid: true, rows: [{ row_number: 3, issues: [] }], message: "Field checks only" };
    else if (path.endsWith("/corrections")) data = { job_id: 2 };
    else if (path.endsWith("/records")) data = { records: [{ row_number: 3, status: "rejected", values: { email: "bad" }, normalized: {},
      issues: [{ fields: ["email"], category: "Email", message: "email must be valid" }] }], total: 1, page: 1, page_size: 25, fields: ["email"] };
    else if (path === "/api/v1/jobs") data = { jobs, total: 2, page: 1, page_size: 10 };
    else data = jobs.find(job => path === `/api/v1/jobs/${job.id}`);
    return { ok: true, json: async () => data };
  }));
});
afterEach(() => {
  routers.forEach(router => router.dispose()); routers = [];
  vi.unstubAllGlobals();
  Reflect.deleteProperty(Element.prototype, "scrollIntoView");
});

function mounted(entries = ["/"], initialIndex = entries.length - 1) {
  const router = createMemoryRouter(applicationRoutes, { initialEntries: entries, initialIndex, future: { v7_relativeSplatPath: true } });
  routers.push(router);
  render(<RouterProvider router={router} future={{ v7_startTransition: true }} />);
  return router;
}
function nav(name: string) { return within(screen.getByRole("navigation", { name: "Primary" })).getByRole("link", { name }); }
async function draft() {
  fireEvent.click(await screen.findByRole("button", { name: "Correct record 3" }));
  fireEvent.change(screen.getByLabelText("Record 3 email"), { target: { value: "edited@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Validate corrections" }));
  await screen.findByText("Field validation passed.");
}

it.each([
  ["/", "Clarity from conflicting data.", "Home"],
  ["/datasets", "Import a dataset", "Datasets"],
  ["/investigate", "Investigate", "Investigate"],
  ["/history", "History", "History"],
])("renders %s directly with one main landmark and accurate navigation", async (path, heading, selected) => {
  mounted([path]);
  expect(await screen.findByRole("heading", { level: 1, name: new RegExp(heading) })).toBeInTheDocument();
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(nav(selected)).toHaveAttribute("aria-current", "page");
  expect(screen.queryByText("Local workspace")).not.toBeInTheDocument();
  expect(document.querySelector('a[href^="/legacy/transactions"]')).toBeNull();
  expect(screen.getByRole("link", {name: "Reconcile Workbench home"}).querySelector("img")).toHaveAttribute("src", "/brand/reconcile-symbol-dark.svg");
  expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");
  if (path !== "/legacy/transactions") expect(screen.queryByText("+ New processing job")).not.toBeInTheDocument();
});

it("handles unknown routes and focus after actual route changes", async () => {
  mounted(["/missing?job=1"]);
  expect(screen.getByRole("heading", { name: "That page isn’t here." })).toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Primary" })).queryByRole("link", { current: "page" })).not.toBeInTheDocument();
  fireEvent.click(nav("Investigate"));
  await screen.findByRole("heading", { name: "Investigate" });
  expect(screen.getByRole("main")).toHaveFocus();
});

it.each(["/", "/datasets"])("migrates %s transaction job links without passing their IDs to Flights", async oldPath => {
  const router = mounted([`${oldPath}?job=1&keep=yes`]);
  await screen.findByRole("heading", { name: "original.csv" });
  expect(router.state.location.pathname).toBe("/legacy/transactions");
  expect(router.state.location.search).toBe("?job=1&keep=yes");
  fireEvent.click(nav("History"));
  await screen.findByRole("heading", { name: "History" });
  expect(router.state.location.search).not.toContain("job=");
  fireEvent.click(nav("Home"));
  await screen.findByRole("heading", { name: /Clarity from/ });
  fireEvent.click(screen.getByRole("link", { name: /Open workspace/ }));
  await screen.findByRole("heading", { name: "Import a dataset" });
  expect(router.state.location.pathname).toBe("/datasets");
  expect(router.state.location.search).not.toContain("job=");
});

it.each(["back", "forward"])("supports browser %s without remounting the workspace on canceled POPs", async direction => {
  const delta = direction === "back" ? -1 : 1;
  const router = direction === "back"
    ? mounted(["/investigate", "/legacy/transactions?job=1&keep=yes"])
    : mounted(["/legacy/transactions?job=1&keep=yes", "/investigate"], 0);
  await draft();
  await act(async () => { await router.navigate(delta); });
  expect(await screen.findByRole("dialog", { name: "Discard unsaved corrections?" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(router.state.location.pathname).toBe("/legacy/transactions");
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("edited@example.com");
  expect(screen.getByText("Field validation passed.")).toBeInTheDocument();
  await act(async () => { await router.navigate(delta); });
  fireEvent.click(screen.getByRole("button", { name: "Discard and continue" }));
  await screen.findByRole("heading", { name: "Investigate" });
  await act(async () => { await router.navigate(-delta); });
  await screen.findByRole("heading", { name: "original.csv" });
  expect(router.state.location.search).toBe("?job=1&keep=yes");
});

it.each(["Home", "History", "Investigate"])("blocks %s links and preserves drafts when canceled", async target => {
  const router = mounted(["/legacy/transactions?job=1"]);
  await draft();
  fireEvent.click(nav(target));
  await screen.findByRole("dialog", { name: "Discard unsaved corrections?" });
  expect(screen.getAllByRole("dialog")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(router.state.location.pathname).toBe("/legacy/transactions");
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("edited@example.com");
  expect(screen.getByRole("button", { name: "Reprocess corrected dataset" })).toBeEnabled();
  const unload = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(unload);
  expect(unload.defaultPrevented).toBe(true);
});

it("uses one guard for query/job navigation and clears it after a successful correction", async () => {
  const router = mounted(["/legacy/transactions?job=1&keep=yes"]);
  await draft();
  fireEvent.click(screen.getByRole("button", { name: "#2 · other.csv" }));
  expect(await screen.findByRole("dialog")).toHaveAccessibleName("Discard unsaved corrections?");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "Reprocess corrected dataset" }));
  await screen.findByRole("heading", { name: "other.csv" });
  expect(router.state.location.search).toBe("?job=2&keep=yes");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("opens and closes the mobile dialog with accessible names and focus restoration", async () => {
  mounted(["/investigate"]);
  const trigger = screen.getByRole("button", { name: "Open navigation" });
  fireEvent.click(trigger);
  const dialog = await screen.findByRole("dialog", { name: "Navigation" });
  expect(trigger).toHaveAttribute("aria-expanded", "true");
  expect(within(dialog).getByRole("link", { name: "Investigate" })).toHaveAttribute("aria-current", "page");
  fireEvent.click(within(dialog).getByRole("button", { name: "Close navigation" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(trigger).toHaveFocus();
  fireEvent.click(trigger);
  fireEvent.click(within(await screen.findByRole("dialog")).getByRole("link", { name: "History" }));
  await screen.findByRole("heading", { name: "History" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("honors reduced motion for existing workspace programmatic scrolling", () => {
  mounted(["/legacy/transactions"]);
  vi.mocked(window.matchMedia).mockImplementation((query: string) => ({ matches: query.includes("reduced-motion"), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }) as unknown as MediaQueryList);
  expect(preferredScrollBehavior()).toBe("auto");
  fireEvent.click(screen.getByRole("link", { name: "Skip to content" }));
  expect(screen.getByRole("main")).toHaveFocus();
  expect(window.location.hash).toBe("");
  fireEvent.click(screen.getByRole("link", { name: "+ New processing job" }));
  expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: "auto", block: "start" });
});
