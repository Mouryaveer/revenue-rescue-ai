"use client";

import { useQuery } from "@tanstack/react-query";
import { getBaselineComparison, formatINR } from "@/lib/api";
import { clsx } from "clsx";
import { TrendingUp, Minus } from "lucide-react";

interface BaselineComparisonProps {
  aiRunId: string;
  baselineRunId: string;
}

export function BaselineComparison({ aiRunId, baselineRunId }: BaselineComparisonProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["baseline-comparison", aiRunId, baselineRunId],
    queryFn: () => getBaselineComparison(aiRunId, baselineRunId),
    enabled: !!aiRunId && !!baselineRunId,
  });

  if (isLoading) {
    return <div className="h-32 bg-card border border-border rounded-lg animate-pulse" />;
  }
  if (!data) return null;

  const improved = data.improvement_pct > 0;
  const rows = [
    { label: "Revenue Recovered",   ai: formatINR(data.REVENUERESCUE_AI.revenue_recovered_paise),  baseline: formatINR(data.BASELINE.revenue_recovered_paise) },
    { label: "Recovery Rate",       ai: `${data.REVENUERESCUE_AI.recovery_rate_pct.toFixed(1)}%`,  baseline: `${data.BASELINE.recovery_rate_pct.toFixed(1)}%` },
    { label: "Escalated Cases",     ai: data.REVENUERESCUE_AI.escalated_cases.toString(),           baseline: data.BASELINE.escalated_cases.toString() },
    { label: "Policy Violations",   ai: data.REVENUERESCUE_AI.policy_violations.toString(),         baseline: data.BASELINE.policy_violations.toString() },
    { label: "Total Cases",         ai: data.REVENUERESCUE_AI.total_cases.toString(),               baseline: data.BASELINE.total_cases.toString() },
  ];

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="border-b border-border px-4 py-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Baseline vs RevenueRescue AI</h3>
        <div className={clsx(
          "flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded",
          improved ? "text-success bg-success/10" : "text-muted-foreground bg-muted/20",
        )}>
          {improved ? <TrendingUp className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
          {improved ? `+${data.improvement_pct.toFixed(1)}% improvement` : "No improvement"}
        </div>
      </div>

      <table className="w-full text-sm">
        <thead className="border-b border-border bg-muted/10">
          <tr>
            <th className="px-4 py-2 text-left label-xs">Metric</th>
            <th className="px-4 py-2 text-right label-xs text-muted-foreground">Baseline</th>
            <th className="px-4 py-2 text-right label-xs text-primary">RevenueRescue AI</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map(({ label, ai, baseline }) => (
            <tr key={label} className="hover:bg-accent/10">
              <td className="px-4 py-2.5 text-muted-foreground">{label}</td>
              <td className="px-4 py-2.5 text-right mono text-muted-foreground">{baseline}</td>
              <td className="px-4 py-2.5 text-right mono font-semibold text-foreground">{ai}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-4 py-2 border-t border-border">
        <p className="text-xs text-muted-foreground">{data.note}</p>
      </div>
    </div>
  );
}
