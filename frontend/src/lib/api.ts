/// Minimal fetch wrapper around the versioned API.
const BASE = (import.meta.env.VITE_API_BASE as string) || "/api/v1";

const TOKEN_KEY = "3dulpin_token";
const USER_KEY = "3dulpin_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}
export function getUser(): unknown {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}
export function setUser(user: unknown) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}

export interface ApiOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = unknown>(
  path: string,
  opts: ApiOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers || {}),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(BASE + path, {
    method: opts.method || "GET",
    headers,
    body,
  });
  let data: unknown = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail =
      (data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : text) || res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export async function uploadPreview(file: File): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}/uploads/preview`, { method: "POST", headers, body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, (data as any).detail || "Upload failed");
  return data;
}
