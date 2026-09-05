/**
 * React Query mutation for generating feasibility analysis.
 * Uses the backend POST /api/v1/analysis/generate endpoint.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type AnalysisRequest, type AnalysisResponse } from "@/lib/api-client";

export function useGenerateAnalysis() {
  return useMutation<AnalysisResponse, Error, AnalysisRequest>({
    mutationFn: api.analysis.generate,
    retry: false,
  });
}

export function useReport(reportId: string | null) {
  return useQuery({
    queryKey: ["reports", reportId],
    queryFn: () => api.analysis.get(reportId!),
    enabled: !!reportId,
    staleTime: 1000 * 60 * 60, // reports don't change
    retry: false,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: api.financial.categories,
    staleTime: 1000 * 60 * 60 * 24,
  });
}

export function useSchemes() {
  return useQuery({
    queryKey: ["schemes"],
    queryFn: api.financial.schemes,
    staleTime: 1000 * 60 * 60 * 24,
  });
}
