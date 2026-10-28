import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ResultsPanel } from "./ResultsPanel";
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it("shows a useful empty state", () => {
  render(<ResultsPanel jobId={null} />);
  expect(screen.getByText(/Your next dataset/)).toBeInTheDocument();
});
it("shows upload status while sending a file", () => {
  render(<ResultsPanel jobId={null} isLoading />);
  expect(screen.getByRole("status")).toHaveTextContent("Uploading your file");
});
it("loads a historical failed job and disables AI", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 4,
        status: "failed",
        filename_original: "broken.csv",
        created_at: "2026-04-01T12:00:00",
        error_message: "Missing required columns",
        total_rows: 0,
        valid_rows: 0,
        invalid_rows: 0,
        file_size: 10,
        duration_ms: 4,
        analysis: null,
        error_breakdown: {},
        ai_report: null,
      }),
    }),
  );
  render(<ResultsPanel jobId={4} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Missing required columns",
  );
  expect(
    screen.getByRole("button", { name: "Generate insights" }),
  ).toBeDisabled();
});
it("offers retry on API failure", async () => {
  const fetchMock = vi.fn().mockRejectedValue(new Error("Network unavailable"));
  vi.stubGlobal("fetch", fetchMock);
  render(<ResultsPanel jobId={4} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Network unavailable",
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Network unavailable",
  );
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("polls queued and processing jobs, then stops on completion", async () => {
  vi.useFakeTimers();
  const { act } = await import("@testing-library/react");
  const base = {
    id: 9,
    filename_original: "async.csv",
    created_at: "2026-04-01T12:00:00",
    error_message: null,
    total_rows: 2,
    valid_rows: 2,
    invalid_rows: 0,
    file_size: 50,
    duration_ms: 4,
    analysis: null,
    error_breakdown: {},
    ai_report: null,
    attempts: 1,
  };
  const fetchMock = vi.fn();
  for (const status of ["queued", "processing", "completed"])
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...base, status }),
    });
  vi.stubGlobal("fetch", fetchMock);
  const terminal = vi.fn();
  const view = render(<ResultsPanel jobId={9} onTerminal={terminal} />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(screen.getByRole("status")).toHaveTextContent("Queued for a worker");
  expect(screen.queryByText("Quality score")).not.toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500);
  });
  expect(screen.getByRole("status")).toHaveTextContent("Processing your CSV");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500);
  });
  expect(screen.getByText("Quality score")).toBeInTheDocument();
  expect(terminal).toHaveBeenCalledTimes(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(fetchMock).toHaveBeenCalledTimes(3);
  view.unmount();
});

it("resumes polling after a transient connection failure and stops on failure", async () => {
  vi.useFakeTimers();
  const { act } = await import("@testing-library/react");
  const failed = {
    id: 5,
    status: "failed",
    filename_original: "bad.csv",
    created_at: "2026-04-01T12:00:00",
    error_message: "Worker retry limit exceeded",
    total_rows: 0,
    valid_rows: 0,
    invalid_rows: 0,
    file_size: 5,
    duration_ms: 0,
    analysis: null,
    error_breakdown: {},
    ai_report: null,
  };
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new Error("Temporary disconnection"))
    .mockResolvedValueOnce({ ok: true, json: async () => failed });
  vi.stubGlobal("fetch", fetchMock);
  const view = render(<ResultsPanel jobId={5} />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Temporary disconnection",
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Worker retry limit exceeded",
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  view.unmount();
});

it("cancels an active job's scheduled polls when unmounted", async () => {
  vi.useFakeTimers();
  const { act } = await import("@testing-library/react");
  const fetchMock = vi
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 6,
        status: "pending",
        filename_original: "pending.csv",
        created_at: "2026-04-01T12:00:00",
        file_size: 10,
        duration_ms: null,
      }),
    });
  vi.stubGlobal("fetch", fetchMock);
  const view = render(<ResultsPanel jobId={6} />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  view.unmount();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
});
