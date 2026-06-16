import { useState } from "react";
import CasePanel from "./components/CasePanel";
import JobHistory from "./components/JobHistory";
import TranscriptPanel from "./components/TranscriptPanel";

type Tab = "submit" | "transcript" | "history";

export default function App() {
  const [tab, setTab] = useState<Tab>("submit");

  return (
    <div className="app">
      <header className="header">
        <span className="header-icon">💊</span>
        <div>
          <h1>Sangam — Polypharmacy Safety Council</h1>
          <p>6-agent Band pipeline · Indian drug-herb interaction assessment · Band of Agents Hackathon</p>
        </div>
      </header>

      <nav className="tabs">
        <button className={`tab${tab === "submit" ? " active" : ""}`} onClick={() => setTab("submit")}>
          Submit Case
        </button>
        <button className={`tab${tab === "transcript" ? " active" : ""}`} onClick={() => setTab("transcript")}>
          Agent Workspace
        </button>
        <button className={`tab${tab === "history" ? " active" : ""}`} onClick={() => setTab("history")}>
          Job History
        </button>
      </nav>

      {tab === "submit" && <CasePanel />}
      {tab === "transcript" && <TranscriptPanel />}
      {tab === "history" && <JobHistory />}
    </div>
  );
}
