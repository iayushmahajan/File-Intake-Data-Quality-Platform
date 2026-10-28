import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { UploadPanel } from "./UploadPanel";
import { FIELDS } from "../../types/imports";
afterEach(() => vi.unstubAllGlobals());
it("invalidates a successful preview when a mapping changes", async () => {
  const preview = {
    headers: [...FIELDS, "Customer Email"],
    required_fields: FIELDS,
    suggested_mapping: Object.fromEntries(FIELDS.map((f) => [f, f])),
    rows: [],
    sample_limit: 10,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (url: string) => ({
      ok: true,
      json: async () => (url.includes("/templates") ? [] : preview),
    })),
  );
  render(<UploadPanel onUploadComplete={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("CSV file"), {
    target: {
      files: [new File(["email\nhello"], "sample.csv", { type: "text/csv" })],
    },
  });
  await screen.findByLabelText("Map email");
  expect(
    screen.getByRole("button", { name: "Upload and Analyze CSV" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Preview validation" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Upload and Analyze CSV" }),
    ).toBeEnabled(),
  );
  fireEvent.change(screen.getByLabelText("Map email"), {
    target: { value: "Customer Email" },
  });
  expect(
    screen.getByRole("button", { name: "Upload and Analyze CSV" }),
  ).toBeDisabled();
  expect(screen.queryByText(/Preview · first/)).not.toBeInTheDocument();
});

const inspection = {
  headers: FIELDS,
  required_fields: FIELDS,
  suggested_mapping: Object.fromEntries(FIELDS.map((field) => [field, field])),
  rows: [],
  sample_limit: 10,
};
const chooseFile = (name = "sample.csv") =>
  fireEvent.change(screen.getByLabelText("CSV file"), {
    target: { files: [new File(["sample"], name, { type: "text/csv" })] },
  });

it("rejects non-CSV files without sending a preview request", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetch);
  render(<UploadPanel onUploadComplete={vi.fn()} />);
  chooseFile("sample.xlsx");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Only .csv files are allowed.",
  );
  expect(
    fetch.mock.calls.every(([url]) => String(url).endsWith("/templates")),
  ).toBe(true);
});

it("keeps manual import available when saved templates cannot load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith("/templates")) throw new Error("Offline");
      return { ok: true, json: async () => inspection };
    }),
  );
  render(<UploadPanel onUploadComplete={vi.fn()} />);
  chooseFile();
  await screen.findByLabelText("Map email");
  expect(
    await screen.findByText(
      "Templates unavailable. You can still configure this import.",
    ),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Preview validation" }),
  ).toBeEnabled();
});

it("blocks previews when two fields map to the same source column", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(async (url: string) => ({
        ok: true,
        json: async () => (url.endsWith("/templates") ? [] : inspection),
      })),
  );
  render(<UploadPanel onUploadComplete={vi.fn()} />);
  chooseFile();
  await screen.findByLabelText("Map email");
  fireEvent.change(screen.getByLabelText("Map email"), {
    target: { value: "customer_id" },
  });
  expect(
    screen.getByRole("button", { name: "Preview validation" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Upload and Analyze CSV" }),
  ).toBeDisabled();
});

it("retries a failed upload successfully without premature success", async () => {
  const complete = vi.fn(),
    failed = vi.fn(),
    started = vi.fn();
  const result = {
    job_id: 12,
    status: "pending",
    status_url: "/api/v1/jobs/12",
    message: "Upload accepted for background processing.",
    original_filename: "sample.csv",
    saved_filename: "saved_sample.csv",
    error_message: null,
  };
  const uploadRequest = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({ detail: "Processing service unavailable" }),
    })
    .mockResolvedValueOnce({ ok: true, json: async () => result });
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(async (url: string) =>
        url.endsWith("/uploads")
          ? uploadRequest()
          : {
              ok: true,
              json: async () => (url.endsWith("/templates") ? [] : inspection),
            },
      ),
  );
  render(
    <UploadPanel
      onUploadComplete={complete}
      onUploadError={failed}
      onUploadStart={started}
    />,
  );
  chooseFile();
  await screen.findByLabelText("Map email");
  fireEvent.click(screen.getByRole("button", { name: "Preview validation" }));
  const upload = screen.getByRole("button", { name: "Upload and Analyze CSV" });
  await waitFor(() => expect(upload).toBeEnabled());
  fireEvent.click(upload);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Processing service unavailable",
  );
  expect(complete).not.toHaveBeenCalled();
  expect(started).toHaveBeenCalledTimes(1);
  expect(failed).toHaveBeenCalledTimes(1);
  expect(upload).toBeEnabled();
  fireEvent.click(upload);
  await waitFor(() => expect(complete).toHaveBeenCalledWith(result));
  expect(complete).toHaveBeenCalledTimes(1);
  expect(started).toHaveBeenCalledTimes(2);
  expect(failed).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
