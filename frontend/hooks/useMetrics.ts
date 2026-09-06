/**
 * Custom hook for dashboard metrics with auto-refresh.
 */

import { useQuery } from "@tanstack/react-query";
import { getMetricsOverview, type MetricsOverview } from "@/lib/api";

export function useMetrics(simulationRunId?: string) {
  return useQuery<MetricsOverview>({
    queryKey: ["metrics-overview", simulationRunId],
    queryFn: () => getMetricsOverview(simulationRunId),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
}
