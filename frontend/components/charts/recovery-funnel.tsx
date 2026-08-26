"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { MetricsOverview } from "@/lib/api";
import { formatINR } from "@/lib/api";

export function RecoveryFunnelChart({ data }: { data: MetricsOverview }) {
  const chartData = [
    { name: "At Risk",   value: data.revenue_at_risk_paise,   color: "#f87171", label: formatINR(data.revenue_at_risk_paise) },
    { name: "Recovered", value: data.revenue_recovered_paise, color: "#34d399", label: formatINR(data.revenue_recovered_paise) },
    { name: "Escalated", value: data.escalated_cases * 100000, color: "#fbbf24", label: `${data.escalated_cases} cases` },
    { name: "Active",    value: data.active_cases * 100000,    color: "#60a5fa", label: `${data.active_cases} cases` },
  ];

  return (
    <div className="card-surface p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-1">Recovery Funnel</h3>
      <p className="text-xs text-text-secondary mb-4">Revenue flow through recovery stages</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
          <YAxis hide />
          <Tooltip
            formatter={(_: number, name: string, props: any) => [props.payload.label, name]}
            contentStyle={{ backgroundColor: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
          />
          <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={60}>
            {chartData.map((e, i) => <Cell key={i} fill={e.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
