import { Link } from "wouter";
import { BarChart3, CheckCircle, FlaskConical, RefreshCw, Shield, Zap } from "lucide-react";
import { ButtonLink, FAQ, FeatureCard, PageFrame, SectionHeading } from "@/components/SiteShell";

export default function SimulationPage() {
  return (
    <PageFrame>
      <main>
        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className="subpage-hero">
          <div className="container subpage-hero-inner">
            <div className="subpage-hero-copy">
              <span className="eyebrow">Platform / Simulation Lab</span>
              <h1>Test recovery at <em>any scale.</em></h1>
              <p>Reproducible batch experiments with seeded RNG. Run AI and Baseline modes on identical datasets. Every result from real execution — never fabricated.</p>
              <div className="hero-actions">
                <ButtonLink href="/dashboard/">Open the lab</ButtonLink>
                <Link className="text-link" href="/pricing/">See pricing ↗</Link>
              </div>
            </div>
            <div className="subpage-hero-art">
              <div style={{ padding: 28, background: "#0f1d38", borderRadius: 10, boxShadow: "20px 20px 0 #dce6ff" }}>
                <div style={{ marginBottom: 14, fontSize: 10, color: "#8da4d3", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase" }}>
                  Simulation Lab — Configure
                </div>
                {[
                  ["Payment Events",  "1,000"],
                  ["Customers",       "100"],
                  ["Failure Rate",    "15%"],
                  ["Random Seed",     "42"],
                  ["Label",           "AI Run vs Baseline"],
                ].map(([label, value]) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,.07)", fontSize: 12 }}>
                    <span style={{ color: "#8da4d3" }}>{label}</span>
                    <span style={{ color: "#e7ff8a", fontFamily: "monospace", fontWeight: 700 }}>{value}</span>
                  </div>
                ))}
                <div style={{ marginTop: 18, display: "flex", gap: 10 }}>
                  <div style={{ flex: 1, padding: "10px 0", background: "#1747f5", borderRadius: 5, textAlign: "center", fontSize: 12, fontWeight: 700, color: "#fff" }}>
                    ▶ Run AI
                  </div>
                  <div style={{ flex: 1, padding: "10px 0", background: "rgba(255,255,255,.07)", borderRadius: 5, textAlign: "center", fontSize: 12, fontWeight: 700, color: "#8da4d3" }}>
                    ⟳ Baseline
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Stats band ─────────────────────────────────────────── */}
        <section className="stats-band">
          <div className="container">
            <div className="stat-strip">
              <div className="stat"><strong>Seeded RNG</strong><span>reproducible results</span></div>
              <div className="stat"><strong>Baseline vs AI</strong><span>same dataset, fair comparison</span></div>
              <div className="stat"><strong>0 fabricated</strong><span>numbers — real execution only</span></div>
              <div className="stat"><strong>Live progress</strong><span>watch the run in real time</span></div>
            </div>
          </div>
        </section>

        {/* ── How it works ───────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <SectionHeading
              eyebrow="How simulation works"
              title="Three steps to a valid comparison."
              description="Configure once. Run both modes. The results speak for themselves — no cherry-picking, no fabrication."
            />
            <div className="steps-grid">
              {[
                {
                  n: "01",
                  title: "Configure the batch",
                  body:  "Set event count, customer count, failure rate, failure distribution, and a random seed. Use the same seed for both AI and Baseline to ensure a fair comparison.",
                  icon:  FlaskConical,
                },
                {
                  n: "02",
                  title: "Run AI + Baseline",
                  body:  "The AI run uses the full LangGraph agent with diagnosis, strategy, and policy gating. The Baseline uses a fixed retry schedule — no diagnosis, no context.",
                  icon:  RefreshCw,
                },
                {
                  n: "03",
                  title: "Compare real results",
                  body:  "Recovery rate, revenue recovered, escalations, policy violations — all computed from what actually happened in the simulation. The dashboard labels everything clearly.",
                  icon:  BarChart3,
                },
              ].map((s) => (
                <div key={s.n} className="step-card">
                  <span className="step-number">{s.n}</span>
                  <h3>{s.title}</h3>
                  <p>{s.body}</p>
                  <s.icon size={22} className="step-icon" />
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Feature cards ──────────────────────────────────────── */}
        <section className="section section-mist">
          <div className="container">
            <SectionHeading
              eyebrow="What the simulation measures"
              title="Metrics from real execution."
              description="The Simulation Lab never manufactures an improvement. It reports whatever the run actually produces."
            />
            <div className="feature-grid">
              <FeatureCard
                icon={BarChart3}
                eyebrow="Recovery metrics"
                title="Revenue at risk vs recovered."
                description="Recovery rate, failed recovery amount, avg recovery time, cost per recovery — all computed from stored run data."
                href="/dashboard/"
              />
              <FeatureCard
                icon={Shield}
                eyebrow="Safety metrics"
                accent="lime"
                title="Policy violations: always zero."
                description="Policy violations are tracked per run. The expected value is zero. Any violation is surfaced immediately and clearly labelled BASELINE vs AI."
                href="/dashboard/"
              />
              <FeatureCard
                icon={Zap}
                eyebrow="Efficiency metrics"
                accent="ink"
                title="Unnecessary interventions vs smart targeting."
                description="See how many interventions the Baseline fires versus how many the AI route uses — with what recovered revenue per intervention."
                href="/dashboard/"
              />
            </div>
          </div>
        </section>

        {/* ── Presets ────────────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <SectionHeading
              eyebrow="Quick presets"
              title="Start in under a minute."
            />
            <div className="metric-grid">
              {[
                { title: "Quick Demo",    events: "100",    customers: "20",  seed: "42", body: "Fast feedback loop. Good for first-run exploration." },
                { title: "Standard Run", events: "1,000",  customers: "100", seed: "42", body: "Representative scale. Use this for baseline comparisons." },
                { title: "Large Batch",  events: "10,000", customers: "500", seed: "42", body: "Stress-test recovery logic across a realistic event volume." },
              ].map((p) => (
                <div key={p.title} className="metric-card">
                  <div className="metric-icon"><FlaskConical size={18} /></div>
                  <h3>{p.title}</h3>
                  <p>{p.body}</p>
                  <div style={{ marginTop: 12, fontSize: 11, fontFamily: "monospace", color: "#6b7890", lineHeight: 1.8 }}>
                    {p.events} events · {p.customers} customers · seed {p.seed}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── FAQ ─────────────────────────────────────────────────── */}
        <section className="section section-mist">
          <div className="container">
            <div className="faq-wrap">
              <div>
                <SectionHeading eyebrow="Simulation questions" title="Before you run the first batch." />
                <ButtonLink href="/dashboard/" variant="outline">Open the lab</ButtonLink>
              </div>
              <FAQ items={[
                "How do I run a simulation?",
                "Is this a real payment system?",
                "Where do the dashboard numbers come from?",
                "Can the AI override merchant policy?",
              ]} />
            </div>
          </div>
        </section>

        {/* ── CTA ─────────────────────────────────────────────────── */}
        <section className="cta-band">
          <div className="container">
            <div className="cta-inner">
              <div>
                <span className="eyebrow">Simulation Lab</span>
                <h2>See the recovery rate before you ship anything.</h2>
              </div>
              <div>
                <p>Run AI and Baseline on the same dataset. Real results, not demos.</p>
                <ButtonLink href="/dashboard/" variant="dark">Open the lab</ButtonLink>
              </div>
            </div>
          </div>
        </section>
      </main>
    </PageFrame>
  );
}
