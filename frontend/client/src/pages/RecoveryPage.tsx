import { useState } from "react";
import { Link } from "wouter";
import {
  AlertTriangle, Bot, CheckCircle, CircleDollarSign,
  RefreshCw, Shield, TrendingUp, Zap,
} from "lucide-react";
import { ButtonLink, FAQ, FeatureCard, MiniTag, PageFrame, PillTabs, RouteLine, SectionHeading } from "@/components/SiteShell";

const codeSnippets: Record<string, string> = {
  "Ingest Event": `POST /api/v1/events/payment-failed
{
  "idempotency_key": "evt_abc123",
  "customer_id":     "cust_xyz",
  "amount_paise":    49900,
  "currency":        "INR",
  "failure_reason":  "INSUFFICIENT_FUNDS"
}`,
  "Agent Output": `{
  "diagnosis":          "temporary_payment_failure",
  "diagnosis_confidence": 0.91,
  "recovery_strategy":  "SCHEDULE_RETRY",
  "reason":             "Strong history, temporary failure.",
  "requested_action": {
    "type":         "SCHEDULE_RETRY",
    "delay_hours":  24
  }
}`,
  "Policy Decision": `{
  "allowed":         true,
  "decision":        "APPROVED",
  "reason":          "Within retry limit, amount under threshold.",
  "policy_version":  1,
  "violations":      []
}`,
};

const FAILURE_CODES = [
  { code: "INSUFFICIENT_FUNDS",  category: "Temporary",    strategy: "Delayed retry",           color: "#f59e0b" },
  { code: "EXPIRED_METHOD",      category: "Method issue", strategy: "Request method update",   color: "#ef4444" },
  { code: "GATEWAY_TEMPORARY",   category: "Infra",        strategy: "Retry later",             color: "#6366f1" },
  { code: "BANK_DECLINE",        category: "Bank decline", strategy: "Context-dependent retry", color: "#ec4899" },
  { code: "AUTH_FAILURE",        category: "Auth",         strategy: "Request user action",     color: "#f97316" },
  { code: "MANDATE_FAILURE",     category: "Recurring",    strategy: "Mandate recovery",        color: "#8b5cf6" },
  { code: "SUBSCRIPTION_GRACE",  category: "Subscription", strategy: "Retry sequencing",        color: "#14b8a6" },
  { code: "CHECKOUT_ABANDONED",  category: "Abandonment",  strategy: "Recovery message",        color: "#1747f5" },
];

export default function RecoveryPage() {
  const [tab,      setTab]      = useState("Ingest Event");
  const [scenario, setScenario] = useState("Failed Payment");

  return (
    <PageFrame>
      <main>
        {/* ── Subpage hero ─────────────────────────────────────── */}
        <section className="subpage-hero">
          <div className="container subpage-hero-inner">
            <div className="subpage-hero-copy">
              <span className="eyebrow">Recovery / Pipeline</span>
              <h1>Revenue recovery with <em>no guesswork.</em></h1>
              <p>Three scenarios. One bounded agent. Deterministic policy. Verified outcomes — never claimed by the LLM.</p>
              <div className="hero-actions">
                <ButtonLink href="/dashboard/">See it live</ButtonLink>
                <Link className="text-link" href="/simulation/">Run a simulation ↗</Link>
              </div>
            </div>
            <div className="subpage-hero-art">
              {/* Pipeline visualisation */}
              <div style={{ padding: 28, background: "#f0f4ff", border: "1px solid #d4e0f7", borderLeft: "4px solid #1747f5", borderRadius: 8 }}>
                <div style={{ marginBottom: 20, fontSize: 11, fontWeight: 700, color: "#53637c", textTransform: "uppercase", letterSpacing: ".1em" }}>
                  Recovery State Machine
                </div>
                {[
                  "DETECTED", "DIAGNOSING", "STRATEGY_PROPOSED", "POLICY_CHECK",
                  "ACTION_EXECUTION", "WAITING", "VERIFICATION", "RECOVERED → STOPPED",
                ].map((state, i, arr) => (
                  <div key={state} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: i < arr.length - 1 ? 6 : 0 }}>
                    <span style={{
                      padding: "4px 10px", borderRadius: 4, fontSize: 11, fontWeight: 700,
                      fontFamily: "monospace",
                      background: state.includes("RECOVERED") ? "#dcfce7" : state === "POLICY_CHECK" ? "#eff6ff" : "#f1f5ff",
                      color: state.includes("RECOVERED") ? "#16a34a" : state === "POLICY_CHECK" ? "#1747f5" : "#374151",
                      border: state.includes("RECOVERED") ? "1px solid #86efac" : "1px solid #dde8f6",
                    }}>
                      {state}
                    </span>
                    {i < arr.length - 1 && <span style={{ color: "#94a3b8", fontSize: 12 }}>↓</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Stats ─────────────────────────────────────────────── */}
        <section className="stats-band">
          <div className="container">
            <div className="stat-strip">
              <div className="stat"><strong>8</strong><span>failure codes handled</span></div>
              <div className="stat"><strong>3</strong><span>recovery scenarios</span></div>
              <div className="stat"><strong>0</strong><span>LLM-executed actions</span></div>
              <div className="stat"><strong>25</strong><span>red-team tests passing</span></div>
            </div>
          </div>
        </section>

        {/* ── Scenario tabs ──────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <SectionHeading
              eyebrow="Three scenarios, one pipeline"
              title="Event type determines context. Architecture never changes."
            />
            <PillTabs
              items={["Failed Payment", "Subscription", "Checkout Abandonment"]}
              active={scenario}
              onChange={setScenario}
            />
            <div style={{ display: "grid", gridTemplateColumns: ".9fr 1.1fr", gap: 60, alignItems: "start" }}>
              <div>
                <MiniTag icon={scenario === "Failed Payment" ? AlertTriangle : scenario === "Subscription" ? RefreshCw : CircleDollarSign}>
                  {scenario}
                </MiniTag>
                <h3 style={{ margin: "16px 0 14px", font: "800 38px/1.02 Manrope, sans-serif", letterSpacing: "-.07em" }}>
                  {scenario === "Failed Payment"
                    ? "Diagnose the cause before picking the strategy."
                    : scenario === "Subscription"
                    ? "Retry sequencing within the grace window."
                    : "Recovery message → simulate return → verify."}
                </h3>
                <p style={{ color: "#64728a", lineHeight: 1.65, fontSize: 15 }}>
                  {scenario === "Failed Payment"
                    ? "The agent identifies the failure reason (INSUFFICIENT_FUNDS, BANK_DECLINE, AUTH_FAILURE…) and selects the appropriate recovery strategy. Policy checks retry count, monetary limits, timing rules, and customer opt-out status before authorising any action."
                    : scenario === "Subscription"
                    ? "Mandate failures and subscription grace period events trigger retry sequencing. The policy engine enforces max retries, minimum retry intervals, and communication limits — all deterministic, none LLM-decided."
                    : "After a configurable abandonment timeout, the bounded pipeline kicks in: LLM proposes a recovery message, Policy Engine authorises it (contact allowed? limit reached?), Communication Simulator records the message and returns a resume outcome, Payment Simulator runs the attempt, Recovery Verifier confirms."}
                </p>
                <ButtonLink href="/dashboard/" className="mt-5">See it in action</ButtonLink>
                <RouteLine />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {FAILURE_CODES.filter(f =>
                  scenario === "Failed Payment"      ? !["MANDATE_FAILURE","SUBSCRIPTION_GRACE","CHECKOUT_ABANDONED"].includes(f.code) :
                  scenario === "Subscription"        ? ["MANDATE_FAILURE","SUBSCRIPTION_GRACE"].includes(f.code) :
                  f.code === "CHECKOUT_ABANDONED"
                ).concat(
                  scenario === "Checkout Abandonment" ? FAILURE_CODES.slice(0,2) : []
                ).map((f) => (
                  <div key={f.code} style={{
                    padding: "14px 16px",
                    border: "1px solid #e1e8f4",
                    background: "#fff",
                    borderRadius: 6,
                    borderLeft: `3px solid ${f.color}`,
                  }}>
                    <div style={{ fontFamily: "monospace", fontSize: 10, fontWeight: 700, color: f.color, marginBottom: 5, letterSpacing: ".05em" }}>
                      {f.code}
                    </div>
                    <div style={{ fontSize: 11, color: "#53637c", marginBottom: 4 }}>{f.category}</div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#14213d" }}>{f.strategy}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Code section ───────────────────────────────────────── */}
        <section className="section section-mist">
          <div className="container code-layout">
            <div>
              <SectionHeading
                eyebrow="Three API calls, full recovery"
                title="Ingest event. Agent runs. Revenue verified."
                description="POST an event, the agent diagnoses and proposes, policy authorises, the simulator executes, the verifier confirms. All auditable."
              />
              <ButtonLink href="/docs/">Read the API docs</ButtonLink>
            </div>
            <div className="code-shell">
              <div className="code-tabs">
                <span>Recovery flow</span>
                <div className="code-tabs-btns">
                  {Object.keys(codeSnippets).map((k) => (
                    <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{k}</button>
                  ))}
                </div>
              </div>
              <pre>{codeSnippets[tab]}</pre>
            </div>
          </div>
        </section>

        {/* ── Feature cards ──────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <SectionHeading
              eyebrow="Safety boundaries"
              title="Hard constraints, not guidelines."
            />
            <div className="feature-grid">
              <FeatureCard
                icon={Bot}
                eyebrow="AI bounds"
                title="Diagnose and propose only."
                description="The LLM may interpret context, classify failure, and propose strategy. It cannot execute financial actions, modify policy limits, or declare revenue recovered."
                href="/recovery/"
              />
              <FeatureCard
                icon={Shield}
                eyebrow="Policy bounds"
                accent="lime"
                title="12 sequential checks, fail closed."
                description="Schema validation → stopping conditions → customer state → monetary limits → retry limits → communication limits → timing rules → escalation triggers."
                href="/recovery/"
              />
              <FeatureCard
                icon={CheckCircle}
                eyebrow="Verification bounds"
                accent="ink"
                title="State, not claim."
                description="Revenue recovery is confirmed by the verifier reading DB/simulator state. Not by LLM output. Not by inference. By authoritative transaction state."
                href="/recovery/"
              />
            </div>
          </div>
        </section>

        {/* ── Red team ───────────────────────────────────────────── */}
        <section className="section section-mist">
          <div className="container">
            <SectionHeading
              eyebrow="Red-team test suite"
              title="25 adversarial tests. All passing."
              description="Every safety constraint is verified by an automated test, not just stated in a prompt."
            />
            <div className="no-code-grid">
              {[
                { title: "4th retry blocked",       body: "LLM requests retry #4 → Policy DENY" },
                { title: "Opt-out respected",        body: "Customer opted out → zero contact" },
                { title: "High-value escalated",     body: "₹1L+ → forced human review" },
                { title: "Prompt injection ignored", body: '"ignore policy" in metadata → no effect' },
              ].map((c) => (
                <div key={c.title} className="no-code-card">
                  <CheckCircle size={19} style={{ color: "#1747f5", marginBottom: 28 }} />
                  <strong>{c.title}</strong>
                  <p>{c.body}</p>
                  <Link href="/docs/" className="text-link" style={{ marginTop: 14, fontSize: 11 }}>
                    See test ↗
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── FAQ ─────────────────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <div className="faq-wrap">
              <div>
                <SectionHeading
                  eyebrow="The short version"
                  title="Questions about the recovery pipeline?"
                />
                <ButtonLink href="/simulation/" variant="outline">Run a simulation</ButtonLink>
              </div>
              <FAQ items={[
                "How does the AI propose recovery actions?",
                "Can the AI override merchant policy?",
                "How is recovery success determined?",
                "Is this a real payment system?",
                "What failure scenarios does it handle?",
                "Does it respect customer opt-outs?",
              ]} />
            </div>
          </div>
        </section>

        {/* ── CTA ─────────────────────────────────────────────────── */}
        <section className="cta-band">
          <div className="container">
            <div className="cta-inner">
              <div>
                <span className="eyebrow">Start recovering</span>
                <h2>See recovered revenue in the first simulation run.</h2>
              </div>
              <div>
                <p>Configure events, run AI and Baseline, compare the difference.</p>
                <ButtonLink href="/simulation/" variant="dark">Run a simulation</ButtonLink>
              </div>
            </div>
          </div>
        </section>
      </main>
    </PageFrame>
  );
}
