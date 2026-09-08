import { ExternalLink, LayoutDashboard } from "lucide-react";
import { ButtonLink, PageFrame } from "@/components/SiteShell";

const DASHBOARD_URL = "http://localhost:3001";

export default function DashboardPage() {
  return (
    <PageFrame>
      <main>
        <section className="collection-hero">
          <div className="container">
            <span className="eyebrow">Platform / Dashboard</span>
            <h1>The recovery <em>console.</em></h1>
            <p>
              Live KPIs, recovery cases, agent activity, simulation lab, audit trail, and policy engine —
              all wired to real backend data. Nothing fabricated.
            </p>
            <div className="hero-actions" style={{ marginTop: 28 }}>
              <ButtonLink href={DASHBOARD_URL}>Open live console</ButtonLink>
              <a className="text-link" href="/simulation/">Run a simulation ↗</a>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="container">
            <div className="metric-grid">
              {[
                { title: "Overview",          body: "Revenue at risk, revenue recovered, recovery rate, active cases, policy violations — all computed from real stored data." },
                { title: "Recovery Cases",    body: "Filterable list by status, scenario, and failure reason. Click any case to see diagnosis, strategy, policy decision, and audit timeline." },
                { title: "Agent Activity",    body: "Case → Diagnosis → Strategy → Policy → Action → Verification. Every step of the LangGraph pipeline visible per case." },
                { title: "Simulation Lab",    body: "Configure batch experiments, run AI vs Baseline, compare recovery rates. All numbers from real execution." },
                { title: "Audit Trail",       body: "Append-only event ledger. Every POLICY_APPROVED, RETRY_EXECUTED, REVENUE_RECOVERED visible with actor and timestamp." },
                { title: "Policies",          body: "Versioned deterministic policy config. Zero LLM involvement. Fail-closed guarantee. Full authorization pipeline diagram." },
              ].map((item) => (
                <div key={item.title} className="metric-card">
                  <div className="metric-icon"><LayoutDashboard size={18} /></div>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="cta-band">
          <div className="container">
            <div className="cta-inner">
              <div>
                <span className="eyebrow">Live console</span>
                <h2>Start the backend and see recovery happen.</h2>
              </div>
              <div>
                <p>
                  <code style={{ fontFamily: "monospace", fontSize: 13, background: "rgba(20,33,61,.08)", padding: "2px 7px", borderRadius: 4 }}>
                    docker compose up
                  </code>
                  {" "}in the repo root.
                </p>
                <ButtonLink href={DASHBOARD_URL} variant="dark">Open console</ButtonLink>
              </div>
            </div>
          </div>
        </section>
      </main>
    </PageFrame>
  );
}
