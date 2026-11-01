import { afterEach, expect, it, vi } from "vitest";
import { api, API_BASE_URL } from "./api";

afterEach(() => vi.unstubAllGlobals());

function errorResponse(detail: unknown, status = 422) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ detail }), { status },
  )));
}

it("formats field-specific FastAPI errors without echoing input or diagnostic metadata", async () => {
  errorResponse([
    { loc: ["body", "file"], msg: "Field required", type: "missing", input: "private@example.com" },
    { loc: ["query", "page"], msg: "Input should be greater than or equal to 1", input: -1 },
    {
      loc: ["body", "patches", 3, "email"], msg: "Input should be a valid string",
      input: { secret: "sensitive-value" }, ctx: { error: "internal traceback" }, url: "internal-diagnostics",
    },
  ]);
  await expect(api("/api/v1/uploads")).rejects.toMatchObject({
    message: "file: Field required; page: Input should be greater than or equal to 1; patches.3.email: Input should be a valid string",
  });
});

it("omits submitted dictionary keys from key-validation error locations", async () => {
  errorResponse([{
    loc: ["body", "patches", "private@example.com", "[key]"],
    msg: "Input should be a valid integer, unable to parse string as an integer",
    type: "int_parsing", input: "private@example.com",
  }]);
  await expect(api("/api/v1/jobs/1/corrections")).rejects.toThrow(
    /^patches: Input should be a valid integer, unable to parse string as an integer$/,
  );
});

it("shows model-level messages and skips malformed entries without hiding valid errors", async () => {
  errorResponse([
    null, { loc: ["body", "name"], msg: 42 }, { loc: [{ secret: "value" }], msg: "Bad location" },
    { msg: "Missing location" }, { loc: [], msg: " " },
    { loc: ["body"], msg: "Value error, Corrections must reference data records and known fields" },
  ]);
  await expect(api("/api/v1/jobs/1/corrections")).rejects.toThrow(
    /^Value error, Corrections must reference data records and known fields$/,
  );
});

it.each([400, 409, 422, 503])("preserves string error details for HTTP %i", async status => {
  errorResponse("Reload templates and preview again.", status);
  await expect(api("/api/v1/imports/preview")).rejects.toThrow(/^Reload templates and preview again\.$/);
});

it.each([
  null,
  "Unexpected upstream response",
  { detail: { message: "Unexpected object" } },
  { detail: [] },
  { detail: [null, { loc: ["body", "file"], msg: 7 }] },
])("falls back safely for an unusable JSON error body: %j", async body => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 422 })));
  await expect(api("/api/v1/uploads")).rejects.toThrow(/^Request failed \(422\)\.$/);
});

it("uses the status fallback for non-JSON errors and non-422 structured bodies", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 })));
  await expect(api("/api/v1/jobs")).rejects.toThrow(/^Request failed \(502\)\.$/);
  errorResponse([{ loc: ["body", "file"], msg: "Internal details" }], 500);
  await expect(api("/api/v1/uploads")).rejects.toThrow(/^Request failed \(500\)\.$/);
});

it("propagates network failures unchanged", async () => {
  const failure = new TypeError("Failed to fetch");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(failure));
  await expect(api("/api/v1/jobs")).rejects.toBe(failure);
});

it("preserves successful JSON responses and forwards request options", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ job_id: 4 })));
  vi.stubGlobal("fetch", fetch);
  const options = { method: "POST", body: new FormData(), signal: new AbortController().signal };
  await expect(api("/api/v1/uploads", options)).resolves.toEqual({ job_id: 4 });
  expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/api/v1/uploads`, options);
});
