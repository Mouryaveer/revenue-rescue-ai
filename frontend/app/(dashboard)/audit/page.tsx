"use client";

import { useQuery } from "@tanstack/react-query";
import { getGlobalAuditLog, formatINR } from "@/lib/api";
import { clsx } from "clsx";
import { formatDate } from "@/lib/utils";
import { CheckCircle, AlertTriangle, Shield, Activity, Clock, XCircle } from "lucide-react";

const EVENT_CONFIG: Record<string, { icon: React.ReactNode; color: string; rowBg: string }> = {
  REVENUE_RECOVERED:           { icon: <CheckCircle className="h-3.5 w-3.5" />, color: "text-success", rowBg: "bg-success/3" },
  CASE_CREATED:                { icon: <Clock className="h-3.5 w-3.5" />,       color: "text-blue-500", rowBg: "" },
  POLICY_APPROVED:             { icon: <Shield className="h-3.5 w-3.5" />,      color: "text-success", rowBg: "" },
  POLICY_DENIED:               { icon: <XCircle className="h-3.5 w-3.5" />,     color: "text-danger",  rowBg: "bg-danger/3" },
  POLICY_ESCALATE:             { icon: <AlertTriangle className="h-3.5 w-3.5" />, color: "text-warning", rowBg: "bg-warning/3" },
  ESCALATED:                   { icon: <AlertTriangle className="h-3.5 w-3.5" />, color: "text-warning", rowBg: "" },
  UNAUTHORIZED_ACTION_ATTEMPT: { icon: <Shield className="h-3.5 w-3.5" />,      color: "text-danger font-bold", rowBg: "bg-danger/5" },
  AGENT_RUN_STARTED:           { icon: <Activity className="h-3.5 w-3.5" />,    color: "text-purple-500", rowBg: "" },
  AGENT_RUN_COMPLETED:         { icon: <Activity className="h-3.5 w-3.5" />,    color: "text-purple-500", rowBg: "" },
};

export default function AuditPage() {
  const { data: events, isLoading } = useQuery({
    queryKey: ["audit-log"],
    queryFn: () => getGlobalAuditLog({ limit: 200 }),
    refetchInterval: 5_000,
  });

  const recovered  = events?.filter(e => e.event_type === "REVENUE_RECOVERED").length ?? 0;
  const denied     = events?.filter(e => e.event_type === "POLICY_DENIED").length ?? 0;
  const escalated  = events?.filter(e => e.event_type === "POLICY_ESCALATE").length ?? 0;
  const violations = events?.filter(e => e.event_type === "UNAUTHORIZED_ACTION_ATTEMPT").length ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">Audit Trail</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Append-only event ledger — every action recorded, nothing deleted
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Recoveries"        value={recovered}  color="text-success" />
        <StatCard label="Policy Denials"    value={denied}     color="text-danger" />
        <StatCard label="Escalations"       value={escalated}  color="text-warning" />
        <StatCard label="Unauthorized Attempts" value={violations} color={violations > 0 ? "text-danger font-bold" : "text-success"} note={violations === 0 ? "Zero — safety boundary held" : "Review immediately"} />
      </div>

      {/* Event table */}
      <div className="card-surface overflow-hidden">
        <div className="border-b border-border px-5 py-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-text-primary">All Events</p>
          <p className="text-xs text-text-secondary">{events?.length ?? 0} events</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b border-border bg-surface-elevated">
              <tr>
                {["Timestamp", "Event", "Actor", "Amount", "Policy v", "Result", "Reason"].map(h => (
                  <th key={h} className="px-4 py-3 text-left label-xs">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono">
              {isLoading
                ? Array.from({ length: 10 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      {Array.from({ length: 7 }).map((_, j) => (
                        <td key={j} className="px-4 py-3"><div className="h-3 bg-gray-100 rounded w-20" /></td>
                      ))}
                    </tr>
                  ))
                : (events ?? []).map(e => {
                    const cfg = EVENT_CONFIG[e.event_type] ?? { icon: <Clock className="h-3.5 w-3.5" />, color: "text-text-secondary", rowBg: "" };
                    return (
                      <tr key={e.id} className={clsx("hover:bg-surface-elevated transition-colors", cfg.rowBg)}>
                        <td className="px-4 py-2.5 text-text-tertiary whitespace-nowrap text-[11px]">
                          {new Date(e.created_at).toISOString().replace("T", " ").slice(0, 19)}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={clsx("flex items-center gap-1.5 font-semibold", cfg.color)}>
                            {cfg.icon}
                            <span className="text-[11px]">{e.event_type}</span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-text-secondary text-[11px]">{e.actor}</td>
                        <td className="px-4 py-2.5 text-[11px]">
                          {e.amount_paise != null
                            ? <span className={e.event_type === "REVENUE_RECOVERED" ? "text-success font-semibold" : "text-text-primary"}>
                                {formatINR(e.amount_paise)}
                              </span>
                            : <span className="text-text-tertiary">—</span>
                          }
                        </td>
                        <td className="px-4 py-2.5 text-center text-text-tertiary text-[11px]">
                          {e.policy_version ?? "—"}
                        </td>
                        <td className="px-4 py-2.5">
                          {e.result && (
                            <span className={clsx(
                              "px-1.5 py-0.5 rounded text-[10px] font-semibold",
                              e.result === "SUCCESS"   ? "bg-success/10 text-success" :
                              e.result === "ERROR"     ? "bg-danger/10 text-danger" :
                              e.result === "ESCALATED" ? "bg-warning/10 text-warning" :
                              "bg-gray-100 text-gray-500"
                            )}>{e.result}</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-text-secondary text-[11px] max-w-xs truncate">
                          {e.reason ?? "—"}
                        </td>
                      </tr>
                    );
                  })}
            </tbody>
          </table>
          {!isLoading && (events ?? []).length === 0 && (
            <div className="px-4 py-10 text-center text-text-tertiary text-sm">
              No audit events yet. Run a simulation or inject a payment event.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, note }: { label: string; value: number; color: string; note?: string }) {
  return (
    <div className="card-surface p-4">
      <p className="label-xs mb-1.5">{label}</p>
      <p className={clsx("font-mono text-2xl font-bold", color)}>{value}</p>
      {note && <p className="text-xs text-text-secondary mt-1">{note}</p>}
    </div>
  );
}
