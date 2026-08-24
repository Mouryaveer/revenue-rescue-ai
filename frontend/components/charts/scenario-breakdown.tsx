"use client";

import { formatINR, type ScenarioMetrics } from "@/lib/api";

const SCENARIO_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  FAILED_PAYMENT:       { label: "Failed Payments",       color: "border-red-200 bg-red-50",    dot: "bg-red-400"    },
  FAILED_SUBSCRIPTION:  { label: "Failed Subscriptions",  color: "border-amber-200 bg-amber-50", dot: "bg-amber-400"  },
  CHECKOUT_ABANDONMENT: { label: "Checkout Abandonment",  color: "border-purple-200 bg-purple-50",dot: "bg-purple-400" },
};

export function ScenarioBreakdown({ data }: { data: Record<string, ScenarioMetrics> }) {
  return (
    <div className="card-surface p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-1">Recovery by Scenario</h3>
      <p className="text-xs text-text-secondary mb-4">All three recovery scenario types</p>
      <div className="grid gap-4 md:grid-cols-3">
        {Object.entries(data).map(([scenario, metrics]) => {
          const cfg = SCENARIO_CONFIG[scenario] ?? { label: scenario, color: "border-gray-200 bg-gray-50", dot: "bg-gray-400" };
          const rate = metrics.revenue_at_risk > 0
            ? (metrics.revenue_recovered / metrics.revenue_at_risk * 100).toFixed(1)
            : "0.0";
          const pct = parseFloat(rate);

          return (
            <div key={scenario} className={`rounded-xl border p-4 ${cfg.color}`}>
              <div className="flex items-center gap-2 mb-3">
                <span className={`h-2.5 w-2.5 rounded-full ${cfg.dot}`} />
                <p className="text-xs font-semibold text-text-primary">{cfg.label}</p>
              </div>
              <div className="space-y-2 text-sm">
                <Row label="Cases"     value={metrics.total.toString()} />
                <Row label="At Risk"   value={formatINR(metrics.revenue_at_risk)}   valueClass="text-danger" />
                <Row label="Recovered" value={formatINR(metrics.revenue_recovered)} valueClass="text-success" />
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-text-secondary">Recovery Rate</span>
                    <span className="font-mono font-bold text-text-primary">{rate}%</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-white/60 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-current transition-all"
                      style={{ width: `${Math.min(pct, 100)}%`, color: pct >= 50 ? "#34d399" : pct >= 25 ? "#fbbf24" : "#f87171" }}
                    />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Row({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-secondary text-xs">{label}</span>
      <span className={`font-mono text-xs font-semibold ${valueClass ?? "text-text-primary"}`}>{value}</span>
    </div>
  );
}
