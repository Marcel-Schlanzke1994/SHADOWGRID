import type { ApiErrorBody } from "@shadowgrid/shared-types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;
  readonly fields?: Record<string, string>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.error.code;
    this.requestId = body.error.request_id;
    this.fields = body.error.fields;
  }
}

export interface ClientOptions {
  baseUrl: string;
  getAccessToken: () => string | null;
  onUnauthorized?: () => Promise<boolean>;
}

export class ShadowgridClient {
  constructor(private readonly options: ClientOptions) {}

  async request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
    const token = this.options.getAccessToken();
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`${this.options.baseUrl}${path}`, { ...init, headers, credentials: "include" });
    if (response.status === 401 && retry && this.options.onUnauthorized && (await this.options.onUnauthorized())) {
      return this.request<T>(path, init, false);
    }
    if (!response.ok) {
      const fallback: ApiErrorBody = { error: { code: "network.http_error", message: response.statusText }, server_time: new Date().toISOString() };
      let body = fallback;
      try { body = (await response.json()) as ApiErrorBody; } catch { /* a non-JSON proxy response is normalized */ }
      throw new ApiError(response.status, body);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  get<T>(path: string): Promise<T> { return this.request<T>(path); }
  post<T>(path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return this.request<T>(path, { method: "POST", headers, body: body === undefined ? undefined : JSON.stringify(body) });
  }
  patch<T>(path: string, body?: unknown): Promise<T> { return this.request<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) }); }
  delete<T>(path: string): Promise<T> { return this.request<T>(path, { method: "DELETE" }); }
}

export const createIdempotencyKey = (): string => crypto.randomUUID();
