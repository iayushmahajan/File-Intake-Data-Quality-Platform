import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

// Keep real history, results and correction components; isolate only file upload.
vi.mock("../panels/UploadPanel", () => ({
  UploadPanel: ({ onUploadStart, onUploadComplete }: {
    onUploadStart: () => void;
    onUploadComplete: (result: { job_id: number }) => void;
  }) => <>
    <button onClick={onUploadStart}>Start test upload</button>
    <button onClick={() => onUploadComplete({ job_id: 2 })}>Complete test upload</button>
  </>,
}));

const record = {
  row_number: 3, status: "rejected",
  values: { customer_id: "C2", email: "bad" }, normalized: {},
  issues: [{ fields: ["email"], category: "Email", message: "email must be valid" }],
};
const jobs = ["original.csv", "other.csv", "child.csv"].map((filename, index) => ({
  id: index + 1, filename_original: filename, status: "completed",
  created_at: "2026-04-01T12:00:00", total_rows: 1, valid_rows: 0, invalid_rows: 1,
  file_size: 100, duration_ms: 1, error_breakdown: { Email: 1 },
  analysis: null, ai_report: null, records_available: true,
  ...(index === 0 ? {
    parent_summary: { id: 2, valid_rows: 0, invalid_rows: 1, score: null },
    child_job_ids: [3],
  } : {}),
}));

beforeEach(() => {
  window.history.replaceState(null, "", "/?job=1&keep=yes");
  Element.prototype.scrollIntoView = vi.fn();
  // jsdom has no native dialog implementation; browser coverage uses showModal.
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = new URL(url).pathname;
    let data: unknown;
    if (path.endsWith("/corrections/validate"))
      data = { valid: true, rows: [{ row_number: 3, issues: [] }], message: "Field checks only" };
    else if (path.endsWith("/corrections")) data = { job_id: 3 };
    else if (path.endsWith("/records"))
      data = { records: [record], total: 1, page: 1, page_size: 25, fields: ["email"] };
    else if (path === "/api/v1/jobs") data = { jobs, total: jobs.length, page: 1, page_size: 10 };
    else data = jobs.find(job => path === `/api/v1/jobs/${job.id}`);
    return { ok: true, json: async () => data };
  }));
});
afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
  Reflect.deleteProperty(Element.prototype, "scrollIntoView");
  window.history.replaceState(null, "", "/");
});

async function editAndValidate(value = "fixed@example.com") {
  fireEvent.click(await screen.findByRole("button", { name: "Correct record 3" }));
  fireEvent.change(screen.getByLabelText("Record 3 email"), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: "Validate corrections" }));
  await screen.findByText("Field validation passed.");
}

it.each([
  ["history", "#2 · other.csv", 2],
  ["original job", "Open original job #2", 2],
  ["child job", "Open correction #3", 3],
])("guards %s navigation; Cancel preserves edits and validation, Discard switches", async (_path, button, target) => {
  render(<AppShell />);
  await editAndValidate();
  fireEvent.click(await screen.findByRole("button", { name: String(button) }));
  expect(screen.getByRole("dialog")).toHaveAccessibleName("Discard unsaved corrections?");
  expect(window.location.search).toBe("?job=1&keep=yes");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "original.csv" })).toBeInTheDocument();
  expect(window.location.search).toBe("?job=1&keep=yes");
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("fixed@example.com");
  expect(screen.getByText("Field validation passed.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reprocess corrected dataset" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: String(button) }));
  fireEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(await screen.findByRole("heading", { name: jobs[Number(target) - 1].filename_original })).toBeInTheDocument();
  expect(window.location.search).toBe(`?job=${target}&keep=yes`);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it.each(["no edits", "restored value", "undo"])("navigates without a warning with %s", async mode => {
  render(<AppShell />);
  fireEvent.click(await screen.findByRole("button", { name: "Correct record 3" }));
  if (mode !== "no edits") {
    const input = screen.getByLabelText("Record 3 email");
    fireEvent.change(input, { target: { value: "fixed@example.com" } });
    if (mode === "undo") fireEvent.click(screen.getByRole("button", { name: "Undo this record" }));
    else fireEvent.change(input, { target: { value: "bad" } });
  }
  fireEvent.click(await screen.findByRole("button", { name: "#2 · other.csv" }));
  expect(await screen.findByRole("heading", { name: "other.csv" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("clears the guard before navigating to a successfully submitted child", async () => {
  render(<AppShell />);
  await editAndValidate();
  fireEvent.click(screen.getByRole("button", { name: "Reprocess corrected dataset" }));
  expect(await screen.findByRole("heading", { name: "child.csv" })).toBeInTheDocument();
  expect(window.location.search).toBe("?job=3&keep=yes");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: "#2 · other.csv" }));
  expect(await screen.findByRole("heading", { name: "other.csv" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("ignores a submitted job's delayed response after navigating and editing another job", async () => {
  const fetchMock = vi.mocked(fetch);
  const originalFetch = fetchMock.getMockImplementation()!;
  let finishSubmission!: (response: Response) => void;
  const submission = new Promise<Response>(resolve => { finishSubmission = resolve; });
  fetchMock.mockImplementation((input, init) =>
    String(input).endsWith("/jobs/1/corrections")
      ? submission
      : originalFetch(input, init),
  );

  render(<AppShell />);
  await editAndValidate();
  fireEvent.click(screen.getByRole("button", { name: "Reprocess corrected dataset" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/jobs/1/corrections"),
    expect.objectContaining({ method: "POST" }),
  ));
  fireEvent.click(await screen.findByRole("button", { name: "#2 · other.csv" }));
  fireEvent.click(screen.getByRole("button", { name: "Discard" }));
  await screen.findByRole("heading", { name: "other.csv" });
  await editAndValidate("other@example.com");

  await act(async () => {
    finishSubmission({ ok: true, json: async () => ({ job_id: 3 }) } as Response);
  });

  expect(screen.getByRole("heading", { name: "other.csv" })).toBeInTheDocument();
  expect(window.location.search).toBe("?job=2&keep=yes");
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("other@example.com");
  expect(screen.getByText("Field validation passed.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reprocess corrected dataset" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "#1 · original.csv" }));
  expect(screen.getByRole("dialog")).toHaveAccessibleName("Discard unsaved corrections?");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(window.location.search).toBe("?job=2&keep=yes");
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("other@example.com");
  expect(screen.getByText("Field validation passed.")).toBeInTheDocument();
});

it("keeps drafts mounted during upload and guards selection of the accepted job", async () => {
  render(<AppShell />);
  await editAndValidate();
  fireEvent.click(screen.getByRole("button", { name: "Start test upload" }));
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("fixed@example.com");
  expect(screen.getByRole("button", { name: "Reprocess corrected dataset" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Complete test upload" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(window.location.search).toBe("?job=1&keep=yes");
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("fixed@example.com");
  expect(screen.getByText("Field validation passed.")).toBeInTheDocument();
});
