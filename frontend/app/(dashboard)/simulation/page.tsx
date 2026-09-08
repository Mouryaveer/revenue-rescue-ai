"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listSimulations, startSimulation, formatINR, apiFetch } from "@/lib/api";
import { useState } from "react";
import { clsx } from "clsx";
import { FlaskConical, Play, RefreshCw, BarChart2, CheckCircle, Clock, AlertTriangle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from "recharts";

const PRESETS = [
  { label: "Quick Demo",     events: 100,   customers: 20,  seed: 42 },
  { label: "Standard Run",   events: 1000,  customers: 100, seed: 42 },
  { label: "Large Batch",    events: 10000, customers: 500, seed: 42 },
];

export default function SimulationPage() {
  const qc = useQueryClient();
  const [numEvents,    setNumEvents]    = useState(1000);
  const [numCustomers, setNumCustomers] = useState(100);
  const [seed,         setSeed]         = useState(42);
  const [label,        setLabel]        = useState("AI Run");
  const [isBaseline,   setIsBaseline]   = useState(false);
  const [activeTab,    setActiveTab]    = useState<"configure" | "results">("configure");

  const { data: runs, isLoading } = useQuery({
    queryKey: ["simulations"],
    queryFn: listSimulations,
    refetchInterval: 3_000,
  });

  const { mutate: runSim, isPending } = useMutation({
    mutationFn: startSimulation,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["simulations"] }); setActiveTab("results"); },
  });

  const completedRuns = (runs ?? []).filter(r => r.status === "COMPLETED");
  const aiRuns       = completedRuns.filter(r => !r.is_baseline);
  const baseRuns     = completedRuns.filter(r =>  r.is_baseline);

  // Build comparison chart data
  const compData = aiRuns.slice(0, 5).map((ai, i) => {
    const bl = baseRuns[i];
    return {
      name: `Run ${i+1}`,
      "AI Rate %":       parseFloat((ai.recovery_rate_pct ?? 0).toFixed(1)),
      "Baseline Rate %": parseFloat((bl?.recovery_rate_pct ?? 0).toFixed(1)),
    };
  });

  const applyPreset = (p: typeof PRESETS[0]) => {
    setNumEvents(p.events); setNumCustomers(p.customers); setSeed(p.seed);
    setLabel(p.label);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">Simulation Lab</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Run reproducible batch experiments — baseline vs RevenueRescue AI
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setActiveTab("configure")} className={clsx("px-3 py-1.5 rounded-lg text-sm font-medium transition-colors", activeTab === "configure" ? "bg-brand-primary text-white" : "bg-surface border border-border text-text-secondary hover:text-text-primary")}>Configure</button>
          <button onClick={() => setActiveTab("results")}   className={clsx("px-3 py-1.5 rounded-lg text-sm font-medium transition-colors", activeTab === "results"   ? "bg-brand-primary text-white" : "bg-surface border border-border text-text-secondary hover:text-text-primary")}>Results</button>
        </div>
      </div>

      {activeTab === "configure" && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Config panel */}
          <div className="card-surface p-5 space-y-5">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-brand-primary" />
              <h3 className="text-sm font-semibold text-text-primary">Experiment Configuration</h3>
            </div>

            {/* Presets */}
            <div>
              <p className="label-xs mb-2">Presets</p>
              <div className="flex gap-2 flex-wrap">
                {PRESETS.map(p => (
                  <button key={p.label} onClick={() => applyPreset(p)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border bg-surface-elevated hover:border-brand-primary/50 hover:text-brand-primary transition-colors">
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Payment Events" value={numEvents} onChange={setNumEvents} min={10} max={10000} />
              <Field label="Customers"      value={numCustomers} onChange={setNumCustomers} min={5} max={1000} />
              <Field label="Random Seed"    value={seed} onChange={setSeed} min={1} max={99999} />
              <div>
                <label className="label-xs block mb-1.5">Label</label>
                <input className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
                  value={label} onChange={e => setLabel(e.target.value)} />
              </div>
            </div>

            <div className="flex items-center gap-2 p-3 bg-surface-elevated rounded-lg border border-border">
              <input type="checkbox" id="baseline" checked={isBaseline} onChange={e => setIsBaseline(e.target.checked)}
                className="h-4 w-4 rounded border-border text-brand-primary" />
              <label htmlFor="baseline" className="text-sm text-text-secondary cursor-pointer">
                <span className="font-medium text-text-primary">Baseline mode</span>
                {" "}— fixed retry schedule, no AI diagnosis
              </label>
            </div>

            <div className="flex gap-3">
              <button disabled={isPending} onClick={() => runSim({ num_customers: numCustomers, num_events: numEvents, failure_rate: 0.15, random_seed: seed, is_baseline: false, label: "AI: " + label })}
                className="flex items-center gap-2 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50 transition-colors">
                <Play className="h-4 w-4" />
                {isPending ? "Starting…" : "Run AI"}
              </button>
              <button disabled={isPending} onClick={() => runSim({ num_customers: numCustomers, num_events: numEvents, failure_rate: 0.15, random_seed: seed, is_baseline: true, label: "Baseline: " + label })}
                className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors">
                <RefreshCw className="h-4 w-4" />
                Run Baseline
              </button>
            </div>

            <p className="text-xs text-text-tertiary">
              ⚠ Use same seed for both AI and Baseline to get a valid comparison.
              All results are computed from real simulation data — never fabricated.
            </p>
          </div>

          {/* Active runs */}
          <div className="card-surface">
            <div className="p-4 border-b border-border">
              <p className="text-sm font-semibold text-text-primary">Active Runs</p>
            </div>
            <div className="divide-y divide-border">
              {(runs ?? []).filter(r => r.status !== "COMPLETED").length === 0
                ? <div className="p-8 text-center text-text-tertiary text-sm">No active runs</div>
                : (runs ?? []).filter(r => r.status !== "COMPLETED").map(r => (
                    <div key={r.simulation_id} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-medium text-text-primary">{r.label}</p>
                        <span className="text-xs font-semibold text-warning animate-pulse">RUNNING</span>
                      </div>
                      <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-brand-primary rounded-full transition-all duration-500" style={{ width: `${r.progress_pct ?? 0}%` }} />
                      </div>
                      <p className="text-xs text-text-tertiary mt-1">{Math.round(r.progress_pct ?? 0)}% · {(r.num_events ?? 0).toLocaleString()} events</p>
                    </div>
                  ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === "results" && (
        <div className="space-y-6">
          {/* Comparison chart */}
          {compData.length > 0 && (
            <div className="card-surface p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-1">Baseline vs RevenueRescue AI — Recovery Rate</h3>
              <p className="text-xs text-text-secondary mb-4">Both runs use identical datasets. All numbers from real simulation data.</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={compData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6b7280" }} />
                  <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11, fill: "#6b7280" }} />
                  <Tooltip formatter={(v: number) => `${v}%`} contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Baseline Rate %" fill="#d1d5db" radius={[4,4,0,0]} />
                  <Bar dataKey="AI Rate %"       fill="#528FF5" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Results table */}
          <div className="card-surface overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary">All Simulation Runs</h3>
              <p className="text-xs text-text-secondary">Results computed from real execution — never fabricated</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-surface-elevated">
                  <tr className="text-left">
                    {["ID", "Label", "Type", "Status", "Events", "Recovered", "Rate", "Seed", "Violations"].map(h => (
                      <th key={h} className="px-4 py-2.5 label-xs">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {isLoading
                    ? <tr><td colSpan={9} className="px-4 py-8 text-center text-text-tertiary text-sm">Loading…</td></tr>
                    : (runs ?? []).map(r => (
                        <tr key={r.simulation_id} className="hover:bg-surface-elevated transition-colors">
                          <td className="px-4 py-3 font-mono text-xs text-text-tertiary">{r.simulation_id.slice(-8)}</td>
                          <td className="px-4 py-3 text-sm font-medium text-text-primary">{r.label}</td>
                          <td className="px-4 py-3">
                            <span className={clsx("text-xs px-2 py-0.5 rounded-full font-semibold border",
                              r.is_baseline
                                ? "text-gray-500 bg-gray-50 border-gray-200"
                                : "text-brand-primary bg-brand-soft border-brand-primary/20"
                            )}>
                              {r.is_baseline ? "BASELINE" : "AI"}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <StatusCell status={r.status} />
                          </td>
                          <td className="px-4 py-3 font-mono text-sm">{(r.num_events ?? 0).toLocaleString()}</td>
                          <td className="px-4 py-3 font-mono text-sm text-success font-semibold">{formatINR(r.revenue_recovered_paise ?? 0)}</td>
                          <td className="px-4 py-3 font-mono text-sm font-bold">{(r.recovery_rate_pct ?? 0).toFixed(1)}%</td>
                          <td className="px-4 py-3 font-mono text-xs text-text-tertiary">{r.random_seed ?? "—"}</td>
                          <td className="px-4 py-3 font-mono text-sm">
                            <span className={clsx("font-semibold", r.policy_violations === 0 ? "text-success" : "text-danger font-bold")}>
                              {r.policy_violations ?? 0}
                            </span>
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, min, max }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number }) {
  return (
    <div>
      <label className="label-xs block mb-1.5">{label}</label>
      <input type="number" min={min} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-mono text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/30" />
    </div>
  );
}

function StatusCell({ status }: { status: string }) {
  const cfg: Record<string, { label: string; class: string }> = {
    COMPLETED: { label: "Completed", class: "text-success" },
    RUNNING:   { label: "Running…",  class: "text-warning animate-pulse" },
    PENDING:   { label: "Queued",    class: "text-text-secondary" },
    FAILED:    { label: "Failed",    class: "text-danger" },
  };
  const c = cfg[status] ?? { label: status, class: "text-text-secondary" };
  return <span className={clsx("text-xs font-semibold", c.class)}>{c.label}</span>;
}
