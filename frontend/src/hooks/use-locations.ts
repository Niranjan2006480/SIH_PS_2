/**
 * React Query hook for location search with debounce.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export function useLocationSearch(query: string, stateCode?: string) {
  return useQuery({
    queryKey: ["locations", "search", query, stateCode],
    queryFn: () => api.locations.search(query, stateCode),
    enabled: query.trim().length >= 2,
    staleTime: 1000 * 60 * 5, // 5 minutes
    placeholderData: (prev) => prev,
  });
}

export function useStates() {
  return useQuery({
    queryKey: ["locations", "states"],
    queryFn: api.locations.states,
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}

export function useDistricts(stateCode: string | null) {
  return useQuery({
    queryKey: ["locations", "districts", stateCode],
    queryFn: () => api.locations.districts(stateCode!),
    enabled: !!stateCode,
    staleTime: 1000 * 60 * 60,
  });
}

export function useVillages(districtCode: string | null) {
  return useQuery({
    queryKey: ["locations", "villages", districtCode],
    queryFn: () => api.locations.villages(districtCode!),
    enabled: !!districtCode,
    staleTime: 1000 * 60 * 60,
  });
}
