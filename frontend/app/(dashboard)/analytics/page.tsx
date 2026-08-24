"use client";

import { useQuery } from "@tanstack/react-query";
import { getMetricsOverview, listSimulations, formatINR } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Legend, CartesianGrid, LineChart, Line,
} from "recharts";

export default function AnalyticsPage() {
  const { data: metrics } = useQuery({
    queryKey: ["metrics-overview"],
    queryFn: () => getMetricsOverview(),
    refetchInterval: 15_000,
  });

  const { data: simRuns } = useQuery({
    queryKey: ["simulations"],
    queryFn: listSimulations,
    refetchInterval: 10_000,
  });

  const completedRuns = (simRuns ?? []).filter(r => r.status === "COMPLETED");
  const aiRuns       = completedRuns.filter(r => !r.is_baseline);
  const baseRuns     = completedRuns.filter(r =>  r.is_baseline);

  const compData = aiRuns.slice(0, 6).map((ai, i) => {
    const bl = baseRuns[i];
    return {
      run:          `Run ${i + 1}`,
      "AI":         parseFloat((ai.recovery_rate_pct ?? 0).toFixed(1)),
      "Baseline":   parseFloat((bl?.recovery_rate_pct ?? 0).toFixed(1)),
      ai_recovered: ai.revenue_recovered_paise ?? 0,
      bl_recovered: bl?.revenue_recovered_paise ?? 0,
    };
  });

  const reasonData = metrics
    ? Object.entries(metrics.by_failure_reason).map(([reason, m]) => ({
        reason: reason.replace(/_/g, " ").slice(0, 16),
        rate: m.total > 0 ? Math.round((m.recovered / m.total) * 100) : 0,
        total: m.total,
      }))
    : [];

  const tooltipStyle = {
    backgroundColor: "#fff", border: "1px solid #e5e7eb",
    borderRadius: 8, fontSize: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.08)"
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-text-primary tracking-tight">Analytics</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          All numbers computed from real simulation data — nothing fabricated
        </p>
      </div>

      {/* Baseline vs AI */}
      {compData.length > 0 && (
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-1">
            Baseline vs RevenueRescue AI — Recovery Rate
          </h3>
          <p className="text-xs text-text-secondary mb-4">
            Both runs use identical datasets and failure distributions.
            All numbers from real simulation execution.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={compData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="run" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <Tooltip formatter={(v: number) => `${v}%`} contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#6b7280" }} />
              <Bar dataKey="Baseline" fill="#d1d5db" radius={[4,4,0,0]} />
              <Bar dataKey="AI"       fill="#528FF5" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>

          {/* Summary table */}
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 label-xs">Run</th>
                  <th className="text-right py-2 label-xs">Baseline Recovered</th>
                  <th className="text-right py-2 label-xs">AI Recovered</th>
                  <th className="text-right py-2 label-xs">Improvement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {compData.map(row => {
                  const improvement = row["AI"] - row["Baseline"];
                  return (
                    <tr key={row.run} className="hover:bg-surface-elevated">
                      <td className="py-2 text-text-secondary">{row.run}</td>
                      <td className="py-2 text-right font-mono">{formatINR(row.bl_recovered)}</td>
                      <td className="py-2 text-right font-mono text-success font-semibold">{formatINR(row.ai_recovered)}</td>
                      <td className={`py-2 text-right font-mono font-semibold ${improvement > 0 ? "text-success" : "text-text-secondary"}`}>
                        {improvement > 0 ? `+${improvement.toFixed(1)}%` : `${improvement.toFixed(1)}%`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recovery rate by failure reason */}
      {reasonData.length > 0 && (
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-1">Recovery Rate by Failure Reason</h3>
          <p className="text-xs text-text-secondary mb-4">Percentage of cases recovered per failure type</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={reasonData} margin={{ top: 4, right: 4, bottom: 32, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="reason" tick={{ fontSize: 9, fill: "#9ca3af" }} angle={-35} textAnchor="end" interval={0} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <Tooltip formatter={(v: number) => `${v}%`} contentStyle={tooltipStyle} />
              <Bar dataKey="rate" name="Recovery Rate %" fill="#528FF5" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {compData.length === 0 && reasonData.length === 0 && (
        <div className="card-surface p-12 text-center">
          <p className="text-text-tertiary text-sm">
            No simulation data yet. Run simulations in{" "}
            <a href="/simulation" className="text-brand-primary hover:underline font-medium">Simulation Lab</a>{" "}
            (both AI and Baseline modes) to see the comparison.
          </p>
        </div>
      )}
    </div>
  );
}
