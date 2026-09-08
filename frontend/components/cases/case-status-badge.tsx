import { clsx } from "clsx";

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  RECOVERED:       { label: "Recovered",  className: "text-success bg-success/10 border-success/20" },
  ESCALATED:       { label: "Escalated",  className: "text-warning bg-warning/10 border-warning/20" },
  FAILED:          { label: "Failed",     className: "text-destructive bg-destructive/10 border-destructive/20" },
  STOPPED:         { label: "Stopped",    className: "text-muted-foreground bg-muted/20 border-border" },
  WAITING:         { label: "Waiting",    className: "text-blue-400 bg-blue-400/10 border-blue-400/20" },
  DIAGNOSING:      { label: "Diagnosing", className: "text-purple-400 bg-purple-400/10 border-purple-400/20" },
  DETECTED:        { label: "Detected",   className: "text-cyan-400 bg-cyan-400/10 border-cyan-400/20" },
  STRATEGY_PROPOSED: { label: "Strategy", className: "text-orange-400 bg-orange-400/10 border-orange-400/20" },
  POLICY_CHECK:    { label: "Policy",     className: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20" },
  ACTION_EXECUTION: { label: "Executing", className: "text-pink-400 bg-pink-400/10 border-pink-400/20" },
  VERIFICATION:    { label: "Verifying",  className: "text-green-400 bg-green-400/10 border-green-400/20" },
};

interface CaseStatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export function CaseStatusBadge({ status, size = "md" }: CaseStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    className: "text-muted-foreground bg-muted/20 border-border",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded border font-medium",
        size === "sm" ? "px-1.5 py-0.5 text-xs" : "px-2 py-0.5 text-xs",
        config.className
      )}
    >
      {config.label}
    </span>
  );
}
