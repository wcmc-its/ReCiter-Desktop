// All /api/* requests go through the Next.js rewrite (see
// frontend/next.config.mjs) so the browser only talks to a single
// origin. The backend is never exposed directly to the host.
const TOKEN_HEADER = "X-Reciter-Token";

let _tokenPromise: Promise<string> | null = null;

export async function getApiToken(): Promise<string> {
  if (_tokenPromise) return _tokenPromise;
  _tokenPromise = (async () => {
    const res = await fetch("/api-auth/token", { cache: "no-store" });
    if (!res.ok) {
      _tokenPromise = null;
      const text = await res.text().catch(() => "");
      throw new Error(`Could not load API token (${res.status}): ${text}`);
    }
    const data = (await res.json()) as { token: string };
    return data.token;
  })();
  return _tokenPromise;
}

async function withToken(headers?: HeadersInit): Promise<HeadersInit> {
  const token = await getApiToken();
  return { ...(headers ?? {}), [TOKEN_HEADER]: token };
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = await withToken({ "Content-Type": "application/json", ...options?.headers });
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const headers = await withToken();
  const res = await fetch(path, {
    method: "POST",
    body: formData,
    headers,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload error ${res.status}: ${text}`);
  }
  return res.json();
}

export function apiExportUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  return url.toString();
}

export async function apiDownload(
  path: string,
  filename: string,
  params?: Record<string, string>
): Promise<void> {
  const url = apiExportUrl(path, params);
  const headers = await withToken();
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Download error ${res.status}: ${text}`);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objectUrl);
}
