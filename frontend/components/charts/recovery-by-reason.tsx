"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { FailureReasonMetrics } from "@/lib/api";
import { formatINR } from "@/lib/api";

export function RecoveryByReasonChart({ data }: { data: Record<string, FailureReasonMetrics> }) {
  const chartData = Object.entries(data).map(([reason, m]) => ({
    reason: reason.replace(/_/g, " ").replace("CHECKOUT ABANDONED", "CHECKOUT").slice(0, 14),
    at_risk:   m.revenue_at_risk,
    recovered: m.revenue_recovered,
  }));

  return (
    <div className="card-surface p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-1">Recovery by Failure Reason</h3>
      <p className="text-xs text-text-secondary mb-4">Revenue at risk vs. recovered</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 28, left: 4 }}>
          <XAxis dataKey="reason" tick={{ fontSize: 9, fill: "#9ca3af" }} angle={-35} textAnchor="end" interval={0} axisLine={false} tickLine={false} />
          <YAxis hide />
          <Tooltip
            formatter={(v: number) => formatINR(v)}
            contentStyle={{ backgroundColor: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: "#6b7280" }} />
          <Bar dataKey="at_risk"   name="At Risk"    fill="#fca5a5" radius={[3,3,0,0]} />
          <Bar dataKey="recovered" name="Recovered"  fill="#34d399" radius={[3,3,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
