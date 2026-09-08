import { useState } from "react";
import { ArrowUpRight, Banknote, Check, CreditCard, FileText, Landmark, ShieldCheck, Sparkles, WalletCards } from "lucide-react";
import { Link } from "wouter";
import { ButtonLink, FAQ, PageFrame, SectionHeading } from "@/components/SiteShell";

/**
 * Editorial Blue Ledger pricing reminder:
 * Use confident offer-led hierarchy, strong ink/cobalt contrast, simple
 * comparison structures, and transparent copy without fake social proof.
 */

export default function Pricing() {
  const [active, setActive] = useState("Payment gateway");
  const products = ["Payment gateway", "Payouts", "Banking+", "Payroll"];
  return <PageFrame>
    <main>
      <section className="pricing-hero"><div className="container"><div className="section-heading"><span className="eyebrow">Pricing that stays legible</span><h1>Start with the layer you need. <em>Keep the options.</em></h1><p>Simple starting points for ambitious teams. Connect what matters now and add the rest when the operation grows.</p></div><div className="pricing-card"><div className="pricing-card-copy"><span>Ledgerly Payment Gateway</span><strong>2.0%</strong><p>Platform fee on every successful domestic transaction. No setup fee. No annual maintenance charge.</p><ButtonLink href="/signup/">Start for free</ButtonLink></div><div className="pricing-card-accent"><span>Built for first motion ↗</span></div></div></div></section>
      <section className="section"><div className="container"><SectionHeading eyebrow="One suite, a clear choice" title="See what fits the way you operate." description="Explore the pieces of the stack side by side. You can always add more as your business finds its next rhythm." /><div className="pricing-tabs">{products.map(item => <button key={item} className={active === item ? "active" : ""} onClick={() => setActive(item)}>{item}</button>)}</div><div className="comparison-table"><div className="comparison-row comparison-head"><span>{active}</span><span>Starter</span><span>Scale</span><span>Custom</span></div>{getRows(active).map(([label, starter, scale, custom]) => <div className="comparison-row" key={label}><span>{label}</span><span>{starter}</span><span>{scale}</span><span>{custom}</span></div>)}</div></div></section>
      <section className="section section-mist"><div className="container"><div className="feature-grid"><PricePromo icon={Banknote} eyebrow="Banking+" title="Banking made close to the business." body="Current accounts, cards, and payouts that give your finance team a cleaner way to operate." href="/x/" /><PricePromo icon={Sparkles} eyebrow="Payroll" title="Three clicks. Payroll fixed." body="Run salary, reimbursements, and compliance from a calm workspace built for teams." href="/payroll/" /><PricePromo icon={ShieldCheck} eyebrow="Developer layer" title="Build once. See the whole route." body="Connect payments, webhooks, and reconciliations with docs that keep the path short." href="/docs/" /></div></div></section>
      <section className="section"><div className="container"><div className="faq-wrap"><div><SectionHeading eyebrow="Before you choose" title="Pricing should answer, not distract." description="Here are the details teams usually want before they start a conversation." /><ButtonLink href="/support/" variant="outline">Ask a question</ButtonLink></div><FAQ items={["What is included in the starting platform fee?", "Are there setup fees or annual maintenance charges?", "Can I combine Payments and Banking+?", "Do you offer custom pricing for higher volumes?", "Can I test the dashboard before I commit?", "How do I get an implementation walkthrough?"]} /></div></div></section>
      <section className="cta-band"><div className="container"><div className="cta-inner"><div><span className="eyebrow">Make the first move</span><h2>Start clear. Scale without a rebuild.</h2></div><div><p>Pick a starting layer and keep the rest of the operating system in reach.</p><ButtonLink href="/signup/" variant="dark">Start for free</ButtonLink></div></div></div></section>
    </main>
  </PageFrame>;
}

function PricePromo({ icon: Icon, eyebrow, title, body, href }: { icon: React.ComponentType<{ size?: number }>; eyebrow: string; title: string; body: string; href: string }) { return <Link href={href} className="feature-card accent-ink"><div className="feature-top"><span className="feature-icon"><Icon size={19} /></span><ArrowUpRight size={18} /></div><span className="eyebrow">{eyebrow}</span><h3>{title}</h3><p>{body}</p><span className="feature-line" /></Link>; }

function getRows(active: string) {
  if (active === "Payouts") return [["Approval flows", "Included", "Included", "Tailored"], ["Bulk transfers", "Included", "Included", "Included"], ["Reconciliation view", "Basic", "Advanced", "Advanced"], ["Support", "Email", "Priority", "Dedicated"]];
  if (active === "Banking+") return [["Current account", "Available", "Available", "Available"], ["Spend controls", "Basic", "Advanced", "Custom"], ["Payouts workspace", "Included", "Included", "Included"], ["Support", "Email", "Priority", "Dedicated"]];
  if (active === "Payroll") return [["Salary processing", "Included", "Included", "Included"], ["Compliance workflows", "Basic", "Advanced", "Custom"], ["Reports and insights", "Basic", "Advanced", "Advanced"], ["Support", "Email", "Priority", "Dedicated"]];
  return [["Domestic methods", "100+", "100+", "100+"], ["Payment links", "Included", "Included", "Included"], ["Dashboard access", "Included", "Included", "Included"], ["Support", "Email", "Priority", "Dedicated"]];
}
