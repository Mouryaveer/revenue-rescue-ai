"use client";

import { clsx } from "clsx";
import { CheckCircle, AlertTriangle, Clock, ArrowRight, Shield, XCircle } from "lucide-react";
import type { AuditEvent } from "@/lib/api";
import { formatINR } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const EVENT_CONFIG: Record<string, { icon: React.ReactNode; color: string }> = {
  CASE_CREATED:            { icon: <Clock className="h-3.5 w-3.5" />,         color: "text-blue-400" },
  DIAGNOSIS_COMPLETED:     { icon: <ArrowRight className="h-3.5 w-3.5" />,    color: "text-purple-400" },
  STRATEGY_PROPOSED:       { icon: <ArrowRight className="h-3.5 w-3.5" />,    color: "text-orange-400" },
  POLICY_APPROVED:         { icon: <CheckCircle className="h-3.5 w-3.5" />,   color: "text-success" },
  POLICY_DENIED:           { icon: <XCircle className="h-3.5 w-3.5" />,       color: "text-destructive" },
  POLICY_ESCALATE:         { icon: <AlertTriangle className="h-3.5 w-3.5" />, color: "text-warning" },
  ACTION_EXECUTED:         { icon: <ArrowRight className="h-3.5 w-3.5" />,    color: "text-cyan-400" },
  REVENUE_RECOVERED:       { icon: <CheckCircle className="h-3.5 w-3.5" />,   color: "text-success" },
  ESCALATED:               { icon: <AlertTriangle className="h-3.5 w-3.5" />, color: "text-warning" },
  STOPPED:                 { icon: <XCircle className="h-3.5 w-3.5" />,       color: "text-muted-foreground" },
  UNAUTHORIZED_ACTION_ATTEMPT: { icon: <Shield className="h-3.5 w-3.5" />,   color: "text-destructive font-bold" },
};

interface AuditTimelineProps {
  events: AuditEvent[];
  compact?: boolean;
}

export function AuditTimeline({ events, compact = false }: AuditTimelineProps) {
  if (!events.length) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No audit events yet.
      </p>
    );
  }

  return (
    <ol className="relative border-l border-border space-y-4 pl-5">
      {events.map((event) => {
        const config = EVENT_CONFIG[event.event_type] ?? {
          icon: <Clock className="h-3.5 w-3.5" />,
          color: "text-muted-foreground",
        };

        return (
          <li key={event.id} className="relative">
            {/* Timeline dot */}
            <span className={clsx(
              "absolute -left-[26px] flex h-5 w-5 items-center justify-center",
              "rounded-full bg-card border border-border",
              config.color,
            )}>
              {config.icon}
            </span>

            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className={clsx("text-xs font-mono font-semibold", config.color)}>
                  {event.event_type}
                </p>
                {!compact && (
                  <p className="text-xs text-muted-foreground">{event.actor}</p>
                )}
                {event.reason && !compact && (
                  <p className="text-xs text-muted-foreground mt-0.5 truncate max-w-xs">
                    {event.reason}
                  </p>
                )}
              </div>

              <div className="text-right shrink-0 space-y-0.5">
                {event.amount_paise != null && (
                  <p className={clsx(
                    "text-xs mono font-semibold",
                    event.event_type === "REVENUE_RECOVERED" ? "text-success" : "text-foreground",
                  )}>
                    {formatINR(event.amount_paise)}
                  </p>
                )}
                {event.policy_version != null && !compact && (
                  <p className="text-xs text-muted-foreground mono">
                    policy v{event.policy_version}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  {formatDate(event.created_at)}
                </p>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
