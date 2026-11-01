export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function api<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    const body: { detail?: unknown } =
      await response.json().catch(() => ({}));

    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}).`,
    );
  }

  return response.json() as Promise<T>;
}
export function downloadUrl(id: number, kind: "input" | "clean" | "errors") {
  return `${API_BASE_URL}/api/v1/jobs/${id}/download/${kind}`;
}
