import { clsx } from "clsx";

const SCENARIO_CONFIG: Record<string, { label: string; className: string }> = {
  FAILED_PAYMENT:       { label: "Failed Payment",       className: "text-red-400 bg-red-400/10 border-red-400/20" },
  FAILED_SUBSCRIPTION:  { label: "Failed Subscription",  className: "text-orange-400 bg-orange-400/10 border-orange-400/20" },
  CHECKOUT_ABANDONMENT: { label: "Checkout Abandonment", className: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20" },
};

export function ScenarioBadge({ scenario }: { scenario: string }) {
  const config = SCENARIO_CONFIG[scenario] ?? {
    label: scenario.replace(/_/g, " "),
    className: "text-muted-foreground bg-muted/20 border-border",
  };

  return (
    <span className={clsx(
      "inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium",
      config.className
    )}>
      {config.label}
    </span>
  );
}
