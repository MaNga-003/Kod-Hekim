/**
 * Server-Sent Events client.
 *
 * Backend `sse-starlette` her event tipini ayrı bir `event:` field'ı ile
 * yayıyor (örn. `event: agent_started`). Bu nedenle her olası tip için
 * ayrı `addEventListener` kaydetmek gerekir.
 */

import { apiBase } from "./api-client";

export type SSEEventType =
  | "clone_started"
  | "clone_done"
  | "agent_started"
  | "agent_progress"
  | "issue_found"
  | "impact_calculated"
  | "fix_generated"
  | "agent_done"
  | "all_done"
  | "error"
  | "heartbeat";

export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

const EVENT_TYPES: SSEEventType[] = [
  "clone_started",
  "clone_done",
  "agent_started",
  "agent_progress",
  "issue_found",
  "impact_calculated",
  "fix_generated",
  "agent_done",
  "all_done",
  "error",
  "heartbeat",
];

/**
 * Verilen `jobId` için SSE bağlantısı aç.
 *
 * `onEvent` her event için tetiklenir. Dönen fonksiyon bağlantıyı kapatır
 * (effect cleanup için).
 */
export function streamEvents(
  jobId: string,
  onEvent: (ev: SSEEvent) => void,
  onError?: (e: Event) => void,
): () => void {
  const url = `${apiBase()}/api/analyze/${jobId}/stream`;
  const es = new EventSource(url);

  for (const t of EVENT_TYPES) {
    es.addEventListener(t, (raw: MessageEvent) => {
      let payload: { data: Record<string, unknown>; timestamp: string } = {
        data: {},
        timestamp: new Date().toISOString(),
      };
      try {
        payload = JSON.parse(raw.data);
      } catch {
        // heartbeat ya da bozuk frame — payload default kalır
      }
      onEvent({ type: t, data: payload.data ?? {}, timestamp: payload.timestamp });
    });
  }

  // Browser EventSource bağlantı koptuğunda otomatik reconnect yapar.
  // onError yalnızca bilgilendirme amaçlı; bağlantı readyState=CLOSED ise
  // tarayıcı yeniden bağlanmayı dener.
  es.onerror = (e) => {
    if (onError) onError(e);
  };

  return () => es.close();
}
