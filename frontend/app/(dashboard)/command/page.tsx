"use client";

import { useQuery } from "@tanstack/react-query";
import { listRecoveryCases, getRecoveryCase, getAuditTrail, formatINR } from "@/lib/api";
import { useState } from "react";
import { clsx } from "clsx";
import {
  CheckCircle, AlertTriangle, Clock, ArrowRight, Search,
  Bot, Shield, Cpu, Activity, Zap,
} from "lucide-react";
import { AuditTimeline } from "@/components/audit/audit-timeline";

const PIPELINE_NODES = [
  { id: "risk_detection",   label: "Risk Detection",   icon: Search,        color: "bg-blue-100 text-blue-600 border-blue-200" },
  { id: "context_builder",  label: "Context Builder",  icon: Cpu,           color: "bg-purple-100 text-purple-600 border-purple-200" },
  { id: "diagnosis",        label: "Diagnosis",        icon: Bot,           color: "bg-amber-100 text-amber-600 border-amber-200" },
  { id: "strategy",         label: "Strategy",         icon: Zap,           color: "bg-orange-100 text-orange-600 border-orange-200" },
  { id: "policy_check",     label: "Policy Check",     icon: Shield,        color: "bg-cyan-100 text-cyan-600 border-cyan-200" },
  { id: "action_execution", label: "Execute Action",   icon: Activity,      color: "bg-pink-100 text-pink-600 border-pink-200" },
  { id: "verification",     label: "Verification",     icon: CheckCircle,   color: "bg-green-100 text-green-600 border-green-200" },
  { id: "completion",       label: "Completion",       icon: CheckCircle,   color: "bg-gray-100 text-gray-600 border-gray-200" },
];

export default function CommandPage() {
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const { data: cases, isLoading: casesLoading } = useQuery({
    queryKey: ["cases-command"],
    queryFn: () => listRecoveryCases({ limit: 20 }),
    refetchInterval: 5_000,
  });

  const { data: caseDetail } = useQuery({
    queryKey: ["case-detail", selectedCaseId],
    queryFn: () => selectedCaseId ? getRecoveryCase(selectedCaseId) : null,
    enabled: !!selectedCaseId,
    refetchInterval: 3_000,
  });

  const { data: audit } = useQuery({
    queryKey: ["case-audit", selectedCaseId],
    queryFn: () => selectedCaseId ? getAuditTrail(selectedCaseId) : null,
    enabled: !!selectedCaseId,
    refetchInterval: 3_000,
  });

  const nodeTrace: string[] = (caseDetail as any)?.diagnosis
    ? ["risk_detection", "context_builder", "diagnosis", "strategy", "policy_check",
       "action_execution", "verification", "completion"]
    : ["risk_detection"];

  const activeNode = caseDetail?.status === "RECOVERED"
    ? "completion"
    : caseDetail?.status === "ESCALATED"
    ? "escalation"
    : nodeTrace[nodeTrace.length - 1] ?? "risk_detection";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-text-primary tracking-tight">Agent Command Center</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          Live recovery pipeline — watch the agent work in real time
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">

        {/* Case list */}
        <div className="card-surface">
          <div className="p-4 border-b border-border">
            <p className="text-sm font-semibold text-text-primary">Recent Cases</p>
          </div>
          <div className="divide-y divide-border max-h-[520px] overflow-y-auto">
            {casesLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="p-3 animate-pulse">
                    <div className="h-4 bg-gray-100 rounded w-3/4 mb-2" />
                    <div className="h-3 bg-gray-100 rounded w-1/2" />
                  </div>
                ))
              : (cases ?? []).map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedCaseId(c.id)}
                    className={clsx(
                      "w-full text-left p-3 hover:bg-gray-50 transition-colors",
                      selectedCaseId === c.id ? "bg-brand-soft border-l-2 border-brand-primary" : ""
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-xs font-mono text-text-secondary truncate">
                        {c.id.slice(0, 8)}…
                      </span>
                      <StatusDot status={c.status} />
                    </div>
                    <p className="text-sm font-medium text-text-primary truncate">
                      {c.failure_reason.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs text-text-secondary mt-0.5">
                      {formatINR(c.amount_at_risk_paise)} at risk
                      {c.is_recovered && ` · ${formatINR(c.amount_recovered_paise)} recovered`}
                    </p>
                  </button>
                ))}
          </div>
        </div>

        {/* Pipeline visualization — Liquid Glass panel */}
        <div className="glass-panel rounded-xl p-5">
          <p className="text-sm font-semibold text-text-primary mb-4">Recovery Pipeline</p>

          {selectedCaseId ? (
            <div className="space-y-2">
              {PIPELINE_NODES.map((node, i) => {
                const visited = nodeTrace.includes(node.id);
                const isActive = node.id === activeNode && !caseDetail?.is_recovered;
                const Icon = node.icon;

                return (
                  <div key={node.id} className="flex items-center gap-3">
                    {/* Connector */}
                    {i > 0 && (
                      <div className="absolute ml-4 -mt-2 h-2 w-px bg-border" />
                    )}
                    <div className={clsx(
                      "flex h-8 w-8 items-center justify-center rounded-lg border text-xs shrink-0 transition-all",
                      isActive ? `${node.color} node-active` : visited ? "bg-success-soft border-success/30 text-success" : "bg-gray-50 border-gray-200 text-gray-400"
                    )}>
                      {visited && !isActive
                        ? <CheckCircle className="h-4 w-4" />
                        : <Icon className="h-4 w-4" />
                      }
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={clsx(
                        "text-sm font-medium",
                        isActive ? "text-text-primary" : visited ? "text-success" : "text-text-tertiary"
                      )}>
                        {node.label}
                      </p>
                      {isActive && (
                        <p className="text-xs text-text-secondary animate-pulse">Processing…</p>
                      )}
                    </div>
                    {isActive && <Activity className="h-4 w-4 text-brand-primary animate-pulse shrink-0" />}
                    {visited && !isActive && <CheckCircle className="h-4 w-4 text-success shrink-0" />}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-48 text-text-tertiary">
              <Bot className="h-10 w-10 mb-3 opacity-30" />
              <p className="text-sm">Select a case to visualize</p>
            </div>
          )}

          {/* Recovery Confirmed moment */}
          {caseDetail?.is_recovered && (
            <div className="mt-4 recovery-confirmed p-4 rounded-xl">
              <div className="text-center">
                <CheckCircle className="h-8 w-8 text-success mx-auto mb-2" />
                <p className="text-xs font-semibold text-success uppercase tracking-wide mb-1">
                  Recovery Verified
                </p>
                <p className="text-2xl font-mono font-bold text-text-primary">
                  {formatINR(caseDetail.amount_recovered_paise)}
                </p>
                <p className="text-xs text-text-secondary mt-1">
                  Payment confirmed · Policy v{caseDetail.policy_decision}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Agent reasoning + audit timeline */}
        <div className="space-y-4">
          {/* Diagnosis summary */}
          {(caseDetail as any)?.diagnosis && (
            <div className="card-surface p-4">
              <p className="label-xs mb-3">AI Diagnosis</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-text-secondary">Failure category</span>
                  <span className="font-medium font-mono text-xs">
                    {(caseDetail as any).diagnosis?.failure_category}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Confidence</span>
                  <ConfidenceBar value={(caseDetail as any).diagnosis?.diagnosis_confidence ?? 0} />
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Strategy</span>
                  <span className="font-mono text-xs text-brand-primary font-semibold">
                    {(caseDetail as any).strategy?.recovery_strategy ?? "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Policy</span>
                  <PolicyBadge decision={caseDetail?.policy_decision ?? null} />
                </div>
              </div>
              {(caseDetail as any).diagnosis?.likely_cause && (
                <p className="text-xs text-text-secondary mt-3 p-2 bg-gray-50 rounded-lg border border-border italic">
                  "{(caseDetail as any).diagnosis.likely_cause}"
                </p>
              )}
            </div>
          )}

          {/* Audit timeline */}
          <div className="card-surface p-4">
            <p className="label-xs mb-3">Audit Timeline</p>
            {audit && audit.length > 0
              ? <AuditTimeline events={audit} compact />
              : <p className="text-xs text-text-tertiary text-center py-4">No events yet</p>
            }
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    RECOVERED: "bg-success", ESCALATED: "bg-warning",
    FAILED: "bg-danger", STOPPED: "bg-gray-400",
    DETECTED: "bg-blue-400 animate-pulse", DIAGNOSING: "bg-purple-400 animate-pulse",
  };
  return <span className={clsx("h-2 w-2 rounded-full shrink-0", colors[status] ?? "bg-gray-300")} />;
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "bg-success" : pct >= 40 ? "bg-warning" : "bg-danger";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 rounded-full bg-gray-200 overflow-hidden">
        <div className={clsx("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono font-semibold">{pct}%</span>
    </div>
  );
}

function PolicyBadge({ decision }: { decision: string | null }) {
  if (!decision) return <span className="text-xs text-text-tertiary">—</span>;
  const cfg: Record<string, string> = {
    APPROVED: "text-success bg-success-soft px-2 py-0.5 rounded text-xs font-semibold",
    DENIED:   "text-danger bg-danger-soft px-2 py-0.5 rounded text-xs font-semibold",
    ESCALATE: "text-warning bg-warning-soft px-2 py-0.5 rounded text-xs font-semibold",
  };
  return <span className={cfg[decision] ?? "text-xs text-text-secondary"}>{decision}</span>;
}
