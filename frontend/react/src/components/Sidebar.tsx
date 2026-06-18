import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { HealthStatus, Job, Tier } from "../types";

const AGENTS = ["Intake", "PatientProfile", "StructuralBio", "PKPD", "EvidenceRAG", "ComplianceGuard"];
const AGENT_SHORT: Record<string, string> = {
  Intake: "IN", PatientProfile: "PP", StructuralBio: "SB",
  PKPD: "PK", EvidenceRAG: "ER", ComplianceGuard: "CG",
};

function relTime(iso: string): string {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    return `${Math.round(diff / 3600)}h ago`;
  } catch { return ""; }
}

function tierLabel(job: Job): { tier: Tier | "pending"; label: string } {
  const t = job.verdict?.risk_tier;
  if (t) return { tier: t, label: t };
  if (job.status === "running") return { tier: "pending", label: "…" };
  if (job.status === "error") return { tier: "pending", label: "ERR" };
  return { tier: "pending", label: "—" };
}

interface Props {
  jobs: Job[];
  isRunning: boolean;
  onNewAnalysis: () => void;
}

export default function Sidebar({ jobs, isRunning, onNewAnalysis }: Props) {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    let alive = true;

    const pollHealth = async () => {
      try {
        const next = await api.health();
        if (!alive) return;
        setHealth(next);
        setHealthError(false);
      } catch {
        if (!alive) return;
        setHealthError(true);
      }
    };

    pollHealth();
    const id = window.setInterval(pollHealth, 30000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  const agentStates = useMemo(() => {
    const explicit = health?.agents;
    return AGENTS.reduce<Record<string, boolean>>((acc, agent) => {
      if (explicit && agent in explicit) {
        const value = explicit[agent];
        acc[agent] = value === true || value === "ok" || value === "alive" || value === "running";
      } else {
        acc[agent] = !healthError && health?.status === "ok";
      }
      return acc;
    }, {});
  }, [health, healthError]);

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-row">
          <span className="sidebar-logo-icon">⚕️</span>
          <div>
            <h1>Sangam</h1>
            <p>Polypharmacy Safety Council</p>
          </div>
        </div>
      </div>

      <button className="sidebar-new-btn" onClick={onNewAnalysis}>
        + New Analysis
      </button>

      <div className="sidebar-section-label">Recent Analyses</div>

      <div className="sidebar-jobs">
        {jobs.length === 0 ? (
          <div className="sidebar-empty">No analyses yet</div>
        ) : (
          jobs.map((job) => {
            const { tier, label } = tierLabel(job);
            const drugHerb = job.case_id
              .replace("_free_text_", "Free text")
              .replace(/^case_\d+_/, "")
              .replace(/_/g, " + ")
              .replace(/\b\w/g, (c) => c.toUpperCase());
            return (
              <div key={job.job_id} className="sidebar-job-item">
                <span className={`sj-tier-pill ${tier}`}>{label}</span>
                <div className="sj-info">
                  <div className="sj-drug">{drugHerb}</div>
                  <div className="sj-time">{relTime(job.created_at)}</div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="sidebar-status">
        <div className="sidebar-status-title">Agent Pipeline</div>
        <div className="agent-dots">
          {AGENTS.map((a) => (
            <div key={a} className="agent-dot-item">
              <span className={`status-dot ${agentStates[a] ? "green" : "red"} ${isRunning ? "live" : ""}`} />
              {AGENT_SHORT[a]}
            </div>
          ))}
        </div>
        <div className={`health-copy ${healthError ? "down" : ""}`}>
          {healthError ? "Health unavailable" : `Health ${health?.status ?? "checking"}`}
        </div>
      </div>
    </aside>
  );
}
