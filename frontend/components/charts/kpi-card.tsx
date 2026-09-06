import { clsx } from "clsx";

interface KpiCardProps {
  label: string;
  value: string;
  icon?: React.ReactNode;
  sub?: string;
  trend?: { value: string; positive?: boolean };
  variant?: "default" | "success" | "danger" | "warn" | "brand";
  valueClass?: string;
  compact?: boolean;
}

const variantConfig = {
  default:  { border: "border-border",          bg: "bg-surface",           value: "text-text-primary" },
  success:  { border: "border-success/25",       bg: "bg-success-soft/60",   value: "text-success" },
  danger:   { border: "border-danger/25",        bg: "bg-danger-soft/60",    value: "text-danger" },
  warn:     { border: "border-warning/25",       bg: "bg-warning-soft/60",   value: "text-warning" },
  brand:    { border: "border-brand-primary/25", bg: "bg-brand-soft/60",     value: "text-brand-primary" },
};

export function KpiCard({
  label, value, icon, sub, trend, variant = "default", valueClass, compact = false,
}: KpiCardProps) {
  const cfg = variantConfig[variant];
  return (
    <div className={clsx(
      "rounded-xl border shadow-card p-4 flex flex-col gap-2.5 transition-shadow hover:shadow-card-hover",
      cfg.border, cfg.bg
    )}>
      <div className="flex items-center justify-between">
        <span className="label-xs">{label}</span>
        {icon && <span className="opacity-80">{icon}</span>}
      </div>

      <div className="flex items-end justify-between gap-2">
        <span className={clsx(
          "font-mono font-bold tabular-nums tracking-tight leading-none",
          compact ? "text-xl" : "text-2xl",
          valueClass ?? cfg.value
        )}>
          {value}
        </span>
        {trend && (
          <span className={clsx(
            "text-xs font-semibold mb-0.5",
            trend.positive ? "text-success" : "text-danger"
          )}>
            {trend.positive ? "↑" : "↓"} {trend.value}
          </span>
        )}
      </div>

      {sub && (
        <p className="text-xs text-text-secondary leading-snug">{sub}</p>
      )}
    </div>
  );
}
