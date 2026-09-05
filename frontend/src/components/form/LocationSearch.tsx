/**
 * Location search input with live suggestions from the backend.
 * Uses the /api/v1/locations/search endpoint.
 */

import { useState, useEffect, useRef } from "react";
import { useLocationSearch } from "@/hooks/use-locations";
import type { LocationResult } from "@/lib/api-client";
import { MapPin, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  value: LocationResult | null;
  onChange: (location: LocationResult) => void;
  placeholder?: string;
  stateCode?: string;
}

export function LocationSearch({ value, onChange, placeholder = "Search village or town...", stateCode }: Props) {
  const [query, setQuery] = useState(value?.village_name ?? "");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data, isFetching } = useLocationSearch(query, stateCode);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(loc: LocationResult) {
    setQuery(loc.village_name);
    setOpen(false);
    onChange(loc);
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-center border border-line bg-cream rounded focus-within:border-moss transition-colors">
        <MapPin size={15} className="ml-3 shrink-0 text-ink/40" />
        <input
          type="text"
          value={query}
          placeholder={placeholder}
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => query.length >= 2 && setOpen(true)}
          className="w-full bg-transparent px-3 py-3 text-sm outline-none placeholder:text-ink/35"
        />
        {isFetching && <Loader2 size={13} className="mr-3 animate-spin text-ink/40" />}
      </div>

      {open && data && data.results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full border border-line bg-cream shadow-lg max-h-72 overflow-y-auto">
          {data.results.map((loc) => (
            <button
              key={loc.village_lgd_code}
              type="button"
              onClick={() => handleSelect(loc)}
              className={cn(
                "w-full px-4 py-3 text-left hover:bg-note transition-colors border-b border-line/50 last:border-0",
                value?.village_lgd_code === loc.village_lgd_code && "bg-moss/5",
              )}
            >
              <div className="text-sm font-medium">{loc.village_name}</div>
              <div className="mt-0.5 font-mono text-[10px] text-ink/50">
                {loc.subdistrict_name} · {loc.district_name} · {loc.state_name}
              </div>
            </button>
          ))}
        </div>
      )}

      {open && query.length >= 2 && !isFetching && data?.results.length === 0 && (
        <div className="absolute z-50 mt-1 w-full border border-line bg-cream p-4 shadow-lg">
          <p className="text-sm text-ink/50">No matching villages found for "{query}"</p>
        </div>
      )}
    </div>
  );
}
