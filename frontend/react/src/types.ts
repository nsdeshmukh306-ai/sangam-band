export type Tier = "RED" | "YELLOW" | "GREEN";
export type JobStatus = "queued" | "running" | "complete" | "error" | "timeout";

export interface CaseMeta {
  id: string;
  title: string;
  expected_tier: Tier;
  drug: string | null;
  herb: string | null;
}

export interface Finding {
  summary: string;
  citation?: string;
  severity?: "high" | "moderate" | "low";
  drug?: string;
  herb?: string;
}

export interface Verdict {
  step?: string;
  status?: string;
  risk_tier?: Tier;
  confidence?: string;
  mechanism?: string;
  auc_pct_change?: number | null;
  delta_g_kcal_mol?: number | null;
  all_findings?: Finding[];
  rationale?: string;
  disclaimer?: string;
  run_id?: string;
}

export interface Job {
  job_id: string;
  case_id: string;
  status: JobStatus;
  run_id?: string | null;
  verdict?: Verdict | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WsEvent {
  event: "status" | "posted" | "verdict" | "error" | "timeout" | "done" | "ping";
  status?: string;
  run_id?: string;
  posted_at?: string;
  verdict?: Verdict;
  error?: string;
}

export interface ParseResult {
  matched_case_id: string | null;
  extracted: {
    drug?: string | null;
    herb?: string | null;
    age?: number | null;
    sex?: string | null;
    indication?: string | null;
    cyp2c9_genotype?: string | null;
    cyp3a4_status?: string | null;
    egfr?: number | null;
  };
  confidence: number;
  free_text_message: string | null;
}

export interface TranscriptMessage {
  id?: string;
  sender_name: string;
  sender_type?: string;
  content: string;
  inserted_at?: string | null;
  message_type?: string;
}

export interface HealthStatus {
  status: string;
  version?: string;
  band_room?: string;
  agents?: Record<string, boolean | string>;
}
