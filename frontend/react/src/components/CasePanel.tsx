import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useReconnectingWs } from "../hooks/useReconnectingWs";
import { useSpeechInput } from "../hooks/useSpeechInput";
import type { CaseMeta, Verdict, WsEvent } from "../types";

const AGENTS = ["Intake", "PatientProfile", "StructuralBio", "PKPD", "EvidenceRAG", "ComplianceGuard"];
const AGENT_LABELS = ["Intake", "Patient\nProfile", "Structural\nBio", "PK / PD", "Evidence\nRAG", "Compliance\nGuard"];
const POLL_INTERVAL_MS = 4000;
const TERMINAL = new Set(["complete", "error", "timeout"]);

const DEMO_CASES = [
  { id: "case_1_warfarin_guggulu",    label: "Anticoagulant" },
  { id: "case_7_atorvastatin_brahmi", label: "Statin" },
  { id: "case_8_amlodipine_arjuna",   label: "BP Med" },
  { id: "case_4_tacrolimus_sjw",      label: "Transplant" },
  { id: "case_14_amoxicillin_garlic", label: "Antibiotic" },
];

interface LogLine { ts: string; text: string; cls: string; }

// ---- Pipeline stepper ----

function PipelineStepper({ running, done }: { running: boolean; done: boolean }) {
  const [activeStep, setActiveStep] = useState(-1);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];

    if (!running) {
      setActiveStep(done ? AGENTS.length : -1);
      return;
    }

    setActiveStep(0);
    const delays = [12000, 25000, 40000, 55000, 70000];
    delays.forEach((d, i) => {
      timersRef.current.push(setTimeout(() => setActiveStep(i + 1), d));
    });
    return () => timersRef.current.forEach(clearTimeout);
  }, [running, done]);

  return (
    <div className="stepper">
      {AGENTS.map((agent, i) => {
        const isDone   = activeStep > i;
        const isActive = activeStep === i;
        return (
          <div key={agent} className={`step ${isDone ? "done" : isActive ? "active" : ""}`}>
            <div className="step-circle">
              {isDone    ? "✓"
               : isActive ? <span className="step-spinner" />
               : i + 1}
            </div>
            <div className="step-label">{AGENT_LABELS[i]}</div>
          </div>
        );
      })}
    </div>
  );
}

// ---- Verdict summary card ----

function VerdictSummary({ verdict }: { verdict: Verdict }) {
  const tier = verdict.risk_tier ?? "YELLOW";
  const ICON: Record<string, string> = { RED: "🔴", YELLOW: "🟡", GREEN: "🟢" };
  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : (n > 0 ? "+" : "") + n.toFixed(1);

  return (
    <div className="verdict-summary">
      <div className={`vs-header ${tier}`}>
        <span className={`vs-tier-badge ${tier}`}>
          {ICON[tier]} {tier} RISK
        </span>
        {verdict.confidence && (
          <span className="vs-confidence">Confidence: {verdict.confidence}</span>
        )}
      </div>
      <div className="vs-body">
        <div className="vs-metrics">
          {verdict.auc_pct_change != null && (
            <div>
              <div className="vs-metric-label">AUC Change</div>
              <div className="vs-metric-value">{fmt(verdict.auc_pct_change)}%</div>
            </div>
          )}
          {verdict.delta_g_kcal_mol != null && (
            <div>
              <div className="vs-metric-label">ΔG Binding</div>
              <div className="vs-metric-value">{verdict.delta_g_kcal_mol?.toFixed(1)} kcal/mol</div>
            </div>
          )}
        </div>
        {verdict.mechanism && <p className="vs-mechanism">{verdict.mechanism}</p>}
        <p className="disclaimer">
          ⚕️ {verdict.disclaimer ?? "For research purposes only. Not a substitute for clinical judgement."}
        </p>
      </div>
    </div>
  );
}

// ---- Main component ----

interface Props {
  onVerdictReceived: (v: Verdict) => void;
  onRunningChange:   (r: boolean) => void;
}

export default function CasePanel({ onVerdictReceived, onRunningChange }: Props) {
  const [cases, setCases]             = useState<CaseMeta[]>([]);
  const [inputText, setInputText]     = useState("");
  const [running, setRunning]         = useState(false);
  const [jobId, setJobId]             = useState<string | null>(null);
  const [wsPath, setWsPath]           = useState<string | null>(null);
  const [log, setLog]                 = useState<LogLine[]>([]);
  const [verdict, setVerdict]         = useState<Verdict | null>(null);
  const [stepperDone, setStepperDone] = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [wsMode, setWsMode]           = useState<"ws" | "poll">("ws");
  const [parsedMatch, setParsedMatch] = useState<string | null>(null);

  const logRef  = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const doneRef = useRef(false);
  const speechSeedRef = useRef("");

  const { listening, toggle: toggleMic } = useSpeechInput((text) => {
    const seed = speechSeedRef.current.trim();
    setInputText(seed ? `${seed} ${text}` : text);
  });

  const handleMicToggle = () => {
    if (!listening) speechSeedRef.current = inputText;
    toggleMic();
  };

  useEffect(() => {
    api.listCases().then((r) => setCases(r.cases)).catch(() => {});
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
    setWsPath(null);
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setRunning(false);
    setStepperDone(true);
    onRunningChange(false);
    if (v) { setVerdict(v); onVerdictReceived(v); }
    if (err) setError(err);
  }, [onRunningChange, onVerdictReceived]);

  const startPoll = useCallback((id: string) => {
    if (pollRef.current) return;
    addLog("↺ WS unavailable — switching to HTTP poll", "running");
    setWsMode("poll");
    pollRef.current = setInterval(async () => {
      try {
        const job = await api.jobStatus(id);
        if (!TERMINAL.has(job.status)) return;
        clearInterval(pollRef.current!); pollRef.current = null;
        if (job.status === "complete" && job.verdict) {
          addLog("✓ Verdict received (HTTP poll)", "verdict");
          finishJob(job.verdict);
        } else if (job.status === "error") {
          addLog(`Error: ${job.error}`, "error");
          finishJob(undefined, job.error ?? "Unknown error");
        } else {
          addLog("Timed out — no verdict within 180 s", "timeout");
          finishJob(undefined, "Analysis timed out.");
        }
      } catch { /* transient */ }
    }, POLL_INTERVAL_MS);
  }, [addLog, finishJob]);

  const handleWsEvent = useCallback((raw: unknown) => {
    const ev = raw as WsEvent;
    if (ev.event === "ping")    return;
    if (ev.event === "status")  addLog(`Status → ${ev.status}`, "running");
    if (ev.event === "posted")  addLog(`Case posted to Band room  [run_id=${ev.run_id}]`, "posted");
    if (ev.event === "verdict") {
      addLog("✓ Verdict received from ComplianceGuard", "verdict");
      finishJob(ev.verdict);
    }
    if (ev.event === "error")   { addLog(`Error: ${ev.error}`, "error"); finishJob(undefined, ev.error); }
    if (ev.event === "timeout") { addLog("Timed out — no verdict within 180 s", "timeout"); finishJob(undefined, "Analysis timed out."); }
  }, [addLog, finishJob]);

  const handleWsClose = useCallback(() => {
    if (!doneRef.current && jobId) startPoll(jobId);
  }, [jobId, startPoll]);

  const { readyState } = useReconnectingWs(wsPath, {
    maxRetries: 4, initialDelayMs: 1000,
    onMessage: handleWsEvent, onClose: handleWsClose,
  });

  useEffect(() => {
    if (readyState === "reconnecting") addLog("⟳ WebSocket reconnecting…", "running");
    if (readyState === "open" && wsMode === "poll") setWsMode("ws");
  }, [readyState]); // eslint-disable-line react-hooks/exhaustive-deps

  const startJob = async (caseId: string, sampleMessage?: string) => {
    doneRef.current = false;
    setRunning(true); setVerdict(null); setStepperDone(false);
    setError(null); setLog([]); setJobId(null); setWsPath(null); setWsMode("ws");
    onRunningChange(true);
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }

    try {
      addLog(`Posting case "${caseId}"…`, "running");
      const { job_id } = await api.runCase(caseId, sampleMessage);
      setJobId(job_id);
      addLog(`Job ${job_id} queued — opening WebSocket…`, "posted");
      setWsPath(`/api/ws/${job_id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addLog(`Failed to post: ${msg}`, "error");
      setError(msg); setRunning(false); setStepperDone(false); onRunningChange(false);
    }
  };

  const handleAnalyse = async () => {
    const text = inputText.trim();
    if (!text || running) return;

    try {
      setParsedMatch(null);
      addLog("Parsing case description…", "running");
      const parsed = await api.parseCase(text);
      if (parsed.matched_case_id) {
        const matchLabel = [parsed.extracted.drug, parsed.extracted.herb].filter(Boolean).join(" + ");
        if (parsed.confidence > 0.7 && matchLabel) setParsedMatch(matchLabel);
        addLog(`Matched: ${matchLabel || parsed.matched_case_id} (conf ${(parsed.confidence * 100).toFixed(0)}%)`, "posted");
        await startJob(parsed.matched_case_id);
      } else {
        const msg = parsed.free_text_message ?? text;
        addLog("No exact match — using free-text Band message", "running");
        await startJob("_free_text_", msg);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg); addLog(`Parse error: ${msg}`, "error");
    }
  };

  const handleDemoCase = async (caseId: string) => {
    if (running) return;
    const c = cases.find((c) => c.id === caseId);
    if (c) setInputText(`${c.drug ?? ""} and ${c.herb ?? ""} interaction`);
    await startJob(caseId);
  };

  const handleReset = () => {
    setVerdict(null); setError(null); setLog([]);
    setStepperDone(false); setInputText(""); setParsedMatch(null);
  };

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const showStepper = running || stepperDone;
  const showEmpty   = !running && !stepperDone && !verdict && !error && log.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>

      {/* NLP Input */}
      <div className="card">
        <div className="card-title">🔬 New Analysis</div>

        <div className="nlp-textarea-wrap">
          <textarea
            className="nlp-textarea"
            rows={4}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={running}
            placeholder={"Describe the case… e.g. My 65-year-old father takes Warfarin for his heart and started Guggulu supplements. Is this safe?"}
          />
          <button
            className={`mic-btn${listening ? " listening" : ""}`}
            onClick={handleMicToggle}
            title={listening ? "Stop recording" : "Start voice input (en-IN)"}
          >
            🎤
          </button>
        </div>

        {parsedMatch && (
          <div className="matched-badge">Matched: {parsedMatch}</div>
        )}

        {listening && (
          <div className="recording-indicator">
            <span className="recording-dot" /> Listening…
          </div>
        )}

        <div className="demo-cases">
          <span className="demo-label">Or try a demo →</span>
          {DEMO_CASES.map((d) => (
            <button key={d.id} className="demo-pill" onClick={() => handleDemoCase(d.id)} disabled={running}>
              {d.label}
            </button>
          ))}
        </div>

        <div className="nlp-actions">
          <button className="btn-primary" onClick={handleAnalyse} disabled={running || !inputText.trim()}>
            {running && <span className="spinner" />}
            {running ? "Analysing…" : "Analyse"}
          </button>
          {(verdict || error || stepperDone) && !running && (
            <button className="btn-secondary" onClick={handleReset}>New Case</button>
          )}
          {running && (
            <span style={{ fontSize: "0.75rem", color: "var(--text-2)" }}>
              {wsMode === "ws"
                ? readyState === "reconnecting" ? "⟳ reconnecting…" : "WS live"
                : "HTTP poll fallback"}
            </span>
          )}
        </div>
      </div>

      {/* Pipeline Stepper */}
      {showStepper && (
        <div className="card">
          <div className="card-title">Pipeline Progress</div>
          <PipelineStepper running={running} done={stepperDone} />
          {log.length > 0 && (
            <div className="log-stream" ref={logRef}>
              {log.map((l, i) => (
                <div key={i} className={`log-line ${l.cls}`}>
                  <span className="log-ts">{l.ts}</span>{l.text}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <div className="alert-error">⚠ {error}</div>}

      {verdict && <VerdictSummary verdict={verdict} />}

      {showEmpty && (
        <div className="empty-state">
          <div className="empty-icon">🧬</div>
          <p style={{ fontWeight: 600, marginBottom: 6 }}>Describe a drug–herb case above to begin</p>
          <p style={{ fontSize: "0.82rem" }}>
            The 6-agent Sangam pipeline evaluates the interaction and returns a safety tier
            with PK metrics, structural binding data, and evidence citations.
          </p>
        </div>
      )}
    </div>
  );
}
