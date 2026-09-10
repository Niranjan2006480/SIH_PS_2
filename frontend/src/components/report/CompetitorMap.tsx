import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { AnalysisResponse, CompetitorItem } from "@/lib/api-client";
import { MapPin, Navigation, Layers, ShieldAlert, Award } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  report: AnalysisResponse;
}

export function CompetitorMap({ report }: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Record<string, L.Marker>>({});
  const [selectedCompetitor, setSelectedCompetitor] = useState<string | null>(null);

  const centerLat = report.latitude ?? 19.7515;
  const centerLon = report.longitude ?? 75.7139;
  const competitors = report.competitors.items ?? [];

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Destroy existing instance if present
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    // Default zoom based on radius
    const initialZoom = report.radius_km > 5 ? 12 : 13;

    // Create Map instance
    const map = L.map(mapContainerRef.current, {
      center: [centerLat, centerLon],
      zoom: initialZoom,
      scrollWheelZoom: false,
    });
    mapInstanceRef.current = map;

    // Crisp high-performance basemap
    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);

    // 1. Add Catchment Radius Buffer Rings
    L.circle([centerLat, centerLon], {
      radius: 5000,
      color: "#275634",
      fillColor: "#275634",
      fillOpacity: 0.05,
      weight: 1.5,
      dashArray: "4, 6",
    })
      .bindTooltip("5 km Primary Catchment", { permanent: false, direction: "top" })
      .addTo(map);

    if (report.radius_km >= 10) {
      L.circle([centerLat, centerLon], {
        radius: 10000,
        color: "#b47828",
        fillColor: "#b47828",
        fillOpacity: 0.03,
        weight: 1.5,
        dashArray: "4, 8",
      })
        .bindTooltip("10 km Extended Catchment", { permanent: false, direction: "top" })
        .addTo(map);
    }

    // 2. Add Center Marker (Proposed Location)
    const centerIcon = L.divIcon({
      className: "custom-center-pin",
      html: `
        <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 34px; height: 34px;">
          <div style="position: absolute; width: 34px; height: 34px; border-radius: 9999px; background-color: rgba(39, 86, 52, 0.25); animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
          <div style="width: 28px; height: 28px; border-radius: 9999px; background-color: #275634; border: 2px solid #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.25); display: flex; align-items: center; justify-content: center; color: #ffffff; font-weight: bold; font-size: 13px;">
            ★
          </div>
        </div>
      `,
      iconSize: [34, 34],
      iconAnchor: [17, 17],
    });

    const centerMarker = L.marker([centerLat, centerLon], { icon: centerIcon }).addTo(map);
    centerMarker.bindPopup(`
      <div style="font-family: inherit; padding: 2px;">
        <div style="font-size: 13px; font-weight: bold; color: #1a1a1a;">${report.village_name}</div>
        <div style="font-size: 11px; color: #275634; font-weight: 600; margin-top: 2px;">Proposed Enterprise Center</div>
        <div style="font-size: 10px; color: #666; margin-top: 4px;">Taluka & District: ${report.district_name}</div>
        <div style="font-size: 10px; color: #666;">Analysis radius: ${report.radius_km} km</div>
      </div>
    `);

    // 3. Add Competitor Markers
    const markers: Record<string, L.Marker> = {};

    competitors.forEach((item, index) => {
      const lat = item.latitude ?? (centerLat + (index + 1) * 0.012);
      const lon = item.longitude ?? (centerLon + (index + 1) * 0.012);

      const isHigh = item.strength === "High";
      const isEmerging = item.strength === "Emerging";
      const markerColor = isHigh ? "#a03228" : isEmerging ? "#475569" : "#b47828";
      const markerLabel = (index + 1).toString();

      const compIcon = L.divIcon({
        className: `custom-comp-pin-${index}`,
        html: `
          <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; cursor: pointer;">
            <div style="width: 24px; height: 24px; border-radius: 9999px; background-color: ${markerColor}; border: 2px solid #ffffff; box-shadow: 0 3px 5px -1px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: #ffffff; font-weight: bold; font-size: 10px; font-family: monospace;">
              ${markerLabel}
            </div>
          </div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const compMarker = L.marker([lat, lon], { icon: compIcon }).addTo(map);
      compMarker.bindPopup(`
        <div style="font-family: inherit; min-width: 170px; padding: 3px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="font-size: 12px; font-weight: bold; color: #1a1a1a;">${item.name}</span>
            <span style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; background-color: ${markerColor}20; color: ${markerColor};">${item.strength || "Moderate"}</span>
          </div>
          <div style="font-size: 11px; color: #444; margin-top: 3px;">${item.category}</div>
          <div style="font-size: 11px; font-weight: 600; color: #275634; margin-top: 3px;">📍 ${item.distance_km} km away</div>
          ${item.offering ? `<div style="font-size: 10px; color: #666; margin-top: 5px; border-top: 1px solid #eee; padding-top: 4px;">${item.offering}</div>` : ""}
        </div>
      `);

      compMarker.on("click", () => {
        setSelectedCompetitor(item.name);
      });

      markers[item.name] = compMarker;
    });

    markersRef.current = markers;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [centerLat, centerLon, report.radius_km, report.village_name, report.district_name, competitors]);

  const handleSelectCompetitor = (item: CompetitorItem) => {
    setSelectedCompetitor(item.name);
    const marker = markersRef.current[item.name];
    if (marker && mapInstanceRef.current) {
      mapInstanceRef.current.setView(marker.getLatLng(), 14, { animate: true });
      marker.openPopup();
    }
  };

  const handleResetView = () => {
    setSelectedCompetitor(null);
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView([centerLat, centerLon], report.radius_km > 5 ? 12 : 13, {
        animate: true,
      });
    }
  };

  return (
    <div className="space-y-4">
      {/* Map Card */}
      <div className="relative overflow-hidden rounded-md border border-line bg-paper shadow-sm">
        {/* Map Header Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-note/50 px-4 py-2.5 text-xs">
          <div className="flex items-center gap-2 font-mono font-medium text-ink/80">
            <Navigation size={14} className="text-moss" />
            <span>
              {report.village_name} Centroid ({centerLat.toFixed(3)}°N, {centerLon.toFixed(3)}°E)
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-ink/60">
              <span className="inline-block h-2.5 w-2.5 rounded-full border border-moss bg-moss/20" />
              <span>5 km Core</span>
            </div>
            {report.radius_km >= 10 && (
              <div className="flex items-center gap-1.5 text-ink/60">
                <span className="inline-block h-2.5 w-2.5 rounded-full border border-ochre bg-ochre/20" />
                <span>10 km Buffer</span>
              </div>
            )}
            <button
              onClick={handleResetView}
              className="flex items-center gap-1 rounded border border-line bg-cream px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-ink/70 transition-colors hover:bg-note"
            >
              <Layers size={11} /> Reset View
            </button>
          </div>
        </div>

        {/* Leaflet Container */}
        <div
          ref={mapContainerRef}
          className="h-[380px] w-full bg-cream/50 z-0"
          style={{ minHeight: "380px" }}
        />

        {/* Map Overlay Badge */}
        <div className="pointer-events-none absolute bottom-3 left-3 z-[400] flex items-center gap-2 rounded bg-paper/90 px-2.5 py-1.5 text-[11px] font-medium text-ink shadow-sm backdrop-blur-sm border border-line">
          <span className="flex h-2 w-2 rounded-full bg-moss" />
          <span>{competitors.length} mapped competitors within {report.radius_km} km</span>
        </div>
      </div>

      {/* Synchronized Competitor Cards Grid */}
      {competitors.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="font-mono text-[11px] uppercase tracking-wider text-ink/60">
              Nearby Competitors & Field Operators
            </h4>
            <span className="font-mono text-[10px] text-ink/40">
              Click to pinpoint on map
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {competitors.map((item, idx) => {
              const isSelected = selectedCompetitor === item.name;
              const isHigh = item.strength === "High";
              const isEmerging = item.strength === "Emerging";

              return (
                <div
                  key={item.name + idx}
                  onClick={() => handleSelectCompetitor(item)}
                  className={cn(
                    "cursor-pointer rounded border p-3 transition-all duration-200",
                    isSelected
                      ? "border-moss bg-moss/5 ring-1 ring-moss shadow-sm"
                      : "border-line bg-note/40 hover:border-ink/30 hover:bg-note",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-bold text-white",
                          isHigh ? "bg-clay" : isEmerging ? "bg-slate-600" : "bg-ochre",
                        )}
                      >
                        {idx + 1}
                      </span>
                      <span className="font-display text-sm font-semibold text-ink line-clamp-1">
                        {item.name}
                      </span>
                    </div>

                    <span
                      className={cn(
                        "shrink-0 rounded px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider",
                        isHigh
                          ? "bg-clay/10 text-clay"
                          : isEmerging
                            ? "bg-slate-200 text-slate-700"
                            : "bg-ochre/15 text-ochre",
                      )}
                    >
                      {item.strength || "Moderate"}
                    </span>
                  </div>

                  <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-moss">
                    <MapPin size={12} className="shrink-0" />
                    <span>{item.distance_km} km away</span>
                    <span className="text-ink/30">•</span>
                    <span className="text-ink/60 truncate">{item.category}</span>
                  </div>

                  {item.offering && (
                    <p className="mt-2 text-xs leading-relaxed text-ink/70 line-clamp-2">
                      {item.offering}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
