"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Shield, Server, Brain, FlaskConical, AlertTriangle } from "lucide-react";

export default function SettingsPage() {
  const { data: env } = useQuery({
    queryKey: ["environment"],
    queryFn: () => apiFetch<any>("/environment"),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-text-primary tracking-tight">Settings</h1>
        <p className="text-sm text-text-secondary mt-0.5">Current environment configuration</p>
      </div>

      {/* Environment */}
      <div className="card-surface p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-brand-primary" />
          <h3 className="text-sm font-semibold text-text-primary">Execution Environment</h3>
        </div>
        <SettingRow
          label="Payment Mode"
          value={env?.payment_label ?? "Loading…"}
          description={env?.payment_description}
          badge={env?.payment_mode === "RAZORPAY_TEST" ? "live-test" : "simulation"}
        />
        <SettingRow
          label="LLM Mode"
          value={env?.llm_label ?? "Loading…"}
          description={env?.llm_mode === "AI" ? "Using OpenAI API for diagnosis and strategy" : "Using deterministic rule-based fallback — no API key required"}
        />
        <SettingRow
          label="Demo Mode"
          value={env?.demo_mode ? "Enabled" : "Disabled"}
          description="Use Demo Mode page to run deterministic scenarios"
        />
      </div>

      {/* Safety notice */}
      <div className="card-surface p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-success" />
          <h3 className="text-sm font-semibold text-text-primary">Safety Guarantees</h3>
        </div>
        {[
          ["Synthetic Data Only", "All customer and payment data is synthetic. No real PII is stored."],
          ["No Real Money", "The simulator and Razorpay test mode never process real payments."],
          ["Policy Engine", "All AI actions are gated by the deterministic Policy Engine. It cannot be bypassed."],
          ["Test Credentials Only", "Razorpay integration accepts only keys starting with rzp_test_. Production keys are rejected."],
          ["Idempotency", "All payment events and recovery actions are idempotent. No duplicate processing."],
          ["Audit Trail", "Every decision, action, and policy check is recorded in the append-only audit ledger."],
        ].map(([title, desc]) => (
          <div key={title} className="flex items-start gap-3">
            <div className="h-4 w-4 rounded-full bg-success/20 flex items-center justify-center shrink-0 mt-0.5">
              <div className="h-1.5 w-1.5 rounded-full bg-success" />
            </div>
            <div>
              <p className="text-sm font-medium text-text-primary">{title}</p>
              <p className="text-xs text-text-secondary">{desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Configure */}
      <div className="card-surface p-5">
        <div className="flex items-center gap-2 mb-4">
          <Brain className="h-4 w-4 text-brand-primary" />
          <h3 className="text-sm font-semibold text-text-primary">How to configure</h3>
        </div>
        <p className="text-sm text-text-secondary mb-3">
          Edit <code className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">.env</code> to change the execution mode.
          Restart the backend container after changes.
        </p>
        <div className="bg-gray-900 text-green-400 rounded-lg p-4 font-mono text-xs space-y-1">
          <p className="text-gray-400"># Payment provider</p>
          <p>PAYMENT_PROVIDER=simulator  <span className="text-gray-500"># or: razorpay_test</span></p>
          <p className="text-gray-400 mt-2"># Razorpay test keys (rzp_test_ prefix required)</p>
          <p>RAZORPAY_KEY_ID=rzp_test_...</p>
          <p>RAZORPAY_KEY_SECRET=...</p>
          <p className="text-gray-400 mt-2"># LLM provider</p>
          <p>LLM_PROVIDER=mock  <span className="text-gray-500"># or: openai</span></p>
          <p>OPENAI_API_KEY=sk-...</p>
        </div>
      </div>

      <div className="flex items-start gap-3 p-4 rounded-xl bg-warning/5 border border-warning/20">
        <AlertTriangle className="h-4 w-4 text-warning mt-0.5 shrink-0" />
        <p className="text-xs text-text-secondary">
          Never commit <code className="font-mono bg-warning/10 px-1 rounded">.env</code> to Git.
          Use <code className="font-mono bg-warning/10 px-1 rounded">.env.example</code> as the template.
          Never use production Razorpay keys.
        </p>
      </div>
    </div>
  );
}

function SettingRow({ label, value, description, badge }: { label: string; value: string; description?: string; badge?: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-border last:border-0">
      <div>
        <p className="text-sm font-medium text-text-primary">{label}</p>
        {description && <p className="text-xs text-text-secondary mt-0.5">{description}</p>}
      </div>
      <div className="text-right shrink-0">
        <span className={badge === "live-test"
          ? "badge-razorpay-test"
          : badge === "simulation"
          ? "badge-simulation"
          : "text-sm font-medium text-text-primary"}>
          {value}
        </span>
      </div>
    </div>
  );
}
