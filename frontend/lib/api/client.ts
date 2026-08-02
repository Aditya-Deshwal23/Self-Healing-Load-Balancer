export type ApiEnvelope<T> = {
  data: T;
  meta?: { request_id?: string; generated_at?: string };
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;

  constructor(
    message: string,
    status: number,
    code = "REQUEST_FAILED",
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

type Problem = { detail?: string; code?: string; request_id?: string };

export async function apiRequest<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<ApiEnvelope<T>> {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    credentials: "same-origin",
    headers: { Accept: "application/json", ...init.headers },
  });
  if (!response.ok) {
    let problem: Problem = {};
    try {
      problem = (await response.json()) as Problem;
    } catch {
      // A non-JSON upstream failure still becomes a bounded client error.
    }
    throw new ApiClientError(
      problem.detail ?? `Request failed with status ${response.status}.`,
      response.status,
      problem.code,
      problem.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
    );
  }
  return (await response.json()) as ApiEnvelope<T>;
}
