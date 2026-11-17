export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) { super(message); this.name = "ApiError"; }
}

function validationMessage(issue: unknown): string {
  if (
    !issue || typeof issue !== "object" ||
    !("msg" in issue) || typeof issue.msg !== "string" || !issue.msg.trim() ||
    !("loc" in issue) || !Array.isArray(issue.loc) ||
    !issue.loc.every(part => typeof part === "string" || Number.isInteger(part))
  ) return "";

  const location = [...issue.loc];
  if (["body", "query", "path", "header", "cookie"].includes(location[0]))
    location.shift();
  // Pydantic includes the submitted dictionary key before this marker.
  if (location.at(-1) === "[key]") location.splice(-2);
  const field = location.join(".");
  return field ? `${field}: ${issue.msg}` : issue.msg;
}

export async function apiResponse(
  path: string,
  options?: RequestInit,
): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body
      ? body.detail
      : undefined;
    const validation = response.status === 422 && Array.isArray(detail)
      ? detail.map(validationMessage).filter(Boolean).join("; ")
      : "";

    const intake = detail && typeof detail === "object" && "code" in detail && typeof detail.code === "string" &&
      "message" in detail && typeof detail.message === "string" && detail.message.trim()
      ? detail.message : "";

    throw new ApiError(
      typeof detail === "string"
        ? detail
        : validation || intake || `Request failed (${response.status}).`,
      response.status,
    );
  }

  return response;
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  return (await apiResponse(path, options)).json() as Promise<T>;
}
export function downloadUrl(id: number, kind: "input" | "clean" | "errors") {
  return `${API_BASE_URL}/api/v1/jobs/${id}/download/${kind}`;
}
