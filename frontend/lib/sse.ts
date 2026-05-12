import { getApiToken } from "./api";

// Same-origin path — Next.js rewrites /api/* to the backend.
export function subscribeSSE(
  path: string,
  body: Record<string, unknown>,
  onEvent: (data: Record<string, unknown>) => void,
  onDone?: () => void
): () => void {
  const controller = new AbortController();

  (async () => {
    const token = await getApiToken();
    const res = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Reciter-Token": token,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!res.ok || !res.body) {
      onDone?.();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(data);
          } catch {
            // skip malformed JSON
          }
        }
      }
    }

    onDone?.();
  })().catch(() => onDone?.());

  return () => controller.abort();
}
