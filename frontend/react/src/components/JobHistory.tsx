import { useEffect, useState } from "react";
import { api } from "../api";
import type { Job, Tier } from "../types";

const TIER_ICON: Record<Tier, string> = { RED: "🔴", YELLOW: "🟡", GREEN: "🟢" };

function relTime(iso: string): string {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    return `${Math.round(diff / 3600)}h ago`;
  } catch {
    return iso;
  }
}

function JobDetail({ job }: { job: Job }) {
  const v = job.verdict;
  const tier = v?.risk_tier;
  return (
    <div style={{ padding: "14px 16px", background: "#f8fafc", borderRadius: 8, marginTop: 6, fontSize: "0.875rem" }}>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 10 }}>
        <span><strong>Job:</strong> <code style={{ fontSize: "0.8rem" }}>{job.job_id}</code></span>
        {job.run_id && <span><strong>Run:</strong> <code style={{ fontSize: "0.8rem" }}>{job.run_id}</code></span>}
        <span><strong>Case:</strong> {job.case_id}</span>
      </div>

      {job.status === "error" && (
        <div className="alert-error">⚠ {job.error}</div>
      )}
      {job.status === "timeout" && (
        <div className="alert-error">⚠ Analysis timed out — no verdict received within 180 s.</div>
      )}

      {v && tier && (
        <div className={`verdict-card ${tier}`} style={{ marginTop: 8 }}>
          <div className={`tier-badge ${tier}`}>
            {TIER_ICON[tier]} {tier} RISK
          </div>
          {v.confidence && <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: 8 }}>Confidence: {v.confidence}</p>}
          <div className="metrics">
            {v.auc_pct_change != null && (
              <div className="metric">
                <span className="metric-label">AUC Change</span>
                <span className="metric-value">{v.auc_pct_change > 0 ? "+" : ""}{v.auc_pct_change?.toFixed(1)}%</span>
              </div>
            )}
            {v.delta_g_kcal_mol != null && (
              <div className="metric">
                <span className="metric-label">ΔG</span>
                <span className="metric-value">{v.delta_g_kcal_mol?.toFixed(1)} kcal/mol</span>
              </div>
            )}
          </div>
          {v.mechanism && <p className="mechanism">{v.mechanism}</p>}
        </div>
      )}
    </div>
  );
}

export default function JobHistory() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const reload = () => {
    setLoading(true);
    api.listJobs(30)
      .then((r) => { setJobs(r.jobs); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);

  const toggle = (id: string) => setExpanded((prev) => (prev === id ? null : id));

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h2>Job History</h2>
        <button className="btn-secondary" onClick={reload} disabled={loading}>
          {loading ? "Loading…" : "↻ Refresh"}
        </button>
      </div>

      {error && <div className="alert-error">⚠ {error}</div>}

      {jobs.length === 0 && !loading && !error && (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <p>No jobs yet. Submit a case to get started.</p>
        </div>
      )}

      <div className="jobs-list">
        {jobs.map((job) => {
          const tier = job.verdict?.risk_tier;
          return (
            <div key={job.job_id}>
              <div className="job-row" onClick={() => toggle(job.job_id)}>
                <div className="job-left">
                  <span className="job-id-text">{job.job_id.slice(0, 8)}</span>
                  <span className="job-title">{job.case_id.replace("case_", "Case ").replace(/_/g, " + ").replace(/(\d+)\s/, "$1: ")}</span>
                  <span className="job-time">{relTime(job.created_at)}</span>
                </div>
                <div className="job-right">
                  {tier && <div className={`tier-pip ${tier}`} title={tier} />}
                  <span className={`status-badge ${job.status}`}>{job.status}</span>
                  <span style={{ color: "var(--muted)", fontSize: "1rem" }}>
                    {expanded === job.job_id ? "▲" : "▼"}
                  </span>
                </div>
              </div>
              {expanded === job.job_id && <JobDetail job={job} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
