// Local dev uses the Vite proxy (relative "/api/v1"); production reads VITE_API_BASE
// (e.g. https://apaar-sathi-api.vercel.app) and appends /api/v1.
const API_ROOT = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
const BASE = `${API_ROOT}/api/v1`;

let token: string | null = localStorage.getItem("apaar_token");

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem("apaar_token", t);
  else localStorage.removeItem("apaar_token");
}

export function getToken() {
  return token;
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = body?.error?.message || res.statusText;
    throw new Error(msg);
  }
  return body as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; role: string; user_id: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<{ user_id: string; role: string; scope_ids: string[] }>("/auth/me"),

  linkagePairs: () => request<LinkageResponse>("/linkage/pairs"),
  pairEvidence: (a: string, b: string) =>
    request<PairEvidence>(`/linkage/pairs/evidence?record_a=${a}&record_b=${b}`),
  timeline: (a: string, b: string) =>
    request<TimelineResponse>(`/identity-clusters/timeline?record_a=${a}&record_b=${b}`),
  intake: () => request<{ results: IntakeResult[] }>("/intake/results"),
  benchmark: () => request<BenchmarkData>("/analytics/benchmark"),

  privacyProof: () => request<PrivacyProof>("/privacy/proof"),
  auditVerify: () => request<AuditResult>("/audit/verify"),

  reveals: () => request<RevealItem[]>("/reveals"),
  createReveal: (record_id: string, purpose: string, purpose_detail: string) =>
    request<{ id: string; status: string }>("/reveals", {
      method: "POST",
      body: JSON.stringify({ record_id, purpose, purpose_detail }),
    }),
  approveReveal: (id: string) =>
    request<{ id: string; status: string; expires_at: string }>(`/reveals/${id}/approve`, {
      method: "POST",
    }),
  consumeReveal: (id: string) =>
    request<{ name: string; apaar: string; expires_at: string }>(`/reveals/${id}/consume`, {
      method: "POST",
    }),
};

// ---- types ----
export interface EvidenceItem {
  comparison: string;
  level: string;
  weight: number;
  direction: "up" | "down" | "neutral";
}
export interface PairEvidence {
  record_a: string;
  record_b: string;
  masked_a: string;
  masked_b: string;
  total_weight: number;
  probability: number;
  band: string;
  evidence: EvidenceItem[];
  exact_token_repeat: boolean;
  baseline1_match?: boolean;
  baseline2_match?: boolean;
  baseline_false_positive?: boolean;
  model_version: string;
}
export interface LinkageResponse {
  pairs: PairEvidence[];
  true_duplicates: PairEvidence[];
  baseline_false_positives: PairEvidence[];
  candidate_count: number;
  block_warnings: { block_key_class: string; size: number }[];
}
export interface TimelineBar {
  episode_id: string;
  institution: string;
  start: string;
  end: string | null;
  status: string;
  transfer_from: string | null;
}
export interface TimelineFinding {
  rule_code: string;
  severity: string;
  rule_version: number;
  evidence: Record<string, unknown>;
}
export interface TimelineResponse {
  bars: TimelineBar[];
  findings: TimelineFinding[];
}
export interface IntakeResult {
  status: string;
  rule_code: string | null;
  institution: string;
  institution_name?: string;
  program: string;
  academic_year: string;
  category: string | null;
  numerator: number;
  limit: number | null;
  effective_limits_seen?: number[];
  approval_reference?: string;
  rule_version: number;
  reason?: string;
  contributing_masked_ids?: string[];
}
export interface BenchmarkData {
  n_records: number;
  candidate_pairs: number;
  modes: Record<string, { precision: number; recall: number; f1: number; false_positive_rate: number }>;
  pr_curve_model: { threshold: number; precision: number; recall: number }[];
  runtime: { blocking_seconds: number; scoring_seconds: number; peak_memory_mb: number };
}
export interface PrivacyProof {
  passed: boolean;
  canaries_used: number;
  checks: { target: string; hits: string[]; pass: boolean; rows_scanned?: number; files_scanned?: number }[];
}
export interface AuditResult {
  valid: boolean;
  events?: number;
  first_mismatch_seq?: number;
  expected_hash?: string;
  stored_hash?: string;
}
export interface RevealItem {
  id: string;
  record_id: string;
  purpose: string;
  status: string;
  requester_id: string;
  approver_id: string | null;
  expires_at: string | null;
  consumed_at: string | null;
}
