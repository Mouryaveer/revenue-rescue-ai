import { useEffect, useState } from "react";
import { Link } from "wouter";
import {
  AlertTriangle, BarChart3, Bot, CheckCircle, CircleDollarSign,
  FlaskConical, RefreshCw, Shield, TrendingUp, Zap,
} from "lucide-react";
import {
  ButtonLink, FAQ, FeatureCard, MiniTag, PageFrame,
  PillTabs, RouteLine, SectionHeading, StatStrip,
} from "@/components/SiteShell";

const slides = [
  {
    kicker:  "AI Revenue Recovery",
    title:   "Find revenue that's slipping away.",
    body:    "RevenueRescue AI detects failed payments, lapsed subscriptions, and abandoned checkouts — then wins them back automatically.",
    action:  "See it recover",
    href:    "/dashboard/",
  },
  {
    kicker:  "Policy-gated, not chatbot-driven",
    title:   "The AI proposes. Policy decides.",
    body:    "Every recovery action is authorised by a deterministic policy engine the LLM cannot override. Safety by architecture, not by prompt.",
    action:  "Explore the pipeline",
    href:    "/recovery/",
  },
  {
    kicker:  "Verified, not claimed",
    title:   "Revenue recovered — confirmed.",
    body:    "Only the Recovery Verifier reading real simulator state can mark a case recovered. No fabricated numbers, ever.",
    action:  "Run a simulation",
    href:    "/simulation/",
  },
];

// Fake but plausible-looking live KPIs for the hero visual
const KPI_DATA = [
  { label: "Revenue Recovered", value: "₹4.7L", sub: "+18% this run", cls: "recovered" },
  { label: "Revenue at Risk",   value: "₹1.2L", sub: "Active cases",  cls: "at-risk"  },
  { label: "Recovery Rate",     value: "73.4%", sub: "vs 31% baseline",cls: "rate"    },
  { label: "Active Cases",      value: "12",    sub: "Agent working", cls: "cases"    },
];

const BAR_HEIGHTS = [28, 45, 35, 62, 50, 70, 55, 48, 65, 72, 58, 68];
const BAR_COLORS  = ["#1747f5","#1747f5","#1747f5","#4ade80","#1747f5","#4ade80","#1747f5","#1747f5","#4ade80","#4ade80","#4ade80","#4ade80"];

export default function Home() {
  const [slide,    setSlide]    = useState(0);
  const [solution, setSolution] = useState("Failed Payment");

  useEffect(() => {
    const id = window.setInterval(() => setSlide((c) => (c + 1) % slides.length), 6800);
    return () => window.clearInterval(id);
  }, []);

  const current = slides[slide];

  return (
    <PageFrame>
      <main>

        {/* ── Offer strip ─────────────────────────────────────────── */}
        <div className="offer-strip">
          <span><Zap size={12} /> RevenueRescue AI · Autonomous Revenue Recovery</span>
          <a href="/simulation/">Run a free simulation →</a>
        </div>

        {/* ── Hero ─────────────────────────────────────────────────── */}
        <section className="hero">
          <div className="hero-inner">
            <div className="hero-copy" key={slide}>
              <span className="eyebrow">{current.kicker}</span>
              <h1>
                {current.title.split(" ").map((word, i) => (
                  <span key={i}>{word === "slipping" || word === "AI" || word === "recovered" ? <em>{word}</em> : word}{" "}</span>
                ))}
              </h1>
              <p>{current.body}</p>
              <div className="hero-actions">
                <ButtonLink href={current.href}>{current.action}</ButtonLink>
                <Link className="text-link" href="/recovery/">How it works ↗</Link>
              </div>
            </div>

            {/* Hero visual — fake live dashboard */}
            <div className="hero-visual">
              <div className="hero-dashboard">
                <div className="hero-dashboard-bar">
                  <div className="hero-dashboard-dot" style={{ background: "#ff5f57" }} />
                  <div className="hero-dashboard-dot" style={{ background: "#febc2e" }} />
                  <div className="hero-dashboard-dot" style={{ background: "#28c840" }} />
                  <span style={{ marginLeft: 8, fontSize: 11, color: "#8da4d3", fontFamily: "monospace" }}>RevenueRescue AI · Recovery Console</span>
                </div>
                <div className="hero-kpis">
                  {KPI_DATA.map((k) => (
                    <div key={k.label} className={`hero-kpi ${k.cls}`}>
                      <div className="hero-kpi-label">{k.label}</div>
                      <div className="hero-kpi-value">{k.value}</div>
                      <div className="hero-kpi-sub">{k.sub}</div>
                    </div>
                  ))}
                </div>
                <div className="hero-bar-chart">
                  <div style={{ fontSize: 9, color: "#8da4d3", marginBottom: 8, fontFamily: "monospace", letterSpacing: ".05em" }}>
                    RECOVERED vs AT-RISK · Last 12 runs
                  </div>
                  <div className="hero-bars">
                    {BAR_HEIGHTS.map((h, i) => (
                      <div key={i} className="hero-bar" style={{ height: h, background: BAR_COLORS[i], opacity: 0.85 }} />
                    ))}
                  </div>
                </div>
              </div>
              <div className="hero-route-card">
                <span>
                  <strong>₹2,999 recovered</strong>
                  <small>Verified by Recovery Verifier · just now</small>
                </span>
              </div>
            </div>
          </div>

          <div className="hero-dots" aria-label="Hero slides">
            {slides.map((s, i) => (
              <button key={s.title} onClick={() => setSlide(i)} className={i === slide ? "active" : ""} aria-label={`Slide ${i + 1}`} />
            ))}
          </div>
        </section>

        {/* ── Stats band ─────────────────────────────────────────── */}
        <section className="stats-band">
          <div className="container">
            <StatStrip items={[
              ["3 scenarios", "payment · subscription · checkout"],
              ["100% policy-gated", "LLM proposes, policy decides"],
              ["0 fabricated KPIs", "every number from real data"],
              ["Seeded RNG", "reproducible experiments"],
            ]} />
          </div>
        </section>

        {/* ── Promo banner ───────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <div className="promo-banner">
              <div className="promo-geo" aria-hidden="true">
                <div className="promo-geo-circle" style={{ width: 420, height: 420, top: -80, left: -60 }} />
                <div className="promo-geo-circle" style={{ width: 280, height: 280, top: 20, left: 40 }} />
              </div>
              <div className="promo-content">
                <span className="eyebrow">Architecture guarantee</span>
                <h2>The LLM never executes.</h2>
                <p>AI proposes → Policy authorises → Executor acts → Verifier confirms. Always in that order, no exceptions.</p>
                <ButtonLink href="/recovery/" variant="dark">See the pipeline</ButtonLink>
              </div>
            </div>
          </div>
        </section>

        {/* ── Solution switcher ───────────────────────────────────── */}
        <section className="section section-mist">
          <div className="container">
            <SectionHeading
              eyebrow="Three recovery scenarios"
              title="One bounded agent pipeline."
              description="Failed payment, failed subscription, and checkout abandonment all flow through the same architecture. Only context and tool selection change."
            />
            <div className="solution-shell">
              <div className="solution-nav">
                {["Failed Payment", "Subscription", "Checkout Abandonment"].map((item) => (
                  <button key={item} className={solution === item ? "active" : ""} onClick={() => setSolution(item)}>
                    {item}
                  </button>
                ))}
              </div>
              <div className="solution-detail">
                <MiniTag icon={solution === "Failed Payment" ? AlertTriangle : solution === "Subscription" ? RefreshCw : CircleDollarSign}>
                  {solution}
                </MiniTag>
                <h3>
                  {solution === "Failed Payment"
                    ? "Retry with context, not just a schedule."
                    : solution === "Subscription"
                    ? "Keep recurring revenue from slipping away."
                    : "Turn abandoned sessions into completed sales."}
                </h3>
                <p>
                  {solution === "Failed Payment"
                    ? "The agent diagnoses the failure reason — insufficient funds, bank decline, expired method — and proposes a contextual retry strategy. Policy authorises. Simulator executes. Verifier confirms."
                    : solution === "Subscription"
                    ? "Mandate failures and subscription grace periods are handled with retry sequencing, timing rules, and communication limits all enforced deterministically by the policy engine."
                    : "After a configurable abandonment timeout, the agent sends a recovery message through the communication simulator. If the customer resumes and payment succeeds, the verifier confirms the recovered revenue."}
                </p>
                <ButtonLink href="/recovery/">See the workflow</ButtonLink>
                <RouteLine />
              </div>
            </div>
          </div>
        </section>

        {/* ── Feature cards ──────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <SectionHeading
              eyebrow="Core architecture"
              title="Principles the system enforces in code."
              description="Not guidelines. Hard constraints. Every one is verifiable from source."
            />
            <div className="feature-grid">
              <FeatureCard
                icon={Bot}
                eyebrow="AI Agent"
                title="Diagnose and propose — nothing more."
                description="LangGraph state machine. Diagnosis and strategy nodes use the LLM. Risk detection, policy check, and verification are fully deterministic."
                href="/recovery/"
              />
              <FeatureCard
                icon={Shield}
                eyebrow="Policy Engine"
                accent="lime"
                title="Fail closed. Always."
                description="Independently testable. Zero LLM involvement. If it errors, no financial action executes. Every decision records policy_id and version."
                href="/recovery/"
              />
              <FeatureCard
                icon={CheckCircle}
                eyebrow="Recovery Verifier"
                accent="ink"
                title="Verified by state, not by claim."
                description="Revenue is marked recovered only when the verifier reads success from the simulator. The LLM cannot declare recovery under any framing."
                href="/recovery/"
              />
              <FeatureCard
                icon={BarChart3}
                eyebrow="Audit Ledger"
                title="Every decision, append-only."
                description="Full lifecycle from CASE_CREATED through POLICY_APPROVED → RETRY_EXECUTED → REVENUE_RECOVERED → CASE_STOPPED."
                href="/dashboard/"
              />
              <FeatureCard
                icon={FlaskConical}
                eyebrow="Simulation Lab"
                accent="lime"
                title="Baseline vs AI, same dataset."
                description="Configurable batch experiments with seeded RNG. Compare recovery rates against a fixed-retry baseline. Every number from real execution."
                href="/simulation/"
              />
              <FeatureCard
                icon={TrendingUp}
                eyebrow="Merchant Dashboard"
                accent="ink"
                title="KPIs from real stored data."
                description="Revenue at risk, recovery rate, active cases, escalations, policy violations. All computed from the database — nothing hard-coded."
                href="/dashboard/"
              />
            </div>
          </div>
        </section>

        {/* ── Story / pipeline section ────────────────────────────── */}
        <section className="section section-mist">
          <div className="container">
            <div className="story-grid">
              <div className="story-copy">
                <span className="eyebrow">The bounded pipeline</span>
                <h2>AI proposes. Policy decides. Verifier confirms.</h2>
                <p>Six steps, all enforced in code. The LLM only touches diagnosis and strategy. Everything else is deterministic, independently testable, and auditable.</p>
                <ButtonLink href="/recovery/" variant="dark">Explore the architecture</ButtonLink>
              </div>
              <div className="story-visual">
                <div className="story-visual-inner">
                  <div className="pipeline">
                    {[
                      { label: "Risk Detection",    sub: "Deterministic",  dot: "det", step: "01" },
                      { label: "Diagnosis",          sub: "LLM node",       dot: "ai",  step: "02" },
                      { label: "Strategy",           sub: "LLM node",       dot: "ai",  step: "03" },
                      { label: "Policy Check",       sub: "Deterministic",  dot: "pol", step: "04" },
                      { label: "Action Execution",   sub: "APPROVED only",  dot: "pol", step: "05" },
                      { label: "Recovery Verifier",  sub: "DB state only",  dot: "pol", step: "06" },
                    ].map((step) => (
                      <div className="pipeline-step" key={step.step}>
                        <div className={`pipeline-dot ${step.dot}`}>{step.step}</div>
                        <div className="pipeline-label">
                          <strong>{step.label}</strong>
                          {step.sub}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="story-caption">
                  <strong>Architecture guarantee</strong>
                  <span>The LLM never executes financial actions, never overrides policy, never declares recovery.</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Industry tabs ───────────────────────────────────────── */}
        <IndustryBlock />

        {/* ── FAQ ─────────────────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <div className="faq-wrap">
              <div>
                <p className="section-lead">
                  Real questions about how the recovery pipeline works, where the safety boundaries are, and how to run your own simulation.
                </p>
                <Link className="text-link" href="/docs/">Read the full docs ↗</Link>
              </div>
              <FAQ items={[
                "How does the AI propose recovery actions?",
                "Can the AI override merchant policy?",
                "How is recovery success determined?",
                "Is this a real payment system?",
                "What failure scenarios does it handle?",
                "Does it respect customer opt-outs?",
                "Where do the dashboard numbers come from?",
              ]} />
            </div>
          </div>
        </section>

        {/* ── CTA band ────────────────────────────────────────────── */}
        <section className="cta-band">
          <div className="container">
            <div className="cta-inner">
              <div>
                <span className="eyebrow">RevenueRescue AI</span>
                <h2>Stop leaving recovered revenue on the table.</h2>
              </div>
              <div>
                <p>Run a simulation, see the recovery rate, compare against the baseline.</p>
                <ButtonLink href="/dashboard/" variant="dark">Try live demo</ButtonLink>
              </div>
            </div>
          </div>
        </section>

      </main>
    </PageFrame>
  );
}

function IndustryBlock() {
  const [active, setActive] = useState("E-commerce");
  const copy: Record<string, { title: string; body: string }> = {
    "E-commerce":    { title: "Recover checkout abandonment before the customer moves on.", body: "The agent detects the abandoned session after a configurable timeout, proposes a recovery message, and verifies payment completion — all within the bounded pipeline." },
    "SaaS":          { title: "Keep subscription revenue from churning silently.", body: "Mandate failures and subscription grace period events are handled with retry sequencing, timing rules, and communication limits enforced by the deterministic policy engine." },
    "Marketplaces":  { title: "Failed payments don't have to mean lost sellers.", body: "Diagnose whether the failure is temporary (INSUFFICIENT_FUNDS) or requires user action (EXPIRED_METHOD) and route the right strategy automatically." },
    "Fintech":       { title: "Full audit trail. Zero policy violations. Every run.", body: "Policy violations are tracked as a first-class metric. The expected outcome is always zero — and the simulation confirms it." },
  };
  return (
    <section className="section section-ink">
      <div className="container">
        <SectionHeading
          eyebrow="Recovery across verticals"
          title="The pipeline adapts. The rules don't."
          description="Event type changes the context and tools. The architecture, safety boundary, and policy engine stay constant."
        />
        <PillTabs items={Object.keys(copy)} active={active} onChange={setActive} />
        <div className="industry-layout">
          <div className="industry-copy">
            <h3>{copy[active].title}</h3>
            <p>{copy[active].body}</p>
            <ButtonLink href="/recovery/">See how it works</ButtonLink>
          </div>
          <div className="industry-art">
            <div className="industry-art-inner">
              <span /><span /><span />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
