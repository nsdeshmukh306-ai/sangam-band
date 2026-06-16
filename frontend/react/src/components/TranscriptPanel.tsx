import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { TranscriptMessage } from "../types";

const AGENT_COLOR_CLASS: Record<string, string> = {
  Intake: "Intake",
  PatientProfile: "PatientProfile",
  StructuralBio: "StructuralBio",
  PKPD: "PKPD",
  EvidenceRAG: "EvidenceRAG",
  ComplianceGuard: "ComplianceGuard",
};

function agentClass(name: string): string {
  return AGENT_COLOR_CLASS[name] ?? (name.toLowerCase().includes("human") ? "human" : "unknown");
}

function formatTs(ts: string | null | undefined): string {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString("en-US", { hour12: false });
  } catch {
    return "";
  }
}

export default function TranscriptPanel() {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchTranscript = useCallback(async (auto = false) => {
    if (!auto) setLoading(true);
    setError(null);
    try {
      const data = await api.roomTranscript();
      setMessages(data.messages);
      setLastFetch(new Date().toLocaleTimeString("en-US", { hour12: false }));
      if (listRef.current) {
        setTimeout(() => {
          if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
        }, 50);
      }
    } catch (e) {
      setError(`Failed to fetch transcript: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      if (!auto) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTranscript();
    timerRef.current = setInterval(() => fetchTranscript(true), 10_000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [fetchTranscript]);

  return (
    <div className="card" style={{ minHeight: 300 }}>
      <div className="transcript-header">
        <h2>Live Band Room Transcript</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {lastFetch && <span className="refresh-note">Last refreshed {lastFetch} · auto-refresh 10 s</span>}
          <button className="btn-secondary" onClick={() => fetchTranscript()} disabled={loading}>
            {loading ? "Refreshing…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {error && <div className="alert-error">⚠ {error}</div>}

      {messages.length === 0 && !error && (
        <div className="empty-state">
          <div className="empty-icon">💬</div>
          <p>{loading ? "Loading transcript…" : "No messages yet in the Band room."}</p>
        </div>
      )}

      <div className="transcript-list" ref={listRef}>
        {messages.map((m, i) => {
          const cls = agentClass(m.sender_name ?? "");
          return (
            <div key={m.id ?? i} className="msg">
              <div className={`msg-bubble ${cls}`}>
                <div className="msg-sender">{m.sender_name ?? "Unknown"}</div>
                <div className="msg-content">{m.content}</div>
                {m.inserted_at && (
                  <div className="msg-time">{formatTs(m.inserted_at)}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
