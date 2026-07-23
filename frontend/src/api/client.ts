import type { GenerateRequest, GenerateResponse, JobStatusResponse } from "../types";

// The backend runs as a local-only sidecar process. Its port is fixed by
// backend/.env (PORT, default 8000) and it only ever binds 127.0.0.1, so a
// hardcoded localhost base URL is safe and avoids needing service discovery.
const API_BASE_URL = "http://127.0.0.1:8000/api";

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar con el backend local. ¿Está corriendo el servidor?"
    );
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore body parse failures, fall back to statusText
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export function createJob(payload: GenerateRequest): Promise<GenerateResponse> {
  return request<GenerateResponse>("/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return request<JobStatusResponse>(`/jobs/${jobId}`);
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE_URL}/jobs/${jobId}/download`;
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    await request("/health");
    return true;
  } catch {
    return false;
  }
}
