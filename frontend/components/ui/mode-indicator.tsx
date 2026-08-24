"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Activity, Cpu, FlaskConical } from "lucide-react";

interface EnvData {
  payment_mode: "RAZORPAY_TEST" | "SIMULATION";
  payment_label: string;
  llm_mode: "AI" | "FALLBACK";
  llm_label: string;
  demo_mode: boolean;
  is_synthetic_data: boolean;
}

export function ModeIndicator() {
  const { data } = useQuery<EnvData>({
    queryKey: ["environment"],
    queryFn: () => apiFetch<EnvData>("/environment"),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const isRazorpay = data?.payment_mode === "RAZORPAY_TEST";

  return (
    <div className="flex h-11 items-center justify-between border-b border-border bg-surface px-6">
      <div className="flex items-center gap-3">

        {/* Synthetic data warning — always shown */}
        <span className="badge-synthetic">
          ⚠ Synthetic Data
        </span>

        {/* Payment mode badge */}
        {isRazorpay ? (
          <span className="badge-razorpay-test">
            <Activity className="h-3 w-3" />
            RAZORPAY TEST MODE
          </span>
        ) : (
          <span className="badge-simulation">
            <FlaskConical className="h-3 w-3" />
            SIMULATION MODE
          </span>
        )}

        {/* LLM mode */}
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
          data?.llm_mode === "AI"
            ? "bg-brand-soft text-brand-primary border-brand-primary/30"
            : "bg-gray-100 text-gray-500 border-gray-200"
        }`}>
          <Cpu className="h-3 w-3" />
          {data?.llm_label ?? "FALLBACK MODE"}
        </span>

        {data?.demo_mode && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-600 border border-purple-200">
            DEMO MODE
          </span>
        )}
      </div>

      <span className="text-xs text-text-secondary">
        RevenueRescue AI · Razorpay Buildathon Track 03
      </span>
    </div>
  );
}
