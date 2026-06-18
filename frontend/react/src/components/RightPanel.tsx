import { useCallback, useEffect, useRef, useState } from "react";
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { api } from "../api";
import type { Finding, TranscriptMessage, Verdict } from "../types";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

// ---- PK Curve Chart ----

function PKChart({ aucPctChange }: { aucPctChange?: number | null }) {
  if (aucPctChange == null) {
    return (
      <div style={{ padding: "16px", textAlign: "center", fontSize: "0.78rem", color: "var(--text-2)" }}>
        PK data unavailable for this case
      </div>
    );
  }

  // 1-compartment oral model: C(t) = D*F*ka/(Vd*(ka-ke)) * (e^-ke*t - e^-ka*t)
  const ka = 0.8, ke_base = 0.18;
  const scale = Math.max(0.2, 1 / (1 + aucPctChange / 100));
  const ke_inter = ke_base * scale;

  const model = (t: number, ke: number) => {
    if (Math.abs(ka - ke) < 0.001) return 0;
    return Math.max(0, 10 * (ka / (ka - ke)) * (Math.exp(-ke * t) - Math.exp(-ka * t)));
  };

  const N = 24, tMax = 24;
  const pts = Array.from({ length: N + 1 }, (_, i) => i * tMax / N);

  const base = pts.map((t) => model(t, ke_base));
  const inter = pts.map((t) => model(t, ke_inter));

  const interColor = aucPctChange > 0 ? "var(--danger)" : "var(--success)";
  const sign = aucPctChange > 0 ? "+" : "";

  return (
    <Line
      data={{
        labels: pts.map((t) => `${t}h`),
        datasets: [
          {
            label: "Baseline",
            data: base,
            borderColor: "#9CA3AF",
            borderDash: [6, 4],
            pointRadius: 0,
            borderWidth: 2,
            tension: 0.35,
          },
          {
            label: `Combined (${sign}${aucPctChange.toFixed(0)}% AUC)`,
            data: inter,
            borderColor: interColor,
            backgroundColor: interColor,
            pointRadius: 0,
            borderWidth: 3,
            tension: 0.35,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 18, color: "#6B7280", font: { size: 11, family: "Inter" } },
          },
          tooltip: { mode: "index", intersect: false },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#9CA3AF", maxTicksLimit: 7, font: { size: 10, family: "Inter" } },
            title: { display: true, text: "Time (0-24h)", color: "#6B7280", font: { size: 10, family: "Inter" } },
          },
          y: {
            border: { display: false },
            grid: { color: "#E5E7EB" },
            ticks: { color: "#9CA3AF", font: { size: 10, family: "Inter" } },
            title: { display: true, text: "Relative concentration", color: "#6B7280", font: { size: 10, family: "Inter" } },
          },
        },
      }}
    />
  );
}

// ---- Agent bubble ----

function agentClass(name: string): string {
  const known = ["Intake", "PatientProfile", "StructuralBio", "PKPD", "EvidenceRAG", "ComplianceGuard"];
  if (known.includes(name)) return name;
  if (name.toLowerCase().includes("human") || name.toLowerCase().includes("user")) return "human";
  return "unknown";
}

function avatarInitials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

function formatTs(ts: string | null | undefined): string {
  if (!ts) return "";
  try { return new Date(ts).toLocaleTimeString("en-US", { hour12: false }); } catch { return ""; }
}

// ---- RightPanel ----

interface Props {
  verdict: Verdict;
  onClose: () => void;
}

export default function RightPanel({ verdict, onClose }: Props) {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const fetchTranscript = useCallback(async () => {
    setLoadingTranscript(true);
    try {
      const data = await api.roomTranscript();
      setMessages(data.messages);
      setTimeout(() => {
        if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
      }, 50);
    } catch { /* ignore — Band room may be offline */ }
    finally { setLoadingTranscript(false); }
  }, []);

  useEffect(() => { fetchTranscript(); }, [fetchTranscript]);

  const tier = verdict.risk_tier ?? "YELLOW";

  const fmt = (n: number | null | undefined, d = 1) =>
    n == null ? "—" : n.toFixed(d);

  return (
    <>
      {/* Header with close */}
      <div className="rp-section-title">
        Analysis Detail
        <button className="btn-secondary" onClick={onClose} style={{ padding: "3px 10px", fontSize: "0.75rem" }}>
          ✕ Close
        </button>
      </div>

      {/* Verdict detail card */}
      <div className="vd-card">
        <div className={`vd-header ${tier}`}>
          <span className={`vd-tier ${tier}`}>{tier} RISK</span>
          {verdict.confidence && (
            <span style={{ fontSize: "0.75rem", color: "var(--text-2)" }}>
              Confidence: {verdict.confidence}
            </span>
          )}
        </div>
        <div className="vd-body">
          {(verdict.auc_pct_change != null || verdict.delta_g_kcal_mol != null) && (
            <div className="vd-metrics">
              {verdict.auc_pct_change != null && (
                <div>
                  <div className="vd-metric-label">AUC Change</div>
                  <div className="vd-metric-value">
                    {verdict.auc_pct_change > 0 ? "+" : ""}{fmt(verdict.auc_pct_change)}%
                  </div>
                </div>
              )}
              {verdict.delta_g_kcal_mol != null && (
                <div>
                  <div className="vd-metric-label">ΔG Binding</div>
                  <div className="vd-metric-value">{fmt(verdict.delta_g_kcal_mol)} kcal/mol</div>
                </div>
              )}
            </div>
          )}
          {verdict.mechanism && <div className="vd-mechanism">{verdict.mechanism}</div>}
          {verdict.rationale && (
            <div>
              <div className="vd-metric-label" style={{ marginBottom: 4 }}>Full Rationale</div>
              <div className="vd-rationale">{verdict.rationale}</div>
            </div>
          )}
          {verdict.disclaimer && (
            <div className="disclaimer">⚕️ {verdict.disclaimer}</div>
          )}
        </div>
      </div>

      {/* PK Curve */}
      <div>
        <div className="rp-section-title">PK Interaction Curve</div>
        <div className="pk-chart-wrap">
          <PKChart aucPctChange={verdict.auc_pct_change} />
        </div>
      </div>

      {/* Evidence */}
      {verdict.all_findings && verdict.all_findings.length > 0 && (
        <div>
          <div className="rp-section-title">Evidence Findings ({verdict.all_findings.length})</div>
          <table className="evidence-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Summary</th>
                <th>Citation</th>
              </tr>
            </thead>
            <tbody>
              {verdict.all_findings.map((f: Finding, i: number) => (
                <tr key={i}>
                  <td><span className={`sev-chip ${f.severity ?? "low"}`}>{f.severity ?? "low"}</span></td>
                  <td>{f.summary}</td>
                  <td className="evidence-citation">{f.citation ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Transcript */}
      <div>
        <div className="rp-section-title">
          Agent Transcript
          <button
            className="btn-secondary"
            onClick={fetchTranscript}
            disabled={loadingTranscript}
            style={{ padding: "2px 9px", fontSize: "0.7rem" }}
          >
            {loadingTranscript ? "…" : "↻"}
          </button>
        </div>

        {messages.length === 0 ? (
          <div style={{ fontSize: "0.78rem", color: "var(--text-2)", textAlign: "center", padding: "16px 0" }}>
            {loadingTranscript ? "Loading…" : "No messages yet"}
          </div>
        ) : (
          <div className="transcript-scroll" ref={transcriptRef}>
            {messages.map((m, i) => {
              const cls = agentClass(m.sender_name ?? "");
              return (
                <div key={m.id ?? i} className={`agent-bubble ${cls}`}>
                  <div className="agent-bubble-header">
                    <div className="agent-avatar">{avatarInitials(m.sender_name ?? "?")}</div>
                    <span className="agent-name">{m.sender_name ?? "Unknown"}</span>
                    <span className="agent-ts">{formatTs(m.inserted_at)}</span>
                  </div>
                  <div className="agent-content">{m.content}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
