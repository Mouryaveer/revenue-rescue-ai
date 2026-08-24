"use client";

import { useQuery } from "@tanstack/react-query";
import { listPolicies, getActivePolicy } from "@/lib/api";
import { Shield, CheckCircle, Lock } from "lucide-react";

export default function PoliciesPage() {
  const { data: policies } = useQuery({ queryKey: ["policies"],       queryFn: listPolicies });
  const { data: active }   = useQuery({ queryKey: ["active-policy"],  queryFn: getActivePolicy });

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">Merchant Policies</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Versioned deterministic authorization gate — the LLM cannot touch this
          </p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-success/10 border border-success/20 text-success text-xs font-semibold">
          <Lock className="h-3.5 w-3.5" />
          Deterministic · Zero LLM
        </div>
      </div>

      {/* Guarantee notice */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-brand-soft border border-brand-primary/20">
        <Shield className="h-4 w-4 text-brand-primary mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-brand-primary">Policy Engine guarantee</p>
          <p className="text-xs text-text-secondary mt-0.5">
            The Policy Engine is independently testable, deterministic, and has zero LLM involvement.
            If it errors for any reason, it fails closed — no financial action executes.
            Every decision records <code className="font-mono bg-white/60 px-1 rounded">policy_id</code> + <code className="font-mono bg-white/60 px-1 rounded">policy_version</code> for complete auditability.
          </p>
        </div>
      </div>

      {/* Active policy */}
      {active && (
        <div className="card-surface p-5">
          <div className="flex items-center gap-2 mb-5">
            <CheckCircle className="h-4 w-4 text-success" />
            <h3 className="text-sm font-semibold text-text-primary">Active Policy — v{active.version}</h3>
            <span className="font-mono text-xs text-text-tertiary">{active.policy_id}</span>
            <span className="ml-auto text-xs font-semibold text-success bg-success/10 px-2 py-0.5 rounded-full">ACTIVE</span>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <PolicySection title="Retry Limits"    config={active.config?.limits as Record<string, unknown>} />
            <PolicySection title="Communication"   config={active.config?.communication as Record<string, unknown>} />
            <PolicySection title="Checkout Rules"  config={active.config?.checkout as Record<string, unknown>} />
            <PolicySection title="Escalation"      config={active.config?.escalation as Record<string, unknown>} />
            <PolicySection title="Stopping Rules"  config={active.config?.stopping as Record<string, unknown>} />
          </div>
        </div>
      )}

      {/* Pipeline visualization */}
      <div className="card-surface p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-4">Authorization Pipeline</h3>
        <div className="space-y-2">
          {[
            "Validate input schema",
            "Load active policy (by version)",
            "Check stopping conditions (highest priority)",
            "Check customer state (opt-out, suspended)",
            "Check monetary limits (max auto-recovery amount)",
            "Check retry limits (max retries)",
            "Check communication limits (max messages)",
            "Check checkout-specific rules",
            "Check timing rules (min retry interval)",
            "Check escalation triggers (UNKNOWN failure, low confidence)",
            "→ ALLOW / DENY / ESCALATE",
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                i === 10 ? "bg-brand-primary text-white" : "bg-surface-elevated border border-border text-text-tertiary"
              }`}>
                {i === 10 ? "→" : i + 1}
              </span>
              <p className={`text-sm ${i === 10 ? "font-semibold text-brand-primary" : "text-text-secondary"}`}>{step}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-text-tertiary mt-4 pt-3 border-t border-border">
          Conflict resolution: specific restriction beats general permission. If ambiguous → fail closed → ESCALATE.
        </p>
      </div>

      {/* Version history */}
      {(policies ?? []).length > 0 && (
        <div className="card-surface overflow-hidden">
          <div className="border-b border-border px-5 py-3">
            <h3 className="text-sm font-semibold text-text-primary">Version History</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-surface-elevated">
              <tr>
                {["Policy ID", "Version", "Status"].map(h => <th key={h} className="px-5 py-3 text-left label-xs">{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(policies ?? []).map(p => (
                <tr key={`${p.policy_id}-${p.version}`} className="hover:bg-surface-elevated">
                  <td className="px-5 py-3 font-mono text-xs text-text-secondary">{p.policy_id}</td>
                  <td className="px-5 py-3 font-mono">v{p.version}</td>
                  <td className="px-5 py-3">
                    {p.is_active
                      ? <span className="text-xs font-semibold text-success bg-success/10 px-2 py-0.5 rounded-full">ACTIVE</span>
                      : <span className="text-xs text-text-tertiary">archived</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PolicySection({ title, config }: { title: string; config?: Record<string, unknown> }) {
  if (!config) return null;
  return (
    <div className="rounded-xl border border-border bg-surface-elevated p-4">
      <p className="label-xs mb-3">{title}</p>
      <div className="space-y-2">
        {Object.entries(config).map(([k, v]) => (
          <div key={k} className="flex justify-between items-center gap-2">
            <span className="text-xs text-text-secondary truncate">{k.replace(/_/g, " ")}</span>
            <span className={`font-mono text-xs font-semibold shrink-0 ${typeof v === "boolean" ? (v ? "text-success" : "text-danger") : "text-text-primary"}`}>
              {typeof v === "boolean" ? (v ? "✓" : "✗") : String(v)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
