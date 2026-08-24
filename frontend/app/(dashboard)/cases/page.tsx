"use client";

import { useQuery } from "@tanstack/react-query";
import { listRecoveryCases, formatINR } from "@/lib/api";
import { useState } from "react";
import Link from "next/link";
import { clsx } from "clsx";
import { formatDate } from "@/lib/utils";
import { Search, ChevronRight, TrendingUp } from "lucide-react";

const STATUS_STYLE: Record<string, string> = {
  RECOVERED:  "status-recovered",
  ESCALATED:  "status-escalated",
  FAILED:     "status-failed",
  STOPPED:    "status-stopped",
  WAITING:    "text-blue-500 bg-blue-50 border-blue-200",
  DIAGNOSING: "text-purple-500 bg-purple-50 border-purple-200",
  DETECTED:   "text-sky-500 bg-sky-50 border-sky-200",
};

const SCENARIO_LABELS: Record<string, string> = {
  FAILED_PAYMENT:       "Payment",
  FAILED_SUBSCRIPTION:  "Subscription",
  CHECKOUT_ABANDONMENT: "Checkout",
};

const SCENARIOS  = ["", "FAILED_PAYMENT", "FAILED_SUBSCRIPTION", "CHECKOUT_ABANDONMENT"];
const STATUSES   = ["", "RECOVERED", "ESCALATED", "FAILED", "STOPPED", "DETECTED", "DIAGNOSING"];

export default function CasesPage() {
  const [scenario,      setScenario]      = useState("");
  const [status,        setStatus]        = useState("");
  const [searchQuery,   setSearchQuery]   = useState("");

  const { data: cases, isLoading } = useQuery({
    queryKey: ["cases", scenario, status],
    queryFn: () => listRecoveryCases({ scenario: scenario || undefined, status: status || undefined, limit: 100 }),
    refetchInterval: 8_000,
  });

  const filtered = (cases ?? []).filter(c =>
    !searchQuery ||
    c.failure_reason.includes(searchQuery.toUpperCase()) ||
    c.id.includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">Recovery Cases</h1>
          <p className="text-sm text-text-secondary mt-0.5">{filtered.length} cases</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-4 w-4 text-text-tertiary" />
          <input
            className="pl-8 pr-3 py-1.5 rounded-lg border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 w-48"
            placeholder="Search cases…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
        <select className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
          value={scenario} onChange={e => setScenario(e.target.value)}>
          <option value="">All Scenarios</option>
          {SCENARIOS.filter(Boolean).map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
          value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">All Statuses</option>
          {STATUSES.filter(Boolean).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="card-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-surface-elevated">
            <tr>
              {["Scenario", "Failure Reason", "Amount at Risk", "Status", "Recovered", "Retries", "Score", ""].map((h, i) => (
                <th key={i} className="px-4 py-3 text-left label-xs">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded w-24" /></td>
                    ))}
                  </tr>
                ))
              : filtered.map(c => (
                  <tr key={c.id} className="hover:bg-surface-elevated transition-colors group">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={clsx(
                          "h-2 w-2 rounded-full shrink-0",
                          c.scenario === "FAILED_PAYMENT" ? "bg-danger" :
                          c.scenario === "FAILED_SUBSCRIPTION" ? "bg-warning" : "bg-purple-400"
                        )} />
                        <span className="text-sm font-medium text-text-primary">
                          {SCENARIO_LABELS[c.scenario] ?? c.scenario}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text-secondary">
                      {c.failure_reason.replace(/_/g, " ")}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-text-primary">
                      {formatINR(c.amount_at_risk_paise)}
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx(
                        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold",
                        STATUS_STYLE[c.status] ?? "text-text-secondary bg-gray-50 border-gray-200"
                      )}>
                        {c.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold">
                      {c.is_recovered ? (
                        <span className="text-success flex items-center gap-1">
                          <TrendingUp className="h-3 w-3" />
                          {formatINR(c.amount_recovered_paise)}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-center text-text-secondary">{c.retry_count}</td>
                    <td className="px-4 py-3">
                      {c.recovery_score != null && (
                        <div className="flex items-center gap-1.5">
                          <div className="h-1.5 w-12 rounded-full bg-gray-200 overflow-hidden">
                            <div className="h-full bg-brand-primary rounded-full" style={{ width: `${c.recovery_score}%` }} />
                          </div>
                          <span className="font-mono text-xs text-text-secondary">{Math.round(c.recovery_score)}</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/cases/${c.id}`} className="opacity-0 group-hover:opacity-100 transition-opacity">
                        <ChevronRight className="h-4 w-4 text-brand-primary" />
                      </Link>
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
        {!isLoading && filtered.length === 0 && (
          <div className="px-4 py-10 text-center text-text-tertiary text-sm">
            No cases found.
          </div>
        )}
      </div>
    </div>
  );
}
