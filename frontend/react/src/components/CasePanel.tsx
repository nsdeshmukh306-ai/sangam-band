import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useReconnectingWs } from "../hooks/useReconnectingWs";
import type { CaseMeta, Finding, Job, Tier, Verdict, WsEvent } from "../types";

const TIER_ICON: Record<Tier, string> = { RED: "🔴", YELLOW: "🟡", GREEN: "🟢" };
const AGENTS = ["Intake", "PatientProfile", "StructuralBio", "PKPD", "EvidenceRAG", "ComplianceGuard"];
const POLL_INTERVAL_MS = 4000;
const TERMINAL = new Set(["complete", "error", "timeout"]);

interface LogLine { ts: string; text: string; cls: string; }
interface SeenAgents { [k: string]: boolean; }

function fmt(n: number | null | undefined, d = 1) { return n == null ? "—" : n.toFixed(d); }

function VerdictCard({ verdict }: { verdict: Verdict }) {
  const tier = verdict.risk_tier ?? "YELLOW";
  return (
    <div className={`verdict-card ${tier}`}>
      <div className={`tier-badge ${tier}`}>
        <span className="tier-icon">{TIER_ICON[tier]}</span>
        {tier} RISK
      </div>
      {verdict.confidence && <p className="section-label">Confidence: {verdict.confidence}</p>}
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
      {verdict.mechanism && <p className="mechanism">{verdict.mechanism}</p>}
      {verdict.all_findings && verdict.all_findings.length > 0 && (
        <details className="findings-detail">
          <summary>Evidence findings ({verdict.all_findings.length})</summary>
          <table className="findings-table">
            <thead>
              <tr><th>Severity</th><th>Summary</th><th>Citation</th></tr>
            </thead>
            <tbody>
              {verdict.all_findings.map((f: Finding, i: number) => (
                <tr key={i}>
                  <td><span className={`sev ${f.severity ?? "low"}`}>{f.severity ?? "low"}</span></td>
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
  const [jobId, setJobId] = useState<string | null>(null);
  const [wsPath, setWsPath] = useState<string | null>(null);
  const [log, setLog] = useState<LogLine[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seenAgents, setSeenAgents] = useState<SeenAgents>({});
  const [wsMode, setWsMode] = useState<"ws" | "poll">("ws");
  const logRef = useRef<HTMLDivElement>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const doneRef = useRef(false);

  useEffect(() => {
    api.listCases()
      .then((r) => { setCases(r.cases); if (r.cases.length > 0) setSelectedId(r.cases[0].id); })
      .catch(() => setError("Could not load cases — is the backend running on :8000?"));
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  const addLog = useCallback((text: string, cls: string) => {
    const ts = new Date().toLocaleTimeString("en-US", { hour12: false });
    setLog((l) => [...l, { ts, text, cls }]);
  }, []);

  const finishJob = useCallback((v?: Verdict, err?: string) => {
    if (doneRef.current) return;
    doneRef.current = true;
    setWsPath(null); // close WS
    if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }
    setRunning(false);
    if (v) setVerdict(v);
    if (err) setError(err);
  }, []);

  // HTTP fallback: poll /api/cases/{job_id}/status until terminal
  const startPollFallback = useCallback((id: string) => {
    if (pollTimerRef.current) return;
    addLog("↺ WS unavailable — switching to HTTP polling fallback", "running");
    setWsMode("poll");
    pollTimerRef.current = setInterval(async () => {
      try {
        const job: Job = await api.jobStatus(id);
        if (TERMINAL.has(job.status)) {
          clearInterval(pollTimerRef.current!);
          pollTimerRef.current = null;
          if (job.status === "complete" && job.verdict) {
            addLog("✓ Verdict received (HTTP poll)", "verdict");
            finishJob(job.verdict);
          } else if (job.status === "error") {
            addLog(`Error: ${job.error}`, "error");
            finishJob(undefined, job.error ?? "Unknown error");
          } else {
            addLog("Timed out — no verdict within 180 s", "timeout");
            finishJob(undefined, "Analysis timed out. Check that all 6 agents are running.");
          }
        }
      } catch { /* transient — keep polling */ }
    }, POLL_INTERVAL_MS);
  }, [addLog, finishJob]);

  // WS event handler
  const handleWsEvent = useCallback((raw: unknown) => {
    const ev = raw as WsEvent;
    if (ev.event === "ping") return;
    if (ev.event === "status") {
      addLog(`Status → ${ev.status}`, "running");
    } else if (ev.event === "posted") {
      addLog(`Case posted to Band room  [run_id=${ev.run_id}]`, "posted");
    } else if (ev.event === "verdict") {
      addLog("✓ Verdict received from ComplianceGuard", "verdict");
      setSeenAgents((p) => ({ ...p, ComplianceGuard: true }));
      finishJob(ev.verdict);
    } else if (ev.event === "error") {
      addLog(`Error: ${ev.error}`, "error");
      finishJob(undefined, ev.error ?? "Unknown error");
    } else if (ev.event === "timeout") {
      addLog("Timed out — no verdict within 180 s", "timeout");
      finishJob(undefined, "Analysis timed out. Check that all 6 agents are running.");
    }
    // "done" is handled by WS close
  }, [addLog, finishJob]);

  // When WS closes unexpectedly (not after "done"), switch to poll
  const handleWsClose = useCallback(() => {
    if (!doneRef.current && jobId) startPollFallback(jobId);
  }, [jobId, startPollFallback]);

  const { readyState } = useReconnectingWs(wsPath, {
    maxRetries: 4,
    initialDelayMs: 1000,
    onMessage: handleWsEvent,
    onClose: handleWsClose,
  });

  // Show reconnect state in log
  useEffect(() => {
    if (readyState === "reconnecting") addLog("⟳ WebSocket reconnecting…", "running");
    if (readyState === "open" && wsMode === "poll") setWsMode("ws");
  }, [readyState]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRun = async () => {
    if (!selectedId || running) return;

    // Reset state
    doneRef.current = false;
    setRunning(true);
    setVerdict(null);
    setError(null);
    setLog([]);
    setSeenAgents({});
    setJobId(null);
    setWsPath(null);
    setWsMode("ws");
    if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }

    try {
      addLog(`Posting case "${selectedId}"…`, "running");
      const { job_id } = await api.runCase(selectedId);
      setJobId(job_id);
      addLog(`Job ${job_id} queued — opening WebSocket…`, "posted");
      setWsPath(`/api/ws/${job_id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addLog(`Failed to post: ${msg}`, "error");
      setError(msg);
      setRunning(false);
    }
  };

  // Cleanup on unmount
  useEffect(() => () => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
  }, []);

  const selected = cases.find((c) => c.id === selectedId);

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
            {" · "}Expected:{" "}
            <span style={{ fontWeight: 700 }}>
              {TIER_ICON[selected.expected_tier]} {selected.expected_tier}
            </span>
            {running && (
              <span style={{ marginLeft: 10, fontSize: "0.78rem", color: "var(--muted)" }}>
                ({wsMode === "ws"
                  ? readyState === "reconnecting" ? "⟳ reconnecting…" : "WS live"
                  : "HTTP poll fallback"})
              </span>
            )}
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
          <p>Select a case study and click <strong>Run Analysis</strong>.</p>
          <p style={{ fontSize: "0.8rem", marginTop: 6, color: "var(--muted)" }}>
            The 6-agent Sangam pipeline evaluates the drug-herb interaction and returns a safety tier.
            Live updates stream via WebSocket with automatic reconnect fallback.
          </p>
        </div>
      )}
    </div>
  );
}
