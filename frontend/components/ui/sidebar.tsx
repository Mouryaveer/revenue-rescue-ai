"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, List, Bot, Shield, ScrollText,
  FlaskConical, BarChart3, Users, Zap, Settings, Play,
} from "lucide-react";
import { clsx } from "clsx";

const NAV = [
  { href: "/overview",    label: "Overview",         icon: LayoutDashboard },
  { href: "/cases",       label: "Recovery Cases",   icon: List },
  { href: "/command",     label: "Command Center",   icon: Bot },
  { href: "/simulation",  label: "Simulation Lab",   icon: FlaskConical },
  { href: "/analytics",   label: "Analytics",        icon: BarChart3 },
  { href: "/policies",    label: "Policies",         icon: Shield },
  { href: "/audit",       label: "Audit Trail",      icon: ScrollText },
  { href: "/customers",   label: "Customers",        icon: Users },
];

const BOTTOM_NAV = [
  { href: "/demo",      label: "Demo Mode",  icon: Play },
  { href: "/settings",  label: "Settings",   icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 flex-col border-r border-border bg-surface">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-primary">
          <Zap className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-bold text-text-primary leading-none">RevenueRescue</p>
          <p className="text-[10px] text-text-secondary mt-0.5">AI Recovery Agent</p>
        </div>
      </div>

      {/* Primary Nav */}
      <nav className="flex-1 space-y-0.5 p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-150",
                active
                  ? "bg-brand-soft text-brand-primary font-semibold"
                  : "text-text-secondary hover:bg-gray-100 hover:text-text-primary"
              )}
            >
              <Icon className={clsx("h-4 w-4 shrink-0", active ? "text-brand-primary" : "")} />
              {label}
              {(href === "/command") && (
                <span className="ml-auto flex h-4 w-4 items-center justify-center rounded-full bg-brand-primary text-[9px] font-bold text-white">
                  <Play className="h-2 w-2" />
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Nav */}
      <div className="border-t border-border p-3 space-y-0.5">
        {BOTTOM_NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-text-secondary hover:bg-gray-100 hover:text-text-primary transition-all duration-150"
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        ))}
        <div className="px-3 pt-2">
          <p className="text-[10px] text-text-tertiary">Razorpay Buildathon 2026</p>
          <p className="text-[10px] text-text-tertiary">Track 03 — AI Revenue Recovery</p>
        </div>
      </div>
    </aside>
  );
}
