/**
 * Custom hook for simulation runs list with auto-refresh during active runs.
 */

import { useQuery } from "@tanstack/react-query";
import { listSimulations, type SimulationRunRecord } from "@/lib/api";

export function useSimulations() {
  const query = useQuery<SimulationRunRecord[]>({
    queryKey: ["simulations"],
    queryFn: listSimulations,
    refetchInterval: (query) => {
      // Poll faster while a run is in progress
      const data = query.state.data;
      if (data?.some((r) => r.status === "RUNNING" || r.status === "PENDING")) {
        return 2_000;
      }
      return 10_000;
    },
  });

  const activeRuns = query.data?.filter((r) => r.status === "RUNNING") ?? [];
  const completedRuns = query.data?.filter((r) => r.status === "COMPLETED") ?? [];
  const aiRuns = completedRuns.filter((r) => !r.is_baseline);
  const baselineRuns = completedRuns.filter((r) => r.is_baseline);

  return { ...query, activeRuns, completedRuns, aiRuns, baselineRuns };
}
