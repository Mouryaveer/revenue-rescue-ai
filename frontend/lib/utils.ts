import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format paise to INR display string */
export function formatINR(paise: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(paise / 100);
}

/** Format paise to compact INR (e.g. ₹4.5L) */
export function formatINRCompact(paise: number): string {
  const inr = paise / 100;
  if (inr >= 10_000_000) return `₹${(inr / 10_000_000).toFixed(1)}Cr`;
  if (inr >= 100_000)    return `₹${(inr / 100_000).toFixed(1)}L`;
  if (inr >= 1_000)      return `₹${(inr / 1_000).toFixed(1)}K`;
  return `₹${inr.toFixed(0)}`;
}

/** ISO timestamp to human-readable */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Status → display color class */
export function statusColor(status: string): string {
  const map: Record<string, string> = {
    RECOVERED:  "text-success",
    ESCALATED:  "text-warning",
    FAILED:     "text-destructive",
    STOPPED:    "text-muted-foreground",
    WAITING:    "text-blue-400",
    DIAGNOSING: "text-purple-400",
    DETECTED:   "text-cyan-400",
  };
  return map[status] ?? "text-foreground";
}
