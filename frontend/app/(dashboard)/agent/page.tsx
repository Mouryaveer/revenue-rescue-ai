"use client";

import { useQuery } from "@tanstack/react-query";
import { listRecoveryCases, formatINR } from "@/lib/api";
import Link from "next/link";
import { clsx } from "clsx";
import { ArrowRight, CheckCircle, AlertTriangle, Clock, Bot } from "lucide-react";

const NODE_STYLE: Record<string, string> = {
  risk_detection:   "bg-blue-50 text-blue-600 border-blue-200",
  context_builder:  "bg-purple-50 text-purple-600 border-purple-200",
  diagnosis:        "bg-amber-50 text-amber-600 border-amber-200",
  strategy:         "bg-orange-50 text-orange-600 border-orange-200",
  policy_check:     "bg-cyan-50 text-cyan-600 border-cyan-200",
  action_execution: "bg-pink-50 text-pink-600 border-pink-200",
  observation:      "bg-gray-50 text-gray-500 border-gray-200",
  verification:     "bg-green-50 text-green-600 border-green-200",
  escalation:       "bg-red-50 text-red-500 border-red-200",
  completion:       "bg-green-50 text-green-600 border-green-200",
};

const PIPELINE = ["risk_detection","diagnosis","strategy","policy_check","action_execution","verification","completion"];

export default function AgentActivityPage() {
  const { data: cases, isLoading } = useQuery({
    queryKey: ["cases-agent"],
    queryFn: () => listRecoveryCases({ limit: 40 }),
    refetchInterval: 6_000,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-text-primary tracking-tight">Agent Activity</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          Recovery pipeline — Case → Diagnosis → Strategy → Policy → Action → Verification
        </p>
      </div>

      {/* Pipeline legend */}
      <div className="card-surface p-4">
        <p className="label-xs mb-3">Pipeline nodes</p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(NODE_STYLE).map(([node, style]) => (
            <span key={node} className={clsx("rounded-lg border px-2.5 py-1 text-xs font-medium", style)}>
              {node.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      </div>

      {/* Cases */}
      <div className="space-y-3">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-20 card-surface animate-pulse" />
            ))
          : (cases ?? []).slice(0, 30).map(c => {
              const recovered = c.is_recovered;
              const escalated = c.status === "ESCALATED";

              return (
                <div key={c.id} className="card-surface p-4 hover:shadow-card-hover transition-shadow">
                  <div className="flex items-start gap-4">
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-text-primary">
                          {c.failure_reason.replace(/_/g, " ")}
                        </span>
                        <span className="text-xs text-text-tertiary">
                          {c.scenario.replace(/_/g, " ")}
                        </span>
                        {recovered
                          ? <span className="flex items-center gap-1 text-xs text-success font-semibold"><CheckCircle className="h-3 w-3" />RECOVERED</span>
                          : escalated
                          ? <span className="flex items-center gap-1 text-xs text-warning font-semibold"><AlertTriangle className="h-3 w-3" />ESCALATED</span>
                          : <span className="flex items-center gap-1 text-xs text-text-tertiary"><Clock className="h-3 w-3" />{c.status}</span>
                        }
                      </div>

                      <p className="text-xs text-text-secondary">
                        {formatINR(c.amount_at_risk_paise)} at risk
                        {recovered && ` · ${formatINR(c.amount_recovered_paise)} verified recovered`}
                      </p>

                      {/* Pipeline visualization */}
                      <div className="flex items-center gap-1 flex-wrap">
                        {PIPELINE.map((node, i) => (
                          <span key={node} className="flex items-center gap-1">
                            <span className={clsx(
                              "rounded border px-1.5 py-0.5 text-[10px] font-medium",
                              NODE_STYLE[node]
                            )}>
                              {node.replace(/_/g, " ")}
                            </span>
                            {i < PIPELINE.length - 1 && (
                              <ArrowRight className="h-2.5 w-2.5 text-text-tertiary shrink-0" />
                            )}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="text-right shrink-0 space-y-1">
                      <p className="label-xs">Policy</p>
                      <p className={clsx("text-sm font-bold mono",
                        c.policy_decision === "APPROVED" ? "text-success" :
                        c.policy_decision === "DENIED"   ? "text-danger" :
                        c.policy_decision === "ESCALATE" ? "text-warning" :
                        "text-text-tertiary"
                      )}>
                        {c.policy_decision ?? "—"}
                      </p>
                      <Link href={`/cases/${c.id}`} className="text-xs text-brand-primary hover:underline">
                        View →
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })
        }
        {!isLoading && (cases ?? []).length === 0 && (
          <div className="card-surface p-12 text-center">
            <Bot className="h-10 w-10 mx-auto text-text-tertiary mb-3 opacity-30" />
            <p className="text-sm text-text-tertiary">No cases yet. Inject a payment event or run a simulation.</p>
          </div>
        )}
      </div>
    </div>
  );
}
