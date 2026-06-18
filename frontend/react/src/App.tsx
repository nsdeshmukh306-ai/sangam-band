import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import CasePanel from "./components/CasePanel";
import RightPanel from "./components/RightPanel";
import Sidebar from "./components/Sidebar";
import type { Job, Verdict } from "./types";

export default function App() {
  const [verdict, setVerdict]       = useState<Verdict | null>(null);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [isRunning, setIsRunning]   = useState(false);

  const refreshJobs = useCallback(async () => {
    try {
      const { jobs } = await api.listJobs(10);
      setRecentJobs(jobs);
    } catch { /* backend may be offline */ }
  }, []);

  useEffect(() => { refreshJobs(); }, [refreshJobs]);

  const handleVerdictReceived = useCallback((v: Verdict) => {
    setVerdict(v);
    refreshJobs();
  }, [refreshJobs]);

  return (
    <div className="dashboard">
      <Sidebar
        jobs={recentJobs}
        isRunning={isRunning}
        onNewAnalysis={() => setVerdict(null)}
      />

      <main className="main-content">
        <CasePanel
          onVerdictReceived={handleVerdictReceived}
          onRunningChange={setIsRunning}
        />
      </main>

      <div className={`right-panel${verdict ? "" : " hidden"}`}>
        {verdict && (
          <RightPanel verdict={verdict} onClose={() => setVerdict(null)} />
        )}
      </div>
    </div>
  );
}
