import { useEffect, useState, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Link } from "wouter";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight, ArrowUpRight, BarChart3, Bot, ChevronDown,
  CircleDollarSign, FlaskConical, Menu, RefreshCw, Shield, TrendingUp, X, Zap,
} from "lucide-react";

// ── Nav groups ────────────────────────────────────────────────────────────────
type NavGroup = {
  label: string; eyebrow: string; description: string;
  links: string[][]; icon: LucideIcon;
};
export const navGroups: NavGroup[] = [
  {
    label: "Recovery",
    eyebrow: "Win revenue back",
    description: "Detect, diagnose, and recover failed payments, subscriptions, and abandoned checkouts — automatically.",
    links: [
      ["Failed Payment Recovery",  "/recovery/",    "Retry with context, not just a schedule."],
      ["Subscription Recovery",    "/recovery/",    "Keep recurring revenue from slipping away."],
      ["Checkout Abandonment",     "/recovery/",    "Turn abandoned sessions into completed sales."],
      ["Policy Engine",            "/recovery/",    "Deterministic guardrails the LLM cannot bypass."],
    ],
    icon: RefreshCw,
  },
  {
    label: "Platform",
    eyebrow: "How it works",
    description: "An AI agent pipeline — bounded by policy, verified by the simulator, never fabricating recovery.",
    links: [
      ["AI Agent Pipeline",   "/platform/", "Diagnosis → Strategy → Policy → Action → Verify."],
      ["Payment Simulator",   "/platform/", "Reproducible, seeded, no real credentials."],
      ["Audit Trail",         "/platform/", "Append-only ledger for every decision."],
      ["Merchant Dashboard",  "/dashboard/","Live KPIs from real stored data."],
    ],
    icon: Bot,
  },
  {
    label: "Developers",
    eyebrow: "Build and integrate",
    description: "FastAPI, LangGraph, PostgreSQL. Run locally without any real payment credentials.",
    links: [
      ["API Reference",      "/docs/",     "POST /events, GET /cases, POST /simulation/run."],
      ["Simulation Lab",     "/simulation/","Configurable batch experiments with baseline comparison."],
      ["Policy Schema",      "/docs/",     "Versioned JSON — deterministic, no LLM."],
      ["GitHub",             "/docs/",     "MIT licensed. Docker Compose. One command."],
    ],
    icon: FlaskConical,
  },
];

// ── Brand ─────────────────────────────────────────────────────────────────────
export function BrandLockup({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link href="/" className={`brand-lockup${inverse ? " inverse" : ""}`} aria-label="RevenueRescue AI home">
      <span className="zap-mark" aria-hidden="true">
        <Zap size={15} color="#fff" strokeWidth={2.5} />
      </span>
      <span>RevenueRescue<span style={{ color: inverse ? "#e7ff8a" : "#1747f5", fontWeight: 800 }}> AI</span></span>
    </Link>
  );
}

// ── ButtonLink ────────────────────────────────────────────────────────────────
export function ButtonLink({
  href = "#",
  children,
  variant = "primary",
  className = "",
  icon = true,
}: {
  href?: string;
  children: ReactNode;
  variant?: "primary" | "dark" | "outline" | "text";
  className?: string;
  icon?: boolean;
}) {
  return (
    <Link href={href} className={`button-link button-${variant} ${className}`}>
      <span>{children}</span>
      {icon && <ArrowUpRight size={16} strokeWidth={2.3} />}
    </Link>
  );
}

// ── Header ────────────────────────────────────────────────────────────────────
export function Header() {
  const [open, setOpen] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close mega menu on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(".site-header")) setOpen(null);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <>
      <header className={`site-header${scrolled ? " is-scrolled" : ""}`}>
        <div className="header-inner">
          <BrandLockup />
          <nav className="desktop-nav" aria-label="Primary">
            {navGroups.map((group) => (
              <button
                key={group.label}
                className={`nav-trigger${open === group.label ? " is-open" : ""}`}
                onClick={() => setOpen(open === group.label ? null : group.label)}
                aria-expanded={open === group.label}
              >
                {group.label}
                <ChevronDown size={13} />
              </button>
            ))}
            <Link href="/simulation/" className="nav-link">Simulation</Link>
            <Link href="/pricing/"    className="nav-link">Pricing</Link>
          </nav>
          <div className="header-actions">
            <Link href="/dashboard/" className="login-link">Dashboard</Link>
            <ButtonLink href="/dashboard/" className="header-cta">Try live demo</ButtonLink>
          </div>
          <button className="mobile-menu-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu size={23} />
          </button>
        </div>

        {/* Mega menu */}
        <AnimatePresence>
          {open && (
            <motion.div
              className="mega-menu"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
            >
              <div className="mega-inner">
                {navGroups.filter((g) => g.label === open).map((group) => {
                  const Icon = group.icon;
                  return (
                    <div className="mega-layout" key={group.label}>
                      <div className="mega-intro">
                        <div className="icon-badge"><Icon size={18} /></div>
                        <span className="eyebrow">{group.eyebrow}</span>
                        <h3>{group.label}</h3>
                        <p>{group.description}</p>
                        <Link href={group.links[0][1]} className="mega-view-all" onClick={() => setOpen(null)}>
                          Explore {group.label} <ArrowRight size={16} />
                        </Link>
                      </div>
                      <div className="mega-links">
                        {group.links.map(([title, href, description]) => (
                          <Link href={href} className="mega-link" key={title} onClick={() => setOpen(null)}>
                            <span>
                              <strong>{title}</strong>
                              <small>{description}</small>
                            </span>
                            <ArrowUpRight size={17} />
                          </Link>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="mobile-drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.22 }}
          >
            <div className="mobile-drawer-top">
              <BrandLockup />
              <button onClick={() => setMobileOpen(false)} aria-label="Close navigation">
                <X size={23} />
              </button>
            </div>
            <div className="mobile-nav-list">
              {navGroups.map((group) => (
                <div className="mobile-group" key={group.label}>
                  <span className="eyebrow">{group.eyebrow}</span>
                  <strong>{group.label}</strong>
                  {group.links.map(([title, href]) => (
                    <Link href={href} key={title} onClick={() => setMobileOpen(false)}>
                      {title} <ArrowUpRight size={15} />
                    </Link>
                  ))}
                </div>
              ))}
              <Link href="/simulation/" onClick={() => setMobileOpen(false)}>Simulation <ArrowUpRight size={15} /></Link>
              <Link href="/pricing/"    onClick={() => setMobileOpen(false)}>Pricing <ArrowUpRight size={15} /></Link>
              <ButtonLink href="/dashboard/" className="mobile-cta">Try live demo</ButtonLink>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────
export function Footer() {
  const columns = [
    ["Recovery", [["Failed Payments", "/recovery/"], ["Subscriptions", "/recovery/"], ["Checkout Abandonment", "/recovery/"], ["Pricing", "/pricing/"]]],
    ["Platform",  [["AI Agent Pipeline", "/platform/"], ["Policy Engine", "/platform/"], ["Payment Simulator", "/platform/"], ["Audit Trail", "/platform/"]]],
    ["Developers",[["API Reference", "/docs/"], ["Simulation Lab", "/simulation/"], ["GitHub", "/docs/"], ["Docker Compose", "/docs/"]]],
    ["Company",   [["About", "/about/"], ["Razorpay Buildathon", "/about/"], ["Track 03", "/about/"], ["Contact", "/about/"]]],
  ] as const;

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-top">
          <div>
            <BrandLockup inverse />
            <p>Find revenue that's slipping away — and win it back.<br />Razorpay Buildathon 2026 · Track 03.</p>
          </div>
          <ButtonLink href="/dashboard/" variant="primary">Try live demo</ButtonLink>
        </div>
        <div className="footer-grid">
          {columns.map(([title, links]) => (
            <div key={title} className="footer-column">
              <span className="eyebrow">{title}</span>
              {links.map(([label, href]) => (
                <Link href={href} key={label}>{label}<ArrowUpRight size={14} /></Link>
              ))}
            </div>
          ))}
        </div>
        <div className="footer-bottom">
          <span>© 2026 RevenueRescue AI · Razorpay Buildathon Track 03</span>
          <span className="footer-legal">
            <Link href="/privacy/">Privacy</Link>
            <Link href="/terms/">Terms</Link>
            <Link href="/docs/">Docs</Link>
          </span>
          <div className="socials">
            <span>gh</span><span>𝕏</span><span>in</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── PageFrame ─────────────────────────────────────────────────────────────────
export function PageFrame({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`site-page ${className}`}>
      <Header />
      {children}
      <Footer />
    </div>
  );
}

// ── SectionHeading ────────────────────────────────────────────────────────────
export function SectionHeading({
  eyebrow, title, description, align = "left",
}: { eyebrow?: string; title: string; description?: string; align?: "left" | "center" }) {
  return (
    <div className={`section-heading align-${align}`}>
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </div>
  );
}

// ── FeatureCard ───────────────────────────────────────────────────────────────
export function FeatureCard({
  icon: Icon, eyebrow, title, description, accent = "blue", href = "#",
}: {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  description: string;
  accent?: "blue" | "lime" | "ink";
  href?: string;
}) {
  return (
    <Link href={href} className={`feature-card accent-${accent}`}>
      <div className="feature-top">
        <span className="feature-icon"><Icon size={19} /></span>
        <ArrowUpRight size={18} />
      </div>
      <span className="eyebrow">{eyebrow}</span>
      <h3>{title}</h3>
      <p>{description}</p>
      <span className="feature-line" />
    </Link>
  );
}

// ── FAQ ───────────────────────────────────────────────────────────────────────
const FAQ_ANSWERS: Record<string, string> = {
  "How does the AI propose recovery actions?":
    "The LLM analyses customer context, transaction history, and failure reason to propose a strategy. It never executes — only the deterministic policy engine can authorise an action.",
  "Can the AI override merchant policy?":
    "Never. The Policy Engine is a separate, independently testable module with zero LLM involvement. If it errors for any reason, it fails closed — no financial action executes.",
  "How is recovery success determined?":
    "Only the Recovery Verifier confirms success by reading simulator/database state. The LLM cannot declare revenue recovered.",
  "Is this a real payment system?":
    "No real money moves. Everything runs through a seeded simulator that models realistic payment outcomes without any real credentials.",
  "What failure scenarios does it handle?":
    "Insufficient funds, expired payment method, bank decline, gateway failures, mandate failures, subscription grace periods, and checkout abandonment.",
  "How do I run a simulation?":
    "Configure event count, customer count, failure rate, and random seed in the Simulation Lab. Run AI and Baseline modes on the same seed to compare results.",
  "Does it respect customer opt-outs?":
    "Yes — hard constraint, no override path. Customer opt-outs are checked before any communication action is executed.",
  "Where do the dashboard numbers come from?":
    "Every number is computed from real stored simulation data. Nothing is hard-coded or fabricated.",
};

export function FAQ({ items }: { items: string[] }) {
  const [active, setActive] = useState<number | null>(null);
  return (
    <div className="faq-list">
      {items.map((question, index) => (
        <div className={`faq-item${active === index ? " is-open" : ""}`} key={question}>
          <button onClick={() => setActive(active === index ? null : index)} aria-expanded={active === index}>
            <span>{question}</span>
            <span className="faq-plus">{active === index ? "−" : "+"}</span>
          </button>
          <AnimatePresence initial={false}>
            {active === index && (
              <motion.div
                className="faq-answer"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <p>{FAQ_ANSWERS[question] ?? "We keep the setup clear and practical. Start with the workflow you need and connect your existing stack."}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}

// ── StatStrip ─────────────────────────────────────────────────────────────────
export function StatStrip({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="stat-strip">
      {items.map(([value, label]) => (
        <div className="stat" key={label}>
          <strong>{value}</strong>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── PillTabs ──────────────────────────────────────────────────────────────────
export function PillTabs({ items, active, onChange }: { items: string[]; active: string; onChange: (v: string) => void }) {
  return (
    <div className="pill-tabs" role="tablist">
      {items.map((item) => (
        <button key={item} className={active === item ? "active" : ""} onClick={() => onChange(item)} role="tab" aria-selected={active === item}>
          {item}
        </button>
      ))}
    </div>
  );
}

// ── MiniTag ───────────────────────────────────────────────────────────────────
export function MiniTag({ icon: Icon = TrendingUp, children }: { icon?: LucideIcon; children: ReactNode }) {
  return <span className="mini-tag"><Icon size={13} />{children}</span>;
}

// ── RouteLine ─────────────────────────────────────────────────────────────────
export function RouteLine() {
  return <div className="route-line" aria-hidden="true"><span /><i /><span /><i /><span /></div>;
}

// ── icon map (used in pages) ──────────────────────────────────────────────────
export const iconMap = { BarChart3, Bot, CircleDollarSign, FlaskConical, RefreshCw, Shield, TrendingUp, Zap };
