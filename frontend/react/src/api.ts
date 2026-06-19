import type {
  CaseMeta,
  HealthStatus,
  InteractionScreenResult,
  Job,
  ParseResult,
  TranscriptMessage,
  WsEvent,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";
const WS_PROTO = location.protocol === "https:" ? "wss:" : "ws:";
export const WS_BASE = import.meta.env.VITE_API_URL
  ? (import.meta.env.VITE_API_URL as string).replace(/^http/, "ws")
  : `${WS_PROTO}//${location.host}`;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    req<HealthStatus>("/health"),

  listCases: () =>
    req<{ count: number; cases: CaseMeta[] }>("/api/cases/list"),

  parseCase: (text: string) =>
    req<ParseResult>("/api/cases/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),

  screenInteractions: (text: string) =>
    req<InteractionScreenResult>("/api/interactions/screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),

  runCase: (case_id: string, sample_message?: string) =>
    req<{ job_id: string; case_id: string; status: string }>("/api/cases/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id, ...(sample_message ? { sample_message } : {}) }),
    }),

  jobStatus: (job_id: string) =>
    req<Job>(`/api/cases/${job_id}/status`),

  listJobs: (limit = 20) =>
    req<{ jobs: Job[] }>(`/api/jobs?limit=${limit}`),

  roomTranscript: () =>
    req<{ count: number; messages: TranscriptMessage[] }>("/api/room/transcript"),
};

export function openJobWs(
  job_id: string,
  onEvent: (e: WsEvent) => void,
  onClose: () => void,
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/api/ws/${job_id}`);
  ws.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data as string) as WsEvent); } catch { /* ignore */ }
  };
  ws.onerror = () => onEvent({ event: "error", error: "WebSocket connection error" });
  ws.onclose = onClose;
  return ws;
}
