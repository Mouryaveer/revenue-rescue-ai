/**
 * Custom hook for recovery cases list with filtering and auto-refresh.
 */

import { useQuery } from "@tanstack/react-query";
import { listRecoveryCases, type RecoveryCaseSummary } from "@/lib/api";

interface UseCasesOptions {
  status?: string;
  scenario?: string;
  failureReason?: string;
  limit?: number;
  offset?: number;
  refetchInterval?: number;
}

export function useRecoveryCases(options: UseCasesOptions = {}) {
  const {
    status,
    scenario,
    failureReason,
    limit = 50,
    offset = 0,
    refetchInterval = 10_000,
  } = options;

  return useQuery<RecoveryCaseSummary[]>({
    queryKey: ["recovery-cases", status, scenario, failureReason, limit, offset],
    queryFn: () =>
      listRecoveryCases({
        status,
        scenario,
        failure_reason: failureReason,
        limit,
        offset,
      }),
    refetchInterval,
  });
}
