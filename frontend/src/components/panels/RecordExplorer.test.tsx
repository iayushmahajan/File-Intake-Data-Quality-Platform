import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RecordExplorer } from "./RecordExplorer";
import type { JobDetail } from "../../types/jobs";
const job: Pick<JobDetail, "id" | "error_breakdown"> = {
  id: 1,
  error_breakdown: { Email: 1 },
};
const record = {
  row_number: 3,
  status: "rejected",
  values: { customer_id: "C2", email: "bad" },
  normalized: {},
  issues: [
    { fields: ["email"], category: "Email", message: "email must be valid" },
  ],
};
afterEach(() => vi.unstubAllGlobals());
it("requires validation again after editing and supports undo", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes("/validate")
          ? {
              valid: true,
              rows: [{ row_number: 3, issues: [] }],
              message: "Field checks only",
            }
          : {
              records: [record],
              total: 1,
              page: 1,
              page_size: 25,
              fields: ["email"],
            },
    })),
  );
  render(<RecordExplorer job={job} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Correct record 3" }),
  );
  const input = screen.getByLabelText("Record 3 email");
  fireEvent.change(input, { target: { value: "bob@example.com" } });
  expect(
    screen.getByRole("button", { name: "Reprocess corrected dataset" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Validate corrections" }));
  await screen.findByText("Field validation passed.");
  expect(
    screen.getByRole("button", { name: "Reprocess corrected dataset" }),
  ).toBeEnabled();
  fireEvent.change(input, { target: { value: "changed@example.com" } });
  expect(
    screen.getByRole("button", { name: "Reprocess corrected dataset" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Undo this record" }));
  expect(input).toHaveValue("bad");
  expect(
    screen.queryByRole("button", { name: "Reprocess corrected dataset" }),
  ).not.toBeInTheDocument();
});
it("uses identical filters for record search and CSV export", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      records: [],
      total: 0,
      page: 1,
      page_size: 25,
      fields: [],
    }),
  });
  vi.stubGlobal("fetch", fetch);
  render(<RecordExplorer job={job} />);
  fireEvent.change(screen.getByLabelText("Search all records"), {
    target: { value: "bob@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Record status"), {
    target: { value: "rejected" },
  });
  fireEvent.change(screen.getByLabelText("Error category"), {
    target: { value: "Email" },
  });
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  const requested = String(fetch.mock.calls.at(-1)?.[0]);
  const link = screen
    .getByRole("link", { name: "Export filtered CSV" })
    .getAttribute("href")!;
  expect(new URL(link).search).toBe(new URL(requested).search);
  expect(new URL(link).searchParams.get("search")).toBe("bob@example.com");
});

it("resets all filters while preserving correction drafts and validation", async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => ({
    ok: true,
    json: async () =>
      url.endsWith("/validate")
        ? {
            valid: true,
            rows: [{ row_number: 3, issues: [] }],
            message: "Field checks only",
          }
        : {
            records: [record],
            total: 50,
            page: Number(new URL(url).searchParams.get("page")),
            page_size: 25,
            fields: ["email"],
          },
  }));
  vi.stubGlobal("fetch", fetch);
  render(<RecordExplorer job={job} category="Email" />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Correct record 3" }),
  );
  fireEvent.change(screen.getByLabelText("Record 3 email"), {
    target: { value: "fixed@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Validate corrections" }));
  await screen.findByText("Field validation passed.");

  fireEvent.change(screen.getByLabelText("Search all records"), {
    target: { value: "bad" },
  });
  fireEvent.change(screen.getByLabelText("Sort by"), {
    target: { value: "email" },
  });
  fireEvent.change(screen.getByLabelText("Direction"), {
    target: { value: "desc" },
  });
  const next = screen.getByRole("button", { name: "Next records" });
  await waitFor(() => expect(next).toBeEnabled());
  fireEvent.click(next);
  await waitFor(() => {
    const params = new URL(String(fetch.mock.calls.at(-1)?.[0])).searchParams;
    expect(Object.fromEntries(params)).toEqual({
      page: "2",
      page_size: "25",
      status: "rejected",
      search: "bad",
      category: "Email",
      sort: "email",
      direction: "desc",
    });
  });

  fireEvent.click(screen.getByRole("button", { name: "Reset Filters" }));
  expect(screen.getByLabelText("Search all records")).toHaveValue("");
  expect(screen.getByLabelText("Record status")).toHaveValue("all");
  expect(screen.getByLabelText("Error category")).toHaveValue("");
  expect(screen.getByLabelText("Sort by")).toHaveValue("row_number");
  expect(screen.getByLabelText("Direction")).toHaveValue("asc");
  await waitFor(() => {
    const requested = new URL(String(fetch.mock.calls.at(-1)?.[0]));
    expect(Object.fromEntries(requested.searchParams)).toEqual({
      page: "1",
      page_size: "25",
      status: "all",
      search: "",
      category: "",
      sort: "row_number",
      direction: "asc",
    });
    const exported = new URL(
      screen.getByRole("link", { name: "Export filtered CSV" }).getAttribute("href")!,
    );
    expect(exported.search).toBe(requested.search);
  });
  expect(screen.getByLabelText("Record 3 email")).toHaveValue("fixed@example.com");
  expect(screen.getByText("edited")).toBeInTheDocument();
  expect(screen.getByText("Field validation passed.")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Reprocess corrected dataset" }),
  ).toBeEnabled();

  fireEvent.click(screen.getByRole("button", { name: "Validate corrections" }));
  await waitFor(() =>
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining("/corrections/validate"),
      expect.objectContaining({
        body: JSON.stringify({ patches: { 3: { email: "fixed@example.com" } } }),
      }),
    ),
  );
});

it.each([
  { ...record, status: "accepted", issues: [], label: "Inspect record 3" },
  {
    ...record,
    issues: [
      {
        fields: [],
        category: "CSV Structure",
        message: "CSV column count does not match header",
      },
    ],
    label: "Correct record 3",
  },
])(
  "keeps $status records with non-editable structure read-only",
  async (row) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          records: [row],
          total: 1,
          page: 1,
          page_size: 25,
          fields: ["email"],
        }),
      }),
    );
    render(<RecordExplorer job={job} />);
    fireEvent.click(await screen.findByRole("button", { name: row.label }));
    expect(screen.getByLabelText("Record 3 email")).toHaveAttribute("readonly");
    expect(
      screen.queryByRole("button", { name: "Validate corrections" }),
    ).not.toBeInTheDocument();
  },
);

it("preserves corrected values after a failed reprocessing request", async () => {
  const onCreated = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith("/corrections"))
        return {
          ok: false,
          status: 503,
          json: async () => ({ detail: "Please retry later" }),
        };
      return {
        ok: true,
        json: async () =>
          url.endsWith("/validate")
            ? {
                valid: true,
                rows: [{ row_number: 3, issues: [] }],
                message: "Field checks only",
              }
            : {
                records: [record],
                total: 1,
                page: 1,
                page_size: 25,
                fields: ["email"],
              },
      };
    }),
  );
  render(<RecordExplorer job={job} onCreated={onCreated} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Correct record 3" }),
  );
  fireEvent.change(screen.getByLabelText("Record 3 email"), {
    target: { value: "fixed@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Validate corrections" }));
  await screen.findByText("Field validation passed.");
  fireEvent.click(
    screen.getByRole("button", { name: "Reprocess corrected dataset" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Please retry later",
  );
  expect(screen.getByLabelText("Record 3 email")).toHaveValue(
    "fixed@example.com",
  );
  expect(onCreated).not.toHaveBeenCalled();
  expect(
    screen.getByRole("button", { name: "Reprocess corrected dataset" }),
  ).toBeEnabled();
});

it("blocks reprocessing when server validation still finds an error", async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => ({
    ok: true,
    json: async () =>
      url.endsWith("/validate")
        ? {
            valid: false,
            rows: [
              {
                row_number: 3,
                issues: [
                  {
                    fields: ["email"],
                    category: "Email",
                    message: "Email is still invalid",
                  },
                ],
              },
            ],
            message: "Fix the validation errors",
          }
        : {
            records: [record],
            total: 1,
            page: 1,
            page_size: 25,
            fields: ["email"],
          },
  }));
  vi.stubGlobal("fetch", fetch);
  render(<RecordExplorer job={job} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Correct record 3" }),
  );
  fireEvent.change(screen.getByLabelText("Record 3 email"), {
    target: { value: "still-invalid" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Validate corrections" }));
  await screen.findAllByText("Email is still invalid");
  expect(screen.getByLabelText("Record 3 email")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(
    screen.getByRole("button", { name: "Reprocess corrected dataset" }),
  ).toBeDisabled();
  expect(
    fetch.mock.calls.some(([url]) => String(url).endsWith("/corrections")),
  ).toBe(false);
});
