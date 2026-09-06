import { CheckCircle } from "lucide-react";
import { ButtonLink, FAQ, PageFrame, SectionHeading } from "@/components/SiteShell";

const TIERS = [
  {
    name:     "Simulation",
    price:    "Free",
    sub:      "No credentials required",
    color:    "#1747f5",
    cta:      "Run a simulation",
    href:     "/simulation/",
    features: [
      "Full LangGraph agent pipeline",
      "Configurable batch simulation",
      "Baseline vs AI comparison",
      "All 3 recovery scenarios",
      "Complete audit trail",
      "Policy engine included",
      "No real credentials needed",
    ],
  },
  {
    name:     "Razorpay Test",
    price:    "Buildathon",
    sub:      "Track 03 submission",
    color:    "#14213d",
    cta:      "View on GitHub",
    href:     "/docs/",
    features: [
      "Everything in Simulation",
      "Razorpay test-mode webhooks",
      "Real test payment attempts",
      "Live environment indicators",
      "Docker Compose included",
      "PostgreSQL + Redis",
      "Fully open source",
    ],
  },
];

const COMPARISON_ROWS = [
  ["Feature",                    "Simulation",  "Razorpay Test"],
  ["LangGraph agent",            "✓",           "✓"],
  ["Policy engine",              "✓",           "✓"],
  ["Recovery verifier",          "✓",           "✓"],
  ["Audit trail",                "✓",           "✓"],
  ["Batch simulation",           "✓",           "✓"],
  ["Baseline comparison",        "✓",           "✓"],
  ["Real credentials",           "Seeded sim",  "Razorpay test keys"],
  ["Payment simulator",          "Built-in",    "Built-in + Razorpay"],
  ["Docker Compose",             "✓",           "✓"],
  ["Policy violations = 0",      "Enforced",    "Enforced"],
];

export default function PricingPage() {
  return (
    <PageFrame>
      <main>
        {/* ── Hero ─────────────────────────────────────────────── */}
        <section style={{ padding: "93px 0 110px", background: "#f1f5ff" }}>
          <div className="container">
            <div className="section-heading align-center">
              <span className="eyebrow">Pricing</span>
              <h1 style={{ margin: 0, font: "800 clamp(48px, 7vw, 88px)/.92 Manrope, sans-serif", letterSpacing: "-.09em" }}>
                Start <em style={{ color: "#1747f5", fontStyle: "normal" }}>free.</em><br />No credentials.
              </h1>
              <p style={{ maxWidth: 520, margin: "20px auto 0" }}>
                The full recovery pipeline — AI agent, policy engine, simulator, verifier — runs without any real payment credentials.
              </p>
            </div>
          </div>
        </section>

        {/* ── Tier cards ─────────────────────────────────────────── */}
        <section className="section">
          <div className="container">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, maxWidth: 860, margin: "0 auto" }}>
              {TIERS.map((tier) => (
                <div key={tier.name} style={{
                  padding: "36px 40px",
                  background: tier.name === "Razorpay Test" ? "#14213d" : "#fff",
                  color:      tier.name === "Razorpay Test" ? "#fff" : "#14213d",
                  border:     "1px solid " + (tier.name === "Razorpay Test" ? "#14213d" : "#dde8f6"),
                  borderRadius: 6,
                  boxShadow:  tier.name === "Simulation" ? "18px 18px 0 #dce6ff" : "18px 18px 0 #e7ff8a",
                }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: tier.name === "Razorpay Test" ? "#8da4d3" : "#53637c" }}>
                    {tier.name}
                  </span>
                  <div style={{ margin: "10px 0 8px", font: "800 64px/.9 Manrope, sans-serif", letterSpacing: "-.08em" }}>
                    {tier.price}
                  </div>
                  <p style={{ margin: "0 0 28px", fontSize: 13, color: tier.name === "Razorpay Test" ? "#8da4d3" : "#66748b" }}>
                    {tier.sub}
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 28 }}>
                    {tier.features.map((f) => (
                      <div key={f} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                        <CheckCircle size={14} style={{ color: tier.name === "Razorpay Test" ? "#e7ff8a" : "#1747f5", flexShrink: 0 }} />
                        <span style={{ color: tier.name === "Razorpay Test" ? "#c8d5e8" : "#4a5878" }}>{f}</span>
                      </div>
                    ))}
                  </div>
                  <ButtonLink href={tier.href} variant={tier.name === "Razorpay Test" ? "primary" : "dark"}>
                    {tier.cta}
                  </ButtonLink>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Comparison table ───────────────────────────────────── */}
        <section className="section section-mist">
          <div className="container">
            <SectionHeading eyebrow="Feature comparison" title="Everything that's included." align="center" />
            <div style={{ maxWidth: 700, margin: "0 auto", border: "1px solid #dde5f2", borderRadius: 6, overflow: "hidden" }}>
              {COMPARISON_ROWS.map((row, i) => (
                <div key={i} style={{
                  display: "grid",
                  gridTemplateColumns: "1.6fr 1fr 1fr",
                  borderBottom: i < COMPARISON_ROWS.length - 1 ? "1px solid #e8edf6" : "none",
                  background: i === 0 ? "#f0f4ff" : "#fff",
                }}>
                  {row.map((cell, j) => (
                    <span key={j} style={{
                      padding: "14px 18px",
                      fontSize: 13,
                      fontWeight: i === 0 || j === 0 ? 700 : 400,
                      color: i === 0 ? "#1747f5" : j === 0 ? "#14213d" : "#5f6f87",
                      borderLeft: j > 0 ? "1px solid #e8edf6" : "none",
                    }}>
                      {cell}
                    </span>
                  ))}
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
                <SectionHeading eyebrow="Pricing questions" title="Everything you need to know." />
                <ButtonLink href="/simulation/" variant="outline">Run a simulation</ButtonLink>
              </div>
              <FAQ items={[
                "Is this a real payment system?",
                "Does it respect customer opt-outs?",
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
                <span className="eyebrow">Get started</span>
                <h2>One docker-compose up and you're running.</h2>
              </div>
              <div>
                <p>Full pipeline. No real credentials. No fabricated results.</p>
                <ButtonLink href="/dashboard/" variant="dark">Try live demo</ButtonLink>
              </div>
            </div>
          </div>
        </section>
      </main>
    </PageFrame>
  );
}
