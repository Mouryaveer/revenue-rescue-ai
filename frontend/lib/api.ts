/**
 * API client — all dashboard data comes from real backend calls.
 * No hard-coded values, no mock responses used in production.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status}: ${err}`);
  }
  return res.json() as Promise<T>;
}

// ── Metrics ────────────────────────────────────────────────────────────────────
export const getMetricsOverview = (simulationRunId?: string) =>
  apiFetch<MetricsOverview>(
    `/metrics/overview${simulationRunId ? `?simulation_run_id=${simulationRunId}` : ""}`
  );

export const getBaselineComparison = (aiRunId: string, baselineRunId: string) =>
  apiFetch<BaselineComparison>(`/metrics/baseline-comparison?ai_run_id=${aiRunId}&baseline_run_id=${baselineRunId}`);

// ── Recovery Cases ─────────────────────────────────────────────────────────────
export const listRecoveryCases = (params?: {
  status?: string;
  scenario?: string;
  failure_reason?: string;
  limit?: number;
  offset?: number;
}) => {
  const q = new URLSearchParams(params as Record<string, string>).toString();
  return apiFetch<RecoveryCaseSummary[]>(`/recovery-cases${q ? `?${q}` : ""}`);
};

export const getRecoveryCase = (id: string) =>
  apiFetch<RecoveryCaseDetail>(`/recovery-cases/${id}`);

export const getAuditTrail = (caseId: string) =>
  apiFetch<AuditEvent[]>(`/recovery-cases/${caseId}/audit`);

export const runAgent = (caseId: string) =>
  apiFetch<{ status: string; message: string }>(`/recovery-cases/${caseId}/run`, { method: "POST" });

export const escalateCase = (caseId: string, reason?: string) =>
  apiFetch<{ status: string }>(`/recovery-cases/${caseId}/escalate?reason=${encodeURIComponent(reason ?? "Manual escalation")}`, { method: "POST" });

// ── Events ─────────────────────────────────────────────────────────────────────
export const ingestPaymentFailed = (event: PaymentFailedEventPayload) =>
  apiFetch<EventResponse>("/events/payment-failed", { method: "POST", body: JSON.stringify(event) });

export const ingestCheckoutAbandoned = (event: CheckoutAbandonedEventPayload) =>
  apiFetch<EventResponse>("/events/checkout-abandoned", { method: "POST", body: JSON.stringify(event) });

// ── Policies ───────────────────────────────────────────────────────────────────
export const listPolicies = () => apiFetch<PolicyRecord[]>("/policies");
export const getActivePolicy = () => apiFetch<PolicyRecord>("/policies/active");

// ── Simulation ─────────────────────────────────────────────────────────────────
export const startSimulation = (req: SimulationRequest) =>
  apiFetch<SimulationRunResponse>("/simulation/run", { method: "POST", body: JSON.stringify(req) });

export const getSimulation = (id: string) => apiFetch<SimulationRunRecord>(`/simulation/${id}`);
export const listSimulations = () => apiFetch<SimulationRunRecord[]>("/simulation");

// ── Audit ──────────────────────────────────────────────────────────────────────
export const getGlobalAuditLog = (params?: { event_type?: string; limit?: number }) => {
  const q = new URLSearchParams(params as Record<string, string>).toString();
  return apiFetch<AuditEvent[]>(`/audit${q ? `?${q}` : ""}`);
};

// ── Types ──────────────────────────────────────────────────────────────────────
export interface MetricsOverview {
  revenue_at_risk_paise: number;
  revenue_recovered_paise: number;
  recovery_rate_pct: number;
  active_cases: number;
  escalated_cases: number;
  recovered_cases: number;
  failed_cases: number;
  policy_violations: number;
  avg_recovery_time_hours: number | null;
  total_cases: number;
  by_scenario: Record<string, ScenarioMetrics>;
  by_failure_reason: Record<string, FailureReasonMetrics>;
}

export interface ScenarioMetrics {
  total: number;
  recovered: number;
  revenue_at_risk: number;
  revenue_recovered: number;
}

export interface FailureReasonMetrics {
  total: number;
  recovered: number;
  revenue_at_risk: number;
  revenue_recovered: number;
}

export interface BaselineComparison {
  REVENUERESCUE_AI: RunMetrics;
  BASELINE: RunMetrics;
  improvement_pct: number;
  note: string;
}

export interface RunMetrics {
  run_id: string;
  revenue_recovered_paise: number;
  recovery_rate_pct: number;
  escalated_cases: number;
  policy_violations: number;
  total_cases: number;
}

export interface RecoveryCaseSummary {
  id: string;
  scenario: string;
  failure_reason: string;
  status: string;
  amount_at_risk_paise: number;
  amount_recovered_paise: number;
  currency: string;
  retry_count: number;
  communication_count: number;
  recovery_score: number | null;
  customer_id: string;
  is_recovered: boolean;
  is_stopped: boolean;
  created_at: string;
  updated_at: string;
}

export interface RecoveryCaseDetail extends RecoveryCaseSummary {
  transaction_id: string | null;
  subscription_id: string | null;
  checkout_session_id: string | null;
  diagnosis: Record<string, unknown> | null;
  strategy: Record<string, unknown> | null;
  policy_decision: string | null;
  escalation_reason: string | null;
  actions: unknown[];
  agent_runs: unknown[];
}

export interface AuditEvent {
  id: string;
  event_type: string;
  actor: string;
  amount_paise: number | null;
  policy_version: number | null;
  result: string | null;
  reason: string | null;
  transaction_id: string | null;
  created_at: string;
}

export interface PolicyRecord {
  policy_id: string;
  version: number;
  is_active: boolean;
  config: Record<string, unknown>;
}

export interface SimulationRequest {
  num_customers: number;
  num_events: number;
  failure_rate: number;
  random_seed: number;
  is_baseline: boolean;
  label: string;
}

export interface SimulationRunResponse {
  simulation_id: string;
  status: string;
  label: string;
  is_baseline: boolean;
  num_events: number;
  random_seed: number;
  created_at: string;
}

export interface SimulationRunRecord extends SimulationRunResponse {
  progress_pct: number;
  recovery_rate_pct: number;
  revenue_at_risk_paise: number;
  revenue_recovered_paise: number;
  total_cases: number;
  recovered_cases: number;
  escalated_cases: number;
  policy_violations: number;
  results: Record<string, unknown> | null;
}

export interface PaymentFailedEventPayload {
  idempotency_key: string;
  customer_id: string;
  amount_paise: number;
  currency: string;
  failure_reason: string;
  failure_message?: string;
}

export interface CheckoutAbandonedEventPayload {
  idempotency_key: string;
  customer_id: string;
  checkout_session_id: string;
  amount_paise: number;
  currency: string;
}

export interface EventResponse {
  recovery_case_id: string;
  status: string;
  message: string;
  is_duplicate: boolean;
}

/** Convert paise to formatted INR string */
export function formatINR(paise: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
  }).format(paise / 100);
}
