import { useEffect, useRef, useState } from "react";
import { api, openJobWs } from "../api";
import type { CaseMeta, Finding, Tier, Verdict, WsEvent } from "../types";

const TIER_ICON: Record<Tier, string> = { RED: "🔴", YELLOW: "🟡", GREEN: "🟢" };
const AGENTS = ["Intake", "PatientProfile", "StructuralBio", "PKPD", "EvidenceRAG", "ComplianceGuard"];

interface LogLine {
  ts: string;
  text: string;
  cls: string;
}

interface SeenAgents {
  [key: string]: boolean;
}

function fmt(n: number | null | undefined, decimals = 1) {
  return n == null ? "—" : n.toFixed(decimals);
}

function VerdictCard({ verdict }: { verdict: Verdict }) {
  const tier = verdict.risk_tier ?? "YELLOW";
  return (
    <div className={`verdict-card ${tier}`}>
      <div className={`tier-badge ${tier}`}>
        <span className="tier-icon">{TIER_ICON[tier]}</span>
        {tier} RISK
      </div>
      {verdict.confidence && (
        <p className="section-label">Confidence: {verdict.confidence}</p>
      )}
      <div className="metrics">
        {verdict.auc_pct_change != null && (
          <div className="metric">
            <span className="metric-label">AUC Change</span>
            <span className="metric-value">
              {verdict.auc_pct_change > 0 ? "+" : ""}{fmt(verdict.auc_pct_change)}%
            </span>
          </div>
        )}
        {verdict.delta_g_kcal_mol != null && (
          <div className="metric">
            <span className="metric-label">ΔG Binding</span>
            <span className="metric-value">{fmt(verdict.delta_g_kcal_mol)} kcal/mol</span>
          </div>
        )}
      </div>
      {verdict.mechanism && (
        <p className="mechanism">{verdict.mechanism}</p>
      )}
      {verdict.all_findings && verdict.all_findings.length > 0 && (
        <details className="findings-detail">
          <summary>Evidence findings ({verdict.all_findings.length})</summary>
          <table className="findings-table">
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
                  <td>
                    <span className={`sev ${f.severity ?? "low"}`}>
                      {f.severity ?? "low"}
                    </span>
                  </td>
                  <td>{f.summary}</td>
                  <td style={{ color: "var(--muted)", fontSize: "0.78rem" }}>{f.citation ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      {verdict.rationale && (
        <details className="findings-detail" style={{ marginTop: 10 }}>
          <summary>Full rationale</summary>
          <p style={{ marginTop: 8, fontSize: "0.875rem", lineHeight: 1.6 }}>{verdict.rationale}</p>
        </details>
      )}
      <p className="disclaimer">
        ⚕️ {verdict.disclaimer ?? "For informational/research purposes only. Not a substitute for clinical judgement."}
      </p>
    </div>
  );
}

export default function CasePanel() {
  const [cases, setCases] = useState<CaseMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<LogLine[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seenAgents, setSeenAgents] = useState<SeenAgents>({});
  const logRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    api.listCases().then((r) => {
      setCases(r.cases);
      if (r.cases.length > 0) setSelectedId(r.cases[0].id);
    }).catch(() => setError("Could not load cases — is the backend running?"));
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  const addLog = (text: string, cls: string) => {
    const ts = new Date().toLocaleTimeString("en-US", { hour12: false });
    setLog((l) => [...l, { ts, text, cls }]);
  };

  const selected = cases.find((c) => c.id === selectedId);

  const handleRun = async () => {
    if (!selectedId || running) return;
    setRunning(true);
    setVerdict(null);
    setError(null);
    setLog([]);
    setSeenAgents({});

    try {
      addLog(`Posting case "${selectedId}"…`, "running");
      const { job_id } = await api.runCase(selectedId);
      addLog(`Job ${job_id} created — waiting for agents…`, "posted");

      wsRef.current?.close();
      wsRef.current = openJobWs(
        job_id,
        (ev: WsEvent) => {
          if (ev.event === "ping") return;
          if (ev.event === "status") {
            addLog(`Status → ${ev.status}`, "running");
          } else if (ev.event === "posted") {
            addLog(`Case posted to Band room [run_id=${ev.run_id}]`, "posted");
          } else if (ev.event === "verdict") {
            addLog("✓ Verdict received from ComplianceGuard", "verdict");
            setVerdict(ev.verdict ?? null);
            setSeenAgents((prev) => ({ ...prev, ComplianceGuard: true }));
          } else if (ev.event === "error") {
            addLog(`Error: ${ev.error}`, "error");
            setError(ev.error ?? "Unknown error");
          } else if (ev.event === "timeout") {
            addLog("Timed out — no verdict within 180 s", "timeout");
            setError("Analysis timed out. Check that all 6 agents are running.");
          } else if (ev.event === "done") {
            setRunning(false);
          }
        },
        () => setRunning(false),
      );
    } catch (e) {
      addLog(`Failed: ${e instanceof Error ? e.message : String(e)}`, "error");
      setError(String(e));
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="card">
        <h2>Submit Case for Analysis</h2>
        <div className="form-row">
          <div className="form-group">
            <label>Case Study</label>
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} disabled={running}>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {TIER_ICON[c.expected_tier]} {c.title}
                </option>
              ))}
            </select>
          </div>
          <button className="btn-primary" onClick={handleRun} disabled={running || !selectedId}>
            {running && <span className="spinner" />}
            {running ? "Analysing…" : "Run Analysis"}
          </button>
        </div>

        {selected && (
          <div className="case-desc">
            <strong>{selected.drug ?? "—"}</strong> + <strong>{selected.herb ?? "—"}</strong>
            {" · "}Expected tier:{" "}
            <span style={{ fontWeight: 700 }}>
              {TIER_ICON[selected.expected_tier]} {selected.expected_tier}
            </span>
          </div>
        )}

        {running && (
          <div className="pipeline">
            {AGENTS.map((a) => (
              <span key={a} className={`p-agent${seenAgents[a] ? " seen" : ""}`}>
                <span className="p-icon">{seenAgents[a] ? "✅" : "⏳"}</span>
                {a}
              </span>
            ))}
          </div>
        )}

        {log.length > 0 && (
          <div className="log-stream" ref={logRef}>
            {log.map((l, i) => (
              <div key={i} className={`log-line ${l.cls}`}>
                <span className="log-ts">{l.ts}</span>{l.text}
              </div>
            ))}
          </div>
        )}

        {error && <div className="alert-error">⚠ {error}</div>}
      </div>

      {verdict && <VerdictCard verdict={verdict} />}

      {!verdict && !running && log.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">🔬</div>
          <p>Select a case study and click <strong>Run Analysis</strong> to start.</p>
          <p style={{ fontSize: "0.8rem", marginTop: 6, color: "var(--muted)" }}>
            The 6-agent Sangam pipeline will evaluate the drug-herb interaction and return a safety tier.
          </p>
        </div>
      )}
    </div>
  );
}
