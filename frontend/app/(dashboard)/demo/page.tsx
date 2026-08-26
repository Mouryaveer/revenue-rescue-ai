"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch, formatINR } from "@/lib/api";
import { useState } from "react";
import { clsx } from "clsx";
import { Play, RefreshCw, CheckCircle, AlertTriangle, XCircle, Shield, Clock } from "lucide-react";

interface DemoScenario {
  id: string;
  name: string;
  scenario: string;
  failure_reason: string;
  amount_paise: number;
  expected: string;
  description: string;
}

interface RunResult {
  case_id: string;
  scenario: DemoScenario;
  status: string;
  message: string;
}

const EXPECTED_ICONS: Record<string, React.ReactNode> = {
  RECOVERED: <CheckCircle className="h-4 w-4 text-success" />,
  ESCALATED: <AlertTriangle className="h-4 w-4 text-warning" />,
  STOPPED:   <XCircle className="h-4 w-4 text-danger" />,
};

const EXPECTED_COLORS: Record<string, string> = {
  RECOVERED: "text-success bg-success/5 border-success/20",
  ESCALATED: "text-warning bg-warning/5 border-warning/20",
  STOPPED:   "text-danger bg-danger/5 border-danger/20",
};

export default function DemoPage() {
  const qc = useQueryClient();
  const [results, setResults] = useState<Record<string, RunResult>>({});
  const [resetting, setResetting] = useState(false);
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set());

  const { data: scenarios, isLoading } = useQuery<DemoScenario[]>({
    queryKey: ["demo-scenarios"],
    queryFn: () => apiFetch<DemoScenario[]>("/demo/scenarios"),
  });

  const pollCaseUntilResolved = async (caseId: string, scenarioId: string, scenario: DemoScenario) => {
    const maxWait = 20; // seconds
    const interval = 1000; // 1s poll
    for (let i = 0; i < maxWait; i++) {
      await new Promise(r => setTimeout(r, interval));
      try {
        const c = await apiFetch<{ status: string; is_recovered: boolean; is_stopped: boolean }>(`/recovery-cases/${caseId}`);
        if (c.status !== "DETECTED" && c.status !== "DIAGNOSING") {
          setResults(prev => ({
            ...prev,
            [scenarioId]: { case_id: caseId, scenario, status: c.status, message: `Resolved: ${c.status}` },
          }));
          setRunningIds(prev => { const s = new Set(prev); s.delete(scenarioId); return s; });
          return;
        }
      } catch { /* keep polling */ }
    }
    // Timeout — show whatever we have
    setRunningIds(prev => { const s = new Set(prev); s.delete(scenarioId); return s; });
  };

  const { mutate: runScenario } = useMutation({
    mutationFn: (id: string) => apiFetch<RunResult>(`/demo/run/${id}`, { method: "POST" }),
    onMutate: (id) => {
      setRunningIds(prev => new Set(prev).add(id));
    },
    onSuccess: (data) => {
      // Show initial RUNNING state immediately
      setResults(prev => ({ ...prev, [data.scenario.id]: data }));
      // Poll until the agent actually finishes (5–10s)
      pollCaseUntilResolved(data.case_id, data.scenario.id, data.scenario);
    },
    onError: (_, id) => {
      setRunningIds(prev => { const s = new Set(prev); s.delete(id); return s; });
    },
  });

  const handleReset = async () => {
    setResetting(true);
    setResults({});
    await apiFetch("/demo/reset", { method: "POST" });
    setTimeout(() => { setResetting(false); qc.invalidateQueries({ queryKey: ["metrics-overview"] }); }, 5000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">Demo Mode</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            7 deterministic scenarios — each demonstrates a specific system capability
          </p>
        </div>
        <button onClick={handleReset} disabled={resetting}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-surface text-sm font-medium text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors">
          <RefreshCw className={clsx("h-4 w-4", resetting && "animate-spin")} />
          {resetting ? "Resetting…" : "Reset Demo"}
        </button>
      </div>

      {/* Safety notice */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-brand-soft border border-brand-primary/20">
        <Shield className="h-4 w-4 text-brand-primary mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-brand-primary">All demo data is synthetic</p>
          <p className="text-xs text-text-secondary mt-0.5">
            No real payments, no real customers, no real money. Every scenario uses deterministic
            seeded simulation. Results are computed — never fabricated.
          </p>
        </div>
      </div>

      {/* Scenario grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-36 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(scenarios ?? []).map((s) => {
            const result = results[s.id];
            const isRunning = runningIds.has(s.id);
            return (
              <div key={s.id} className={clsx(
                "card-surface p-5 transition-all hover:shadow-card-hover",
                result && !isRunning ? "ring-1 ring-brand-primary/20" : ""
              )}>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-text-tertiary">{s.id}</span>
                      <span className={clsx(
                        "inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border",
                        EXPECTED_COLORS[s.expected] ?? ""
                      )}>
                        {EXPECTED_ICONS[s.expected]}
                        {s.expected}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-text-primary leading-snug">{s.name}</p>
                  </div>
                  <span className="text-base font-mono font-bold text-text-primary shrink-0">
                    {formatINR(s.amount_paise)}
                  </span>
                </div>

                <p className="text-xs text-text-secondary mb-4 leading-relaxed">{s.description}</p>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-text-tertiary font-mono">
                      {s.failure_reason.replace(/_/g, " ")}
                    </span>
                  </div>
                  <button
                    onClick={() => runScenario(s.id)}
                    disabled={isRunning}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-primary text-white text-xs font-semibold hover:bg-brand-hover disabled:opacity-50 transition-colors"
                  >
                    {isRunning
                      ? <><Clock className="h-3.5 w-3.5 animate-spin" /> Running…</>
                      : result
                      ? <><RefreshCw className="h-3.5 w-3.5" /> Re-run</>
                      : <><Play className="h-3.5 w-3.5" /> Run</>
                    }
                  </button>
                </div>

                {result && !isRunning && (
                  <div className="mt-3 pt-3 border-t border-border">
                    <p className="text-xs text-text-secondary">
                      Status: <span className={clsx("font-semibold", result.status === "RECOVERED" ? "text-success" : result.status === "ESCALATED" ? "text-warning" : "text-text-secondary")}>{result.status}</span>
                      {" · "}Case: <span className="font-mono">{result.case_id.slice(0, 12)}…</span>
                    </p>
                    <a href={`/cases/${result.case_id}`}
                      className="text-xs text-brand-primary hover:underline font-medium">
                      View case detail →
                    </a>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Demo flow guide */}
      <div className="card-surface p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-3">5-Minute Demo Flow</h3>
        <ol className="space-y-2 text-sm text-text-secondary">
          {[
            "Run Demo-001 and Demo-002 → show successful recovery path end-to-end",
            "Open Command Center → watch the pipeline nodes light up live",
            "Open each recovered case → show audit timeline with POLICY_APPROVED → REVENUE_RECOVERED",
            "Run Demo-003 → show Policy Engine blocking the 4th retry (RED-TEAM check)",
            "Run Demo-006 → show opted-out customer getting immediate DENIED",
            "Go to Simulation Lab → run 1,000 event AI + Baseline comparison → show real metrics",
            "Show Overview → Policy Violations = 0 throughout",
          ].map((step, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="h-5 w-5 rounded-full bg-brand-soft text-brand-primary text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
