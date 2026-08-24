"use client";

import { useQuery } from "@tanstack/react-query";
import { getMetricsOverview, formatINR } from "@/lib/api";
import { KpiCard } from "@/components/charts/kpi-card";
import { RecoveryFunnelChart } from "@/components/charts/recovery-funnel";
import { RecoveryByReasonChart } from "@/components/charts/recovery-by-reason";
import { ScenarioBreakdown } from "@/components/charts/scenario-breakdown";
import {
  TrendingUp, AlertTriangle, CheckCircle, Clock, Shield, Users, XCircle, Activity,
} from "lucide-react";

export default function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["metrics-overview"],
    queryFn: () => getMetricsOverview(),
    refetchInterval: 10_000,
  });

  if (isLoading) return <OverviewSkeleton />;
  if (error || !data) return (
    <div className="flex items-center justify-center h-48 rounded-xl border border-danger/20 bg-danger-soft/40 text-danger text-sm">
      Failed to load metrics — check backend connection.
    </div>
  );

  const recoveryRateColor =
    data.recovery_rate_pct >= 60 ? "text-success" :
    data.recovery_rate_pct >= 30 ? "text-warning" : "text-danger";

  return (
    <div className="space-y-6">

      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">
            Revenue Recovery Console
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">
            All numbers computed from verified recovery data — nothing fabricated
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-success-soft border border-success/20 text-success text-xs font-semibold">
          <Activity className="h-3.5 w-3.5 animate-pulse" />
          Live · Refreshing every 10s
        </div>
      </div>

      {/* Primary KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          label="Revenue at Risk"
          value={formatINR(data.revenue_at_risk_paise)}
          icon={<AlertTriangle className="h-4 w-4 text-danger" />}
          variant="danger"
          sub="Active recovery opportunities"
        />
        <KpiCard
          label="Revenue Recovered"
          value={formatINR(data.revenue_recovered_paise)}
          icon={<TrendingUp className="h-4 w-4 text-success" />}
          variant="success"
          sub="Verified by Recovery Verifier"
        />
        <KpiCard
          label="Recovery Rate"
          value={`${data.recovery_rate_pct.toFixed(1)}%`}
          icon={<CheckCircle className="h-4 w-4" />}
          valueClass={recoveryRateColor}
          sub="Recovered / At-risk revenue"
        />
        <KpiCard
          label="Active Cases"
          value={data.active_cases.toString()}
          icon={<Clock className="h-4 w-4 text-warning" />}
          variant="warn"
          sub="Agent currently working"
        />
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard label="Total Cases"    value={data.total_cases.toString()}      icon={<Users className="h-4 w-4 text-text-secondary" />} compact />
        <KpiCard label="Escalated"      value={data.escalated_cases.toString()}  icon={<AlertTriangle className="h-4 w-4 text-warning" />}  variant="warn"    compact />
        <KpiCard label="Failed"         value={data.failed_cases.toString()}     icon={<XCircle className="h-4 w-4 text-danger" />}         variant="danger"  compact />
        <KpiCard
          label="Policy Violations"
          value={data.policy_violations.toString()}
          icon={<Shield className="h-4 w-4" />}
          variant={data.policy_violations === 0 ? "success" : "danger"}
          sub={data.policy_violations === 0 ? "✓ Zero violations — safety boundary held" : "⚠ Review audit trail"}
          compact
        />
      </div>

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <RecoveryFunnelChart data={data} />
        <RecoveryByReasonChart data={data.by_failure_reason} />
      </div>

      <ScenarioBreakdown data={data.by_scenario} />
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-7 w-72 bg-gray-200 rounded-lg" />
      <div className="grid grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 bg-gray-100 border border-gray-200 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="h-56 bg-gray-100 border border-gray-200 rounded-xl" />
        <div className="h-56 bg-gray-100 border border-gray-200 rounded-xl" />
      </div>
    </div>
  );
}
