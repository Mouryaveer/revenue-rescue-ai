"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { getRecoveryCase, getAuditTrail, runAgent, escalateCase, formatINR } from "@/lib/api";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { clsx } from "clsx";
import { CheckCircle, AlertTriangle, ArrowLeft, Play, Users, ChevronRight } from "lucide-react";
import { AuditTimeline } from "@/components/audit/audit-timeline";
import { formatDate } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  RECOVERED: "status-recovered",
  ESCALATED: "status-escalated",
  FAILED:    "status-failed",
  STOPPED:   "status-stopped",
  DETECTED:  "text-sky-600 bg-sky-50 border-sky-200",
  DIAGNOSING:"text-purple-600 bg-purple-50 border-purple-200",
};

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const { data: c, isLoading } = useQuery({
    queryKey: ["case", id],
    queryFn: () => getRecoveryCase(id),
    refetchInterval: 4_000,
  });

  const { data: audit } = useQuery({
    queryKey: ["audit", id],
    queryFn: () => getAuditTrail(id),
    refetchInterval: 4_000,
  });

  const { mutate: triggerAgent, isPending: agentRunning } = useMutation({
    mutationFn: () => runAgent(id),
  });

  const { mutate: doEscalate, isPending: escalating } = useMutation({
    mutationFn: () => escalateCase(id),
  });

  if (isLoading) return <DetailSkeleton />;
  if (!c) return (
    <div className="text-center text-danger py-12">Case not found</div>
  );

  const diagnosis = (c as any).diagnosis as Record<string, any> | null;
  const strategy  = (c as any).strategy  as Record<string, any> | null;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <Link href="/cases" className="text-text-secondary hover:text-brand-primary flex items-center gap-1 transition-colors">
          <ArrowLeft className="h-4 w-4" /> Recovery Cases
        </Link>
        <ChevronRight className="h-4 w-4 text-text-tertiary" />
        <span className="text-text-primary font-mono">{id.slice(0,8)}…</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-bold text-text-primary">
              {c.failure_reason.replace(/_/g, " ")}
            </h1>
            <span className={clsx(
              "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              STATUS_STYLE[c.status] ?? "text-text-secondary bg-gray-50 border-gray-200"
            )}>
              {c.status}
            </span>
          </div>
          <p className="text-sm text-text-secondary">
            {c.scenario.replace(/_/g, " ")} · Created {formatDate(c.created_at)}
          </p>
        </div>

        {/* Recovery Confirmation */}
        {c.is_recovered && (
          <div className="recovery-confirmed px-5 py-4 text-center min-w-[180px]">
            <CheckCircle className="h-6 w-6 text-success mx-auto mb-1" />
            <p className="text-[10px] font-semibold text-success uppercase tracking-wider">Recovery Verified</p>
            <p className="text-xl font-mono font-bold text-text-primary mt-0.5">
              {formatINR(c.amount_recovered_paise)}
            </p>
            <p className="text-[10px] text-text-secondary mt-0.5">
              Policy {c.policy_decision} · Attempt #{c.retry_count}
            </p>
          </div>
        )}
      </div>

      {/* Key metrics row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Metric label="Amount at Risk"   value={formatINR(c.amount_at_risk_paise)}     color="text-danger" />
        <Metric label="Recovered"        value={c.is_recovered ? formatINR(c.amount_recovered_paise) : "—"} color="text-success" />
        <Metric label="Retry Count"      value={c.retry_count.toString()}               />
        <Metric label="Recovery Score"   value={c.recovery_score ? `${Math.round(c.recovery_score)}/100` : "—"} />
        <Metric label="Policy Decision"  value={c.policy_decision ?? "Pending"}
          color={c.policy_decision === "APPROVED" ? "text-success" : c.policy_decision === "DENIED" || c.policy_decision === "ESCALATE" ? "text-danger" : "text-text-secondary"} />
      </div>

      {/* Main content grid */}
      <div className="grid gap-5 lg:grid-cols-2">

        {/* Diagnosis + Strategy */}
        <div className="space-y-4">
          <div className="card-surface p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-4">AI Diagnosis</h3>
            {diagnosis ? (
              <div className="space-y-3">
                <InfoRow label="Category"    value={diagnosis.failure_category} mono />
                <InfoRow label="Diagnosis"   value={diagnosis.diagnosis} />
                <InfoRow label="Confidence"  value={`${Math.round((diagnosis.diagnosis_confidence ?? 0) * 100)}%`} mono />
                <InfoRow label="Recoverable" value={diagnosis.is_recoverable ? "Yes" : "No"} />
                <InfoRow label="Human Review" value={diagnosis.needs_human_review ? "Required" : "Not required"} />
                {diagnosis.likely_cause && (
                  <div className="pt-2 border-t border-border">
                    <p className="text-xs text-text-secondary label-xs mb-1">Reasoning</p>
                    <p className="text-sm text-text-primary italic">"{diagnosis.likely_cause}"</p>
                  </div>
                )}
                {diagnosis.notes === "FALLBACK_MODE" && (
                  <p className="text-xs text-text-tertiary bg-gray-50 px-2 py-1 rounded">
                    ⚙ Deterministic fallback mode (no LLM)
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-text-tertiary">Diagnosis pending…</p>
            )}
          </div>

          <div className="card-surface p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-4">Recovery Strategy</h3>
            {strategy ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg bg-brand-soft border border-brand-primary/20">
                  <span className="text-sm font-semibold text-brand-primary">{strategy.recovery_strategy}</span>
                  <span className="text-xs text-brand-primary/70">{Math.round((strategy.confidence ?? 0) * 100)}% confidence</span>
                </div>
                <InfoRow label="Reason" value={strategy.reason} />
                {strategy.requested_action?.delay_hours && (
                  <InfoRow label="Delay" value={`${strategy.requested_action.delay_hours}h`} mono />
                )}
                <InfoRow label="Expected Recovery"
                  value={strategy.expected_recovery_paise ? formatINR(strategy.expected_recovery_paise) : "—"}
                  note="Heuristic estimate only — not authoritative" />
              </div>
            ) : (
              <p className="text-sm text-text-tertiary">Strategy pending…</p>
            )}
          </div>
        </div>

        {/* Audit Timeline */}
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Audit Timeline</h3>
          {audit && audit.length > 0
            ? <AuditTimeline events={audit} />
            : <p className="text-sm text-text-tertiary text-center py-8">No events yet</p>
          }
        </div>
      </div>

      {/* Actions */}
      {!c.is_recovered && !c.is_stopped && (
        <div className="flex gap-3 pt-2">
          <button onClick={() => triggerAgent()} disabled={agentRunning}
            className="flex items-center gap-2 rounded-lg bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50 transition-colors shadow-sm">
            <Play className="h-4 w-4" />
            {agentRunning ? "Running…" : "Run Agent"}
          </button>
          <button onClick={() => doEscalate()} disabled={escalating}
            className="flex items-center gap-2 rounded-lg border border-warning/40 px-5 py-2.5 text-sm font-medium text-warning hover:bg-warning/5 disabled:opacity-50 transition-colors">
            <AlertTriangle className="h-4 w-4" />
            {escalating ? "Escalating…" : "Escalate to Human"}
          </button>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <p className="label-xs mb-1">{label}</p>
      <p className={clsx("font-mono font-bold text-lg leading-tight", color ?? "text-text-primary")}>{value}</p>
    </div>
  );
}

function InfoRow({ label, value, mono, note }: { label: string; value: string; mono?: boolean; note?: string }) {
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm text-text-secondary shrink-0">{label}</span>
        <span className={clsx("text-sm text-right", mono ? "font-mono font-medium text-text-primary" : "text-text-primary")}>{value}</span>
      </div>
      {note && <p className="text-xs text-text-tertiary mt-0.5">{note}</p>}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-6 w-48 bg-gray-100 rounded" />
      <div className="h-10 w-96 bg-gray-100 rounded-xl" />
      <div className="grid grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 bg-gray-100 rounded-xl" />)}
      </div>
      <div className="grid grid-cols-2 gap-5">
        <div className="h-64 bg-gray-100 rounded-xl" />
        <div className="h-64 bg-gray-100 rounded-xl" />
      </div>
    </div>
  );
}
