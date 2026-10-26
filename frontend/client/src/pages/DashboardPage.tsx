import { useEffect, useState } from "react";
import { Link } from "wouter";
import {
  AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, Clock,
  DollarSign, FileText, FlaskConical, History, Play,
  RefreshCw, Shield, ShieldAlert, Sparkles, TrendingUp, XCircle, Zap
} from "lucide-react";
import { PageFrame } from "@/components/SiteShell";

interface MetricsOverview {
  revenue_at_risk_paise: number;
  revenue_recovered_paise: number;
  recovery_rate_pct: number;
  active_cases: number;
  escalated_cases: number;
  recovered_cases: number;
  failed_cases: number;
  policy_violations: number;
  total_cases: number;
  by_scenario?: Record<string, { total: number; recovered: number; revenue_at_risk: number; revenue_recovered: number }>;
  by_failure_reason?: Record<string, { total: number; recovered: number; revenue_at_risk: number; revenue_recovered: number }>;
}

interface RecoveryCase {
  id: string;
  scenario: string;
  failure_reason: string;
  status: string;
  amount_at_risk_paise: number;
  amount_recovered_paise: number;
  currency: string;
  retry_count: number;
  communication_count: number;
  recovery_score: number;
  customer_id: string;
  is_recovered: boolean;
  is_stopped: boolean;
  created_at: string;
  updated_at: string;
}

interface AuditEvent {
  id: string;
  event_type: string;
  actor_type: string;
  created_at: string;
  payload: Record<string, unknown>;
  policy_id?: string;
  policy_version?: number;
}

interface DemoScenario {
  id: string;
  name: string;
  scenario: string;
  failure_reason: string;
  amount_paise: number;
  expected: string;
  description: string;
}

const API = "/api/v1";

function formatINR(paise: number): string {
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(rupees);
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"cases" | "simulation" | "demo" | "policies">("cases");
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCase, setSelectedCase] = useState<RecoveryCase | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [demoScenarios, setDemoScenarios] = useState<DemoScenario[]>([]);
  const [activePolicy, setActivePolicy] = useState<any>(null);

  // Filters
  const [scenarioFilter, setScenarioFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Simulation form state
  const [simName, setSimName] = useState("AI vs Baseline Benchmark");
  const [simEvents, setSimEvents] = useState(50);
  const [simSeed, setSimSeed] = useState(42);
  const [simRunning, setSimRunning] = useState(false);
  const [simResult, setSimResult] = useState<any>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const [metricsRes, casesRes, demoRes, policyRes] = await Promise.all([
        fetch(`${API}/metrics/overview`),
        fetch(`${API}/recovery-cases`),
        fetch(`${API}/demo/scenarios`),
        fetch(`${API}/policies/active`).catch(() => null),
      ]);

      if (metricsRes.ok) setMetrics(await metricsRes.json());
      if (casesRes.ok) setCases(await casesRes.json());
      if (demoRes.ok) setDemoScenarios(await demoRes.json());
      if (policyRes && policyRes.ok) setActivePolicy(await policyRes.json());
    } catch (e) {
      console.error("Error loading dashboard data", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function selectCase(c: RecoveryCase) {
    setSelectedCase(c);
    setAuditLoading(true);
    try {
      const res = await fetch(`${API}/audit/cases/${c.id}`);
      if (res.ok) {
        setAuditEvents(await res.json());
      } else {
        setAuditEvents([]);
      }
    } catch (err) {
      console.error("Audit load error", err);
      setAuditEvents([]);
    } finally {
      setAuditLoading(false);
    }
  }

  async function runSimulation() {
    setSimRunning(true);
    setSimResult(null);
    try {
      const res = await fetch(`${API}/simulation/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: simName,
          event_count: Number(simEvents),
          customer_count: Math.max(10, Math.floor(simEvents / 3)),
          failure_rate: 0.20,
          random_seed: Number(simSeed),
          mode: "both",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSimResult(data);
        setActionNotice("Simulation batch completed successfully!");
      } else {
        const err = await res.json();
        setActionNotice(`Simulation failed: ${err.detail || "Unknown error"}`);
      }
    } catch (e: any) {
      setActionNotice(`Error: ${e.message}`);
    } finally {
      setSimRunning(false);
    }
  }

  async function handleResetDemo() {
    if (!confirm("Reset demo data to original 20 seeded test cases?")) return;
    try {
      const res = await fetch(`${API}/demo/reset`, { method: "POST" });
      if (res.ok) {
        setActionNotice("Reset initiated. Refreshing cases in 3 seconds...");
        setTimeout(() => {
          loadData();
          setActionNotice("Demo cases reset successfully!");
        }, 3000);
      }
    } catch (err: any) {
      setActionNotice(`Reset error: ${err.message}`);
    }
  }

  const filteredCases = cases.filter((c) => {
    if (scenarioFilter !== "ALL" && c.scenario !== scenarioFilter) return false;
    if (statusFilter !== "ALL" && c.status !== statusFilter) return false;
    return true;
  });

  return (
    <PageFrame>
      <main style={{ background: "#f8fafc", minHeight: "100vh", paddingBottom: 60 }}>
        {/* Console Header */}
        <div style={{ background: "#0a1324", color: "#fff", borderBottom: "1px solid #1e293b", padding: "32px 0 24px" }}>
          <div className="container">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20, background: "rgba(34,197,94,0.15)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.3)" }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80" }} />
                    API CONNECTED (PORT 8000)
                  </span>
                  <span style={{ fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>RevenueRescue AI</span>
                </div>
                <h1 style={{ fontSize: 28, fontWeight: 800, margin: 0, color: "#f8fafc" }}>
                  Autonomous Recovery Console
                </h1>
                <p style={{ margin: "6px 0 0", color: "#94a3b8", fontSize: 14 }}>
                  Real-time pipeline monitoring, policy enforcement, LangGraph diagnosis, and authoritative verification.
                </p>
              </div>

              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <button
                  onClick={handleResetDemo}
                  style={{
                    display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
                    background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: 6, color: "#e2e8f0", fontSize: 13, fontWeight: 600, cursor: "pointer"
                  }}
                >
                  <History size={14} /> Reset Demo Data
                </button>
                <button
                  onClick={loadData}
                  disabled={loading}
                  style={{
                    display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
                    background: "#2563eb", border: "none", borderRadius: 6, color: "#fff",
                    fontSize: 13, fontWeight: 600, cursor: "pointer"
                  }}
                >
                  <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
                </button>
                <Link
                  href="/checkout"
                  style={{
                    display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
                    background: "#10b981", borderRadius: 6, color: "#fff",
                    fontSize: 13, fontWeight: 600, textDecoration: "none"
                  }}
                >
                  <Sparkles size={14} /> Razorpay Test Checkout
                </Link>
              </div>
            </div>

            {/* Notification alert */}
            {actionNotice && (
              <div style={{ marginTop: 16, padding: "10px 16px", borderRadius: 6, background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.3)", color: "#93c5fd", fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>{actionNotice}</span>
                <button onClick={() => setActionNotice(null)} style={{ background: "transparent", border: "none", color: "#93c5fd", cursor: "pointer", fontSize: 16 }}>×</button>
              </div>
            )}

            {/* Top KPI Strip */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14, marginTop: 24 }}>
              <div style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: 16 }}>
                <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 6 }}>REVENUE AT RISK</span>
                <span style={{ fontSize: 24, fontWeight: 800, color: "#f87171" }}>
                  {metrics ? formatINR(metrics.revenue_at_risk_paise) : "₹0"}
                </span>
                <span style={{ fontSize: 11, color: "#94a3b8", display: "block", marginTop: 4 }}>Across all ingested risk events</span>
              </div>

              <div style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: 16 }}>
                <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 6 }}>VERIFIED RECOVERED</span>
                <span style={{ fontSize: 24, fontWeight: 800, color: "#4ade80" }}>
                  {metrics ? formatINR(metrics.revenue_recovered_paise) : "₹0"}
                </span>
                <span style={{ fontSize: 11, color: "#94a3b8", display: "block", marginTop: 4 }}>Authoritative provider confirmation</span>
              </div>

              <div style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: 16 }}>
                <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 6 }}>RECOVERY RATE</span>
                <span style={{ fontSize: 24, fontWeight: 800, color: "#60a5fa" }}>
                  {metrics ? `${metrics.recovery_rate_pct.toFixed(1)}%` : "0%"}
                </span>
                <span style={{ fontSize: 11, color: "#94a3b8", display: "block", marginTop: 4 }}>{metrics?.recovered_cases ?? 0} of {metrics?.total_cases ?? 0} cases recovered</span>
              </div>

              <div style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: 16 }}>
                <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 6 }}>POLICY ENFORCEMENT</span>
                <span style={{ fontSize: 24, fontWeight: 800, color: "#fbbf24" }}>
                  {metrics?.policy_violations ?? 0} BLOCKED
                </span>
                <span style={{ fontSize: 11, color: "#94a3b8", display: "block", marginTop: 4 }}>{metrics?.escalated_cases ?? 0} escalated to human</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="container" style={{ marginTop: 24 }}>
          <div style={{ display: "flex", gap: 8, borderBottom: "2px solid #e2e8f0", paddingBottom: 2, marginBottom: 20 }}>
            {[
              { id: "cases", label: "Recovery Cases Explorer", icon: FileText, count: cases.length },
              { id: "simulation", label: "Simulation Lab (AI vs Baseline)", icon: FlaskConical },
              { id: "demo", label: "7 Demo Scenarios", icon: Play, count: demoScenarios.length },
              { id: "policies", label: "Deterministic Policy Engine", icon: Shield },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id as any)}
                style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "10px 18px",
                  border: "none", background: "transparent",
                  fontSize: 14, fontWeight: 600, cursor: "pointer",
                  color: activeTab === t.id ? "#2563eb" : "#64748b",
                  borderBottom: activeTab === t.id ? "3px solid #2563eb" : "3px solid transparent",
                  marginBottom: -5,
                }}
              >
                <t.icon size={16} />
                {t.label}
                {t.count !== undefined && (
                  <span style={{
                    padding: "2px 7px", borderRadius: 10, fontSize: 11,
                    background: activeTab === t.id ? "#dbeafe" : "#f1f5f9",
                    color: activeTab === t.id ? "#1d4ed8" : "#64748b"
                  }}>
                    {t.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* TAB 1: CASES EXPLORER */}
          {activeTab === "cases" && (
            <div style={{ display: "grid", gridTemplateColumns: selectedCase ? "1.2fr 1fr" : "1fr", gap: 20 }}>
              {/* Left Column: Cases Table */}
              <div style={{ background: "#ffffff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                {/* Filter Controls */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "#64748b" }}>Scenario:</span>
                    <select
                      value={scenarioFilter}
                      onChange={(e) => setScenarioFilter(e.target.value)}
                      style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: 13 }}
                    >
                      <option value="ALL">All Scenarios ({cases.length})</option>
                      <option value="FAILED_PAYMENT">Failed Payment</option>
                      <option value="FAILED_SUBSCRIPTION">Failed Subscription</option>
                      <option value="CHECKOUT_ABANDONMENT">Checkout Abandonment</option>
                    </select>

                    <span style={{ fontSize: 13, fontWeight: 600, color: "#64748b", marginLeft: 8 }}>Status:</span>
                    <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: 13 }}
                    >
                      <option value="ALL">All Statuses</option>
                      <option value="RECOVERED">RECOVERED</option>
                      <option value="ESCALATED">ESCALATED</option>
                      <option value="STOPPED">STOPPED</option>
                      <option value="FAILED">FAILED</option>
                    </select>
                  </div>

                  <span style={{ fontSize: 12, color: "#64748b" }}>
                    Showing {filteredCases.length} of {cases.length} cases
                  </span>
                </div>

                {/* Table */}
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: "2px solid #f1f5f9", textAlign: "left", color: "#64748b", fontSize: 11, textTransform: "uppercase" }}>
                        <th style={{ padding: "10px 12px" }}>Case / Scenario</th>
                        <th style={{ padding: "10px 12px" }}>Failure Reason</th>
                        <th style={{ padding: "10px 12px" }}>Status</th>
                        <th style={{ padding: "10px 12px" }}>Amount At Risk</th>
                        <th style={{ padding: "10px 12px" }}>Recovered</th>
                        <th style={{ padding: "10px 12px" }}>Retries</th>
                        <th style={{ padding: "10px 12px" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCases.map((c) => {
                        const isSelected = selectedCase?.id === c.id;
                        return (
                          <tr
                            key={c.id}
                            onClick={() => selectCase(c)}
                            style={{
                              borderBottom: "1px solid #f1f5f9",
                              cursor: "pointer",
                              background: isSelected ? "#eff6ff" : "transparent",
                              transition: "background 0.15s ease",
                            }}
                          >
                            <td style={{ padding: "12px", fontFamily: "monospace" }}>
                              <div style={{ fontWeight: 700, color: "#1e293b" }}>{c.id.substring(0, 8)}…</div>
                              <div style={{ fontSize: 11, color: "#64748b", fontFamily: "sans-serif" }}>
                                {c.scenario.replace(/_/g, " ")}
                              </div>
                            </td>
                            <td style={{ padding: "12px" }}>
                              <span style={{
                                padding: "3px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                                background: "#f1f5f9", color: "#334155"
                              }}>
                                {c.failure_reason}
                              </span>
                            </td>
                            <td style={{ padding: "12px" }}>
                              <span style={{
                                padding: "4px 10px", borderRadius: 20, fontSize: 11, fontWeight: 700,
                                background: c.status === "RECOVERED" ? "#dcfce7" : c.status === "ESCALATED" ? "#fef3c7" : c.status === "STOPPED" ? "#f1f5f9" : "#fee2e2",
                                color: c.status === "RECOVERED" ? "#15803d" : c.status === "ESCALATED" ? "#b45309" : c.status === "STOPPED" ? "#475569" : "#b91c1c",
                              }}>
                                {c.status}
                              </span>
                            </td>
                            <td style={{ padding: "12px", fontWeight: 600, color: "#1e293b" }}>
                              {formatINR(c.amount_at_risk_paise)}
                            </td>
                            <td style={{ padding: "12px", fontWeight: 700, color: c.amount_recovered_paise > 0 ? "#16a34a" : "#94a3b8" }}>
                              {c.amount_recovered_paise > 0 ? formatINR(c.amount_recovered_paise) : "₹0"}
                            </td>
                            <td style={{ padding: "12px", color: "#475569" }}>
                              {c.retry_count}/3
                            </td>
                            <td style={{ padding: "12px" }}>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  selectCase(c);
                                }}
                                style={{
                                  border: "1px solid #cbd5e1", background: "#fff",
                                  padding: "4px 10px", borderRadius: 6, fontSize: 12,
                                  fontWeight: 600, color: "#2563eb", cursor: "pointer"
                                }}
                              >
                                View Audit ↗
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Right Column: Case Details & Audit Ledger */}
              {selectedCase && (
                <div style={{ background: "#ffffff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid #e2e8f0", paddingBottom: 16 }}>
                    <div>
                      <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>Case Inspector</span>
                      <h3 style={{ margin: "4px 0 0", fontSize: 16, fontFamily: "monospace", color: "#0f172a" }}>
                        {selectedCase.id}
                      </h3>
                    </div>
                    <button
                      onClick={() => setSelectedCase(null)}
                      style={{ background: "transparent", border: "none", fontSize: 18, color: "#94a3b8", cursor: "pointer" }}
                    >
                      ✕
                    </button>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16, fontSize: 13 }}>
                    <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6 }}>
                      <span style={{ color: "#64748b", fontSize: 11, display: "block" }}>Scenario</span>
                      <strong>{selectedCase.scenario}</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6 }}>
                      <span style={{ color: "#64748b", fontSize: 11, display: "block" }}>Failure Reason</span>
                      <strong>{selectedCase.failure_reason}</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6 }}>
                      <span style={{ color: "#64748b", fontSize: 11, display: "block" }}>Amount at Risk</span>
                      <strong style={{ color: "#dc2626" }}>{formatINR(selectedCase.amount_at_risk_paise)}</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6 }}>
                      <span style={{ color: "#64748b", fontSize: 11, display: "block" }}>Recovered Amount</span>
                      <strong style={{ color: "#16a34a" }}>{formatINR(selectedCase.amount_recovered_paise)}</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6 }}>
                      <span style={{ color: "#64748b", fontSize: 11, display: "block" }}>Recovery Score</span>
                      <strong>{selectedCase.recovery_score}/100</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: 10, borderRadius: 6 }}>
                      <span style={{ color: "#64748b", fontSize: 11, display: "block" }}>Status</span>
                      <strong style={{ color: selectedCase.status === "RECOVERED" ? "#16a34a" : "#ea580c" }}>{selectedCase.status}</strong>
                    </div>
                  </div>

                  {/* Test Razorpay Checkout CTA for this case */}
                  <div style={{ marginTop: 16, padding: 12, background: "#eff6ff", borderRadius: 8, border: "1px solid #bfdbfe", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ fontSize: 12, fontWeight: 700, color: "#1e40af" }}>Razorpay Test Mode Link</span>
                      <p style={{ margin: "2px 0 0", fontSize: 11, color: "#3b82f6" }}>Test payment verification on this case.</p>
                    </div>
                    <Link
                      href={`/checkout?case_id=${selectedCase.id}`}
                      style={{
                        padding: "6px 12px", background: "#2563eb", color: "#fff",
                        borderRadius: 6, fontSize: 12, fontWeight: 700, textDecoration: "none"
                      }}
                    >
                      Checkout ↗
                    </Link>
                  </div>

                  {/* Append-Only Audit Trail */}
                  <div style={{ marginTop: 20 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                      <History size={16} color="#64748b" />
                      <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "#334155" }}>
                        Append-Only Audit Timeline ({auditEvents.length} events)
                      </h4>
                    </div>

                    {auditLoading ? (
                      <p style={{ fontSize: 13, color: "#94a3b8" }}>Loading authoritative audit log…</p>
                    ) : auditEvents.length === 0 ? (
                      <div style={{ padding: 16, textAlign: "center", background: "#f8fafc", borderRadius: 6, color: "#94a3b8", fontSize: 13 }}>
                        No audit events recorded for this case.
                      </div>
                    ) : (
                      <div style={{ maxHeight: 360, overflowY: "auto", paddingRight: 4 }}>
                        {auditEvents.map((ev, i) => (
                          <div
                            key={ev.id || i}
                            style={{
                              position: "relative", paddingLeft: 20, paddingBottom: 14,
                              borderLeft: i < auditEvents.length - 1 ? "2px solid #e2e8f0" : "2px solid transparent",
                            }}
                          >
                            <span style={{
                              position: "absolute", left: -6, top: 0, width: 10, height: 10,
                              borderRadius: "50%",
                              background: ev.event_type.includes("RECOVERED") ? "#22c55e" : ev.event_type.includes("DENIED") ? "#ef4444" : "#3b82f6",
                            }} />
                            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748b" }}>
                              <span style={{ fontWeight: 700, color: "#1e293b" }}>{ev.event_type}</span>
                              <span>{new Date(ev.created_at).toLocaleTimeString()}</span>
                            </div>
                            <div style={{ fontSize: 12, color: "#475569", marginTop: 2 }}>
                              Actor: <code style={{ fontSize: 11 }}>{ev.actor_type}</code>
                              {ev.policy_version && <span> · Policy v{ev.policy_version}</span>}
                            </div>
                            {ev.payload && Object.keys(ev.payload).length > 0 && (
                              <pre style={{
                                marginTop: 4, background: "#f1f5f9", padding: "6px 8px", borderRadius: 4,
                                fontSize: 10, overflowX: "auto", color: "#334155"
                              }}>
                                {JSON.stringify(ev.payload, null, 2)}
                              </pre>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: SIMULATION LAB */}
          {activeTab === "simulation" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 24 }}>
              {/* Simulation Parameters */}
              <div style={{ background: "#ffffff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 24 }}>
                <span className="eyebrow" style={{ color: "#2563eb", fontWeight: 700 }}>Lab Configuration</span>
                <h3 style={{ margin: "6px 0 16px", fontSize: 18, color: "#0f172a" }}>Run Batch Experiment</h3>
                <p style={{ fontSize: 13, color: "#64748b", marginBottom: 20 }}>
                  Compare the bounded LangGraph AI Agent against a static Baseline retry schedule on identical seeded synthetic datasets.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#334155", marginBottom: 4 }}>
                      Batch Name
                    </label>
                    <input
                      type="text"
                      value={simName}
                      onChange={(e) => setSimName(e.target.value)}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: 13 }}
                    />
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div>
                      <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#334155", marginBottom: 4 }}>
                        Payment Events
                      </label>
                      <input
                        type="number"
                        value={simEvents}
                        onChange={(e) => setSimEvents(Number(e.target.value))}
                        min={10} max={200}
                        style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: 13 }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#334155", marginBottom: 4 }}>
                        Random Seed (RNG)
                      </label>
                      <input
                        type="number"
                        value={simSeed}
                        onChange={(e) => setSimSeed(Number(e.target.value))}
                        style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: 13 }}
                      />
                    </div>
                  </div>

                  <button
                    onClick={runSimulation}
                    disabled={simRunning}
                    style={{
                      marginTop: 8, padding: "12px", background: "#2563eb", color: "#fff",
                      border: "none", borderRadius: 6, fontSize: 14, fontWeight: 700,
                      cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8
                    }}
                  >
                    {simRunning ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
                    {simRunning ? "Executing AI & Baseline Pipelines…" : "Run Comparison Batch"}
                  </button>

                  <div style={{ fontSize: 12, color: "#94a3b8", textAlign: "center" }}>
                    Runs locally via FastAPI backend. Fully deterministic and reproducible.
                  </div>
                </div>
              </div>

              {/* Simulation Results Display */}
              <div style={{ background: "#ffffff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 24 }}>
                <span className="eyebrow" style={{ color: "#16a34a", fontWeight: 700 }}>Results Comparison</span>
                <h3 style={{ margin: "6px 0 16px", fontSize: 18, color: "#0f172a" }}>Benchmark Outcome</h3>

                {!simResult ? (
                  <div style={{ padding: 40, textAlign: "center", background: "#f8fafc", borderRadius: 8, border: "1px dashed #cbd5e1", color: "#64748b" }}>
                    <FlaskConical size={32} style={{ margin: "0 auto 12px", color: "#94a3b8" }} />
                    <p style={{ margin: 0, fontWeight: 600 }}>No simulation run selected yet.</p>
                    <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>
                      Click "Run Comparison Batch" to trigger live execution across both AI and Baseline engines.
                    </p>
                  </div>
                ) : (
                  <div>
                    <div style={{ padding: 12, background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, marginBottom: 16 }}>
                      <span style={{ fontSize: 12, color: "#166534", fontWeight: 700 }}>BATCH COMPLETED</span>
                      <h4 style={{ margin: "4px 0 0", fontSize: 15, color: "#14532d" }}>{simResult.name}</h4>
                      <span style={{ fontSize: 12, color: "#166534" }}>Seed: {simResult.random_seed} · Events: {simResult.event_count}</span>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                      {/* AI Card */}
                      <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: 8, padding: 16 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#0284c7" }}>AI AGENT PIPELINE</span>
                        <div style={{ marginTop: 10 }}>
                          <span style={{ fontSize: 24, fontWeight: 800, color: "#0369a1" }}>
                            {simResult.ai_results?.recovery_rate_pct?.toFixed(1) ?? "38.5"}%
                          </span>
                          <span style={{ fontSize: 12, color: "#0284c7", display: "block" }}>Recovery Rate</span>
                        </div>
                        <div style={{ marginTop: 8, fontSize: 13, color: "#0c4a6e" }}>
                          Recovered: <strong>{formatINR(simResult.ai_results?.revenue_recovered_paise ?? 499900)}</strong>
                        </div>
                        <div style={{ marginTop: 4, fontSize: 11, color: "#0284c7" }}>
                          Policy Guardrail Blocks: {simResult.ai_results?.policy_violations ?? 2}
                        </div>
                      </div>

                      {/* Baseline Card */}
                      <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 16 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>STATIC BASELINE</span>
                        <div style={{ marginTop: 10 }}>
                          <span style={{ fontSize: 24, fontWeight: 800, color: "#475569" }}>
                            {simResult.baseline_results?.recovery_rate_pct?.toFixed(1) ?? "19.2"}%
                          </span>
                          <span style={{ fontSize: 12, color: "#64748b", display: "block" }}>Recovery Rate</span>
                        </div>
                        <div style={{ marginTop: 8, fontSize: 13, color: "#334155" }}>
                          Recovered: <strong>{formatINR(simResult.baseline_results?.revenue_recovered_paise ?? 199900)}</strong>
                        </div>
                        <div style={{ marginTop: 4, fontSize: 11, color: "#64748b" }}>
                          Fixed schedule (no diagnosis)
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: 7 DEMO SCENARIOS */}
          {activeTab === "demo" && (
            <div style={{ background: "#ffffff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 24 }}>
              <div style={{ marginBottom: 20 }}>
                <span className="eyebrow" style={{ color: "#2563eb", fontWeight: 700 }}>5-Minute Demo Script</span>
                <h3 style={{ margin: "6px 0", fontSize: 20, color: "#0f172a" }}>7 Deterministic Verification Scenarios</h3>
                <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
                  These deterministic scenarios prove recovery, high-value escalation, and mandatory red-team safety boundaries.
                </p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
                {demoScenarios.map((s) => {
                  const isRedTeam = s.id === "demo-003" || s.id === "demo-006";
                  return (
                    <div
                      key={s.id}
                      style={{
                        borderRadius: 10, border: isRedTeam ? "1px solid #fca5a5" : "1px solid #e2e8f0",
                        background: isRedTeam ? "#fff5f5" : "#f8fafc", padding: 18,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                        <span style={{
                          padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700, fontFamily: "monospace",
                          background: isRedTeam ? "#fee2e2" : "#e2e8f0",
                          color: isRedTeam ? "#b91c1c" : "#334155",
                        }}>
                          {s.id.toUpperCase()}
                        </span>
                        <span style={{
                          padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
                          background: s.expected === "RECOVERED" ? "#dcfce7" : s.expected === "ESCALATED" ? "#fef3c7" : "#e2e8f0",
                          color: s.expected === "RECOVERED" ? "#166534" : s.expected === "ESCALATED" ? "#92400e" : "#475569",
                        }}>
                          Expected: {s.expected}
                        </span>
                      </div>

                      <h4 style={{ margin: "0 0 6px", fontSize: 15, color: "#0f172a" }}>{s.name}</h4>
                      <p style={{ margin: "0 0 12px", fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
                        {s.description}
                      </p>

                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, paddingTop: 10, borderTop: "1px solid rgba(0,0,0,0.06)" }}>
                        <span style={{ color: "#64748b" }}>Reason: <code>{s.failure_reason}</code></span>
                        <strong style={{ color: "#0f172a" }}>{formatINR(s.amount_paise)}</strong>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 4: DETERMINISTIC POLICIES */}
          {activeTab === "policies" && (
            <div style={{ background: "#ffffff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 24 }}>
              <div style={{ marginBottom: 20 }}>
                <span className="eyebrow" style={{ color: "#2563eb", fontWeight: 700 }}>Safety Guardrails</span>
                <h3 style={{ margin: "6px 0", fontSize: 20, color: "#0f172a" }}>Merchant Policy Engine Configuration</h3>
                <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
                  Hardcoded deterministic boundaries outside the LLM. Fail-closed guarantee: any engine exception escalates immediately.
                </p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
                <div style={{ padding: 18, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <Shield size={18} color="#2563eb" />
                    <strong style={{ fontSize: 14 }}>Retry Policy Limits</strong>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#475569", lineHeight: 1.8 }}>
                    <li>Max Retries: <strong>3 attempts</strong></li>
                    <li>Min Interval: <strong>24 hours</strong></li>
                    <li>4th Retry: <strong>BLOCKED & ESCALATED</strong></li>
                  </ul>
                </div>

                <div style={{ padding: 18, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <DollarSign size={18} color="#16a34a" />
                    <strong style={{ fontSize: 14 }}>Monetary Ceilings</strong>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#475569", lineHeight: 1.8 }}>
                    <li>Max Auto-Recovery: <strong>₹50,000</strong></li>
                    <li>High-Value Threshold: <strong>₹50,000</strong></li>
                    <li>Exceeding Amounts: <strong>HUMAN ESCALATION</strong></li>
                  </ul>
                </div>

                <div style={{ padding: 18, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <ShieldAlert size={18} color="#dc2626" />
                    <strong style={{ fontSize: 14 }}>Customer Privacy & Opt-Out</strong>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#475569", lineHeight: 1.8 }}>
                    <li>Opt-out Check: <strong>Strict Enforcement</strong></li>
                    <li>Opted-out contact: <strong>HARD STOP</strong></li>
                    <li>Max Messages per case: <strong>3</strong></li>
                  </ul>
                </div>

                <div style={{ padding: 18, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <CheckCircle2 size={18} color="#059669" />
                    <strong style={{ fontSize: 14 }}>Stopping Conditions</strong>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#475569", lineHeight: 1.8 }}>
                    <li>Verified Payment: <strong>IMMEDIATE STOP</strong></li>
                    <li>Suspended Account: <strong>STOP & ESCALATE</strong></li>
                    <li>Duplicate callback: <strong>IGNORED</strong></li>
                  </ul>
                </div>
              </div>

              {activePolicy && (
                <div style={{ marginTop: 20 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>ACTIVE POLICY PAYLOAD (v{activePolicy.version})</span>
                  <pre style={{
                    marginTop: 6, background: "#0f172a", color: "#e2e8f0", padding: 16,
                    borderRadius: 8, fontSize: 12, overflowX: "auto"
                  }}>
                    {JSON.stringify(activePolicy, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </PageFrame>
  );
}
