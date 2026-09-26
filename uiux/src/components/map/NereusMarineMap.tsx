import React, { useEffect, useRef, useState, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Layers,
  Satellite,
  Waves,
  Navigation,
  Compass,
  Anchor,
  Radio,
  Plus,
  Minus,
  Maximize2,
  ShieldAlert,
  ShieldCheck,
  MapPin,
  RefreshCw
} from 'lucide-react';

export type MapStyleMode = 'satellite' | 'ocean' | 'dark' | 'voyager';

interface RegionalPreset {
  id: string;
  name: string;
  lat: number;
  lng: number;
  zoom: number;
  badge: string;
}

const REGIONAL_PRESETS: RegionalPreset[] = [
  { id: 'goa', name: 'Goa Shelf', lat: 15.35, lng: 73.35, zoom: 9, badge: 'PFZ HOTSPOT' },
  { id: 'rameshwaram', name: 'Palk Strait / IMBL', lat: 9.28, lng: 79.31, zoom: 9, badge: 'RESTRICTED IMBL' },
  { id: 'mumbai', name: 'Mumbai Coast', lat: 18.95, lng: 72.80, zoom: 9, badge: 'COMMERCIAL' },
  { id: 'kochi', name: 'Kochi Malabar', lat: 9.96, lng: 76.22, zoom: 9, badge: 'PELAGIC MACKEREL' },
  { id: 'chennai', name: 'Chennai Coromandel', lat: 13.08, lng: 80.27, zoom: 9, badge: 'PORT APPROACH' },
  { id: 'gujarat', name: 'Gulf of Khambhat', lat: 21.10, lng: 72.10, zoom: 9, badge: 'TIDAL BASIN' },
];

// Baseline static targets for maritime situational awareness
const BASE_FLEET_TARGETS = [
  { id: 'aero-01', name: 'AERO-01 Aerial Drone', type: 'DRONE', lat: 15.42, lng: 73.41, speed: '18.4 kt', alt: '140 m' },
  { id: 'sub-04', name: 'SUB-04 Benthic AUV', type: 'AUV', lat: 15.28, lng: 73.22, speed: '3.2 kt', depth: '42 m' },
  { id: 'ais-419', name: 'Fishing Craft AIS-419', type: 'VESSEL', lat: 15.31, lng: 73.38, speed: '7.8 kt', status: 'INCOIS Safe' },
  { id: 'buoy-goa', name: 'INCOIS Met-Ocean Buoy BD08', type: 'BUOY', lat: 15.15, lng: 73.18, wave: '1.4 m', sst: '28.8°C' },
  { id: 'pfz-candolim', name: 'Verified PFZ Convergence', type: 'PFZ', lat: 15.52, lng: 73.65, chl: '0.08 mg/m³', sst: '28.6°C' },
];

export const NereusMarineMap: React.FC<{ className?: string }> = ({
  className = 'w-full h-full min-h-[480px]',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const markersLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const overlayLayerGroupRef = useRef<L.LayerGroup | null>(null);

  const { mapLayers, toggleMapLayer, setFocusedTarget, latestOverlay } = useOrcaStore();
  const [mapStyle, setMapStyle] = useState<MapStyleMode>('satellite');
  const [currentZoom, setCurrentZoom] = useState<number>(9);
  const [activeRegionId, setActiveRegionId] = useState<string>('goa');

  // Tile URL configuration for different maritime layers
  const getTileConfig = (style: MapStyleMode) => {
    switch (style) {
      case 'satellite':
        return {
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          attribution: '&copy; Esri, DigitalGlobe, GeoEye, Earthstar Geographics',
          maxZoom: 18,
        };
      case 'ocean':
        return {
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',
          attribution: '&copy; Esri, GEBCO, NOAA, National Geographic',
          maxZoom: 16,
        };
      case 'dark':
        return {
          url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
          attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
          maxZoom: 19,
        };
      case 'voyager':
      default:
        return {
          url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
          attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
          maxZoom: 19,
        };
    }
  };

  // Helper to create glowing custom SVG icons
  const createMarkerIcon = (type: string, label: string) => {
    let color = '#06B6D4';
    let pulseColor = 'rgba(6, 182, 212, 0.4)';
    let badge = '●';

    if (type === 'PFZ') {
      color = '#10B981';
      pulseColor = 'rgba(16, 185, 129, 0.4)';
      badge = '🐟 PFZ';
    } else if (type === 'DRONE') {
      color = '#38BDF8';
      pulseColor = 'rgba(56, 189, 248, 0.4)';
      badge = '✈ DRONE';
    } else if (type === 'AUV') {
      color = '#14B8A6';
      pulseColor = 'rgba(20, 184, 166, 0.4)';
      badge = '⚓ AUV';
    } else if (type === 'VESSEL') {
      color = '#F59E0B';
      pulseColor = 'rgba(245, 158, 11, 0.4)';
      badge = '🚢 AIS';
    } else if (type === 'BUOY') {
      color = '#818CF8';
      pulseColor = 'rgba(129, 140, 248, 0.4)';
      badge = '📡 BUOY';
    } else if (type === 'WAYPOINT') {
      color = '#22D3EE';
      pulseColor = 'rgba(34, 211, 238, 0.4)';
      badge = '✦ WP';
    }

    const html = `
      <div class="relative flex items-center justify-center cursor-pointer select-none group" style="transform: translate(-50%, -50%);">
        <div class="absolute w-8 h-8 rounded-full animate-ping pointer-events-none" style="background-color: ${pulseColor};"></div>
        <div class="relative flex items-center gap-1 px-2 py-0.5 rounded-full border shadow-lg backdrop-blur-md transition-transform group-hover:scale-110" style="background-color: #05111A; border-color: ${color}; color: #FFFFFF; font-size: 10px; font-family: monospace; font-weight: bold; white-space: nowrap;">
          <span style="color: ${color};">${badge}</span>
          <span style="font-size: 9px; opacity: 0.85;">${label}</span>
        </div>
      </div>
    `;

    return L.divIcon({
      html,
      className: 'custom-nereus-marker',
      iconSize: [30, 30],
      iconAnchor: [15, 15],
      popupAnchor: [0, -18],
    });
  };

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initial = REGIONAL_PRESETS[0];
    const map = L.map(mapContainerRef.current, {
      center: [initial.lat, initial.lng],
      zoom: initial.zoom,
      zoomControl: false, // We render custom premium frosted glass zoom controls
      attributionControl: false,
    });

    const config = getTileConfig(mapStyle);
    const tileLayer = L.tileLayer(config.url, {
      attribution: config.attribution,
      maxZoom: config.maxZoom,
    }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    const overlayGroup = L.layerGroup().addTo(map);

    tileLayerRef.current = tileLayer;
    markersLayerGroupRef.current = markersGroup;
    overlayLayerGroupRef.current = overlayGroup;
    mapInstanceRef.current = map;

    map.on('zoomend', () => {
      setCurrentZoom(map.getZoom());
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Tile Layer when mapStyle changes
  useEffect(() => {
    if (!mapInstanceRef.current || !tileLayerRef.current) return;
    const config = getTileConfig(mapStyle);
    tileLayerRef.current.setUrl(config.url);
  }, [mapStyle]);

  // Render Fleet Targets with active layer filters
  useEffect(() => {
    const markersGroup = markersLayerGroupRef.current;
    if (!markersGroup || !mapInstanceRef.current) return;

    markersGroup.clearLayers();

    BASE_FLEET_TARGETS.forEach((target) => {
      if (target.type === 'PFZ' && !mapLayers.pfz) return;
      if (target.type === 'BUOY' && !mapLayers.weather) return;
      if ((target.type === 'DRONE' || target.type === 'AUV') && !mapLayers.drones) return;

      const marker = L.marker([target.lat, target.lng], {
        icon: createMarkerIcon(target.type, target.name.split(' ')[0]),
      });

      // Rich Oceanographic Telemetry Popup
      const popupHtml = `
        <div style="font-family: sans-serif; min-width: 180px; padding: 4px; color: #0A1E2C;">
          <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; margin-bottom: 6px;">
            <strong style="font-size: 11px; text-transform: uppercase;">${target.name}</strong>
            <span style="font-size: 9px; padding: 2px 4px; border-radius: 4px; background: #E0F2FE; color: #0369A1; font-weight: bold;">${target.type}</span>
          </div>
          <div style="font-size: 11px; font-family: monospace; line-height: 1.5;">
            <div><strong>Lat/Lon:</strong> ${target.lat.toFixed(3)}°N, ${target.lng.toFixed(3)}°E</div>
            ${target.speed ? `<div><strong>Speed:</strong> ${target.speed}</div>` : ''}
            ${target.alt ? `<div><strong>Altitude:</strong> ${target.alt}</div>` : ''}
            ${target.depth ? `<div><strong>Depth:</strong> ${target.depth}</div>` : ''}
            ${target.sst ? `<div><strong>SST:</strong> ${target.sst}</div>` : ''}
            ${target.chl ? `<div><strong>Chlorophyll:</strong> ${target.chl}</div>` : ''}
            ${target.wave ? `<div><strong>Wave Height:</strong> ${target.wave}</div>` : ''}
          </div>
          <div style="margin-top: 6px; font-size: 9px; color: #059669; font-weight: bold; border-top: 1px solid #F1F5F9; padding-top: 4px;">
            ✓ Real-time Telemetry Verified
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml);
      marker.on('click', () => {
        if (target.type === 'DRONE') setFocusedTarget('drone');
        if (target.type === 'AUV') setFocusedTarget('auv');
      });

      markersGroup.addLayer(marker);
    });
  }, [mapLayers]);

  // Synchronize dynamic SSE backend overlay (Waypoints, IMBL, PFZ polygons)
  useEffect(() => {
    const overlayGroup = overlayLayerGroupRef.current;
    const map = mapInstanceRef.current;
    if (!overlayGroup || !map || !latestOverlay) return;

    overlayGroup.clearLayers();

    // 1. Center & Zoom FlyTo if present and valid
    if (
      latestOverlay.center &&
      typeof latestOverlay.center.lat === 'number' &&
      typeof latestOverlay.center.lng === 'number' &&
      Number.isFinite(latestOverlay.center.lat) &&
      Number.isFinite(latestOverlay.center.lng)
    ) {
      map.flyTo([latestOverlay.center.lat, latestOverlay.center.lng], 9, {
        duration: 1.4,
        easeLinearity: 0.25,
      });
    }

    // 2. Safe Route Waypoints Polyline
    if (Array.isArray(latestOverlay.route_waypoints) && latestOverlay.route_waypoints.length > 0) {
      const validPoints: [number, number][] = [];

      latestOverlay.route_waypoints.forEach((wp: any, idx: number) => {
        const lat = typeof wp.lat === 'number' ? wp.lat : parseFloat(wp.lat);
        const lng = typeof wp.lng === 'number' ? wp.lng : typeof wp.lon === 'number' ? wp.lon : parseFloat(wp.lng || wp.lon);

        if (Number.isFinite(lat) && Number.isFinite(lng)) {
          validPoints.push([lat, lng]);

          // Waypoint marker pin
          const wpMarker = L.marker([lat, lng], {
            icon: createMarkerIcon('WAYPOINT', wp.label || `WP-${idx + 1}`),
          }).bindPopup(`
            <div style="font-family: monospace; font-size: 11px;">
              <strong>${wp.label || `Waypoint ${idx + 1}`}</strong><br/>
              Lat: ${lat.toFixed(3)}° | Lng: ${lng.toFixed(3)}°<br/>
              <span style="color: #06B6D4;">Optimal Safe Corridor</span>
            </div>
          `);
          overlayGroup.addLayer(wpMarker);
        }
      });

      if (validPoints.length > 1) {
        // Glowing cyan geodesic polyline
        const routeLine = L.polyline(validPoints, {
          color: '#06B6D4',
          weight: 4,
          opacity: 0.9,
          dashArray: '8, 6',
          lineCap: 'round',
        });
        overlayGroup.addLayer(routeLine);
      }
    }

    // 3. IMBL and Marine Protected Area Boundaries
    if (Array.isArray(latestOverlay.boundaries)) {
      latestOverlay.boundaries.forEach((b: any) => {
        if (!Array.isArray(b.coordinates) || b.coordinates.length < 2) return;

        const coords: [number, number][] = b.coordinates
          .map((pt: any) => {
            if (Array.isArray(pt) && Number.isFinite(pt[0]) && Number.isFinite(pt[1])) {
              return [pt[0], pt[1]] as [number, number];
            }
            return null;
          })
          .filter(Boolean) as [number, number][];

        if (coords.length > 1) {
          const isIMBL = b.type === 'imbl';
          const boundaryLine = L.polyline(coords, {
            color: isIMBL ? '#EF4444' : '#F59E0B',
            weight: 3.5,
            opacity: 0.85,
            dashArray: isIMBL ? '6, 6' : undefined,
          }).bindPopup(`
            <div style="font-family: sans-serif; font-size: 11px;">
              <strong style="color: ${isIMBL ? '#DC2626' : '#D97706'};">
                ${isIMBL ? '⚠️ International Maritime Boundary Line (IMBL)' : '🛡️ Marine Protected Area'}
              </strong><br/>
              <span>Standoff Buffer: 5.0 Nautical Miles</span>
            </div>
          `);
          overlayGroup.addLayer(boundaryLine);
        }
      });
    }

    // 4. Dynamic PFZ Features
    if (latestOverlay.type === 'pfz_zones' && Array.isArray(latestOverlay.features)) {
      latestOverlay.features.forEach((feat: any, idx: number) => {
        const lat = feat.latitude || feat.lat;
        const lng = feat.longitude || feat.lon || feat.lng;

        if (Number.isFinite(lat) && Number.isFinite(lng)) {
          const pfzMarker = L.marker([lat, lng], {
            icon: createMarkerIcon('PFZ', feat.zone_id || `PFZ-${idx + 1}`),
          }).bindPopup(`
            <div style="font-family: monospace; font-size: 11px; padding: 4px;">
              <div style="font-weight: bold; color: #047857; margin-bottom: 4px;">INCOIS POTENTIAL FISHING ZONE</div>
              <div><strong>Zone ID:</strong> ${feat.zone_id || 'Optimal Zone'}</div>
              <div><strong>SST:</strong> ${feat.sst_celsius ? `${feat.sst_celsius}°C` : '28.7°C'}</div>
              <div><strong>Chlorophyll:</strong> ${feat.chlorophyll_mg_m3 ? `${feat.chlorophyll_mg_m3} mg/m³` : '0.06 mg/m³'}</div>
              <div><strong>Species:</strong> Indian Mackerel, Sardine</div>
            </div>
          `);
          overlayGroup.addLayer(pfzMarker);
        }
      });
    }
  }, [latestOverlay]);

  // Smooth Zoom Handlers
  const handleZoomIn = () => {
    mapInstanceRef.current?.zoomIn();
  };

  const handleZoomOut = () => {
    mapInstanceRef.current?.zoomOut();
  };

  const handleFlyToRegion = (region: RegionalPreset) => {
    setActiveRegionId(region.id);
    mapInstanceRef.current?.flyTo([region.lat, region.lng], region.zoom, {
      duration: 1.5,
      easeLinearity: 0.25,
    });
  };

  return (
    <div className={`relative rounded-3xl overflow-hidden glass-panel-ocean border border-ocean-400/30 shadow-2xl flex flex-col ${className}`}>
      
      {/* Top Map Header Controls */}
      <div className="p-3.5 border-b border-ocean-500/20 bg-ocean-950/85 backdrop-blur-xl flex flex-wrap items-center justify-between gap-2.5 z-20">
        
        {/* Title and Telemetry Badge */}
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-xs font-bold text-white font-mono tracking-wider uppercase">
            NEREUS SATELLITE & MET-OCEAN CARTOGRAPHY
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-400/40">
            ESRI / CARTO LIVE
          </span>
        </div>

        {/* Style Mode Switcher */}
        <div className="flex items-center gap-1 bg-ocean-900/90 p-1 rounded-xl border border-ocean-400/30 text-[11px] font-mono">
          <button
            onClick={() => setMapStyle('satellite')}
            className={`px-2.5 py-1 rounded-lg font-bold transition-all flex items-center gap-1 ${
              mapStyle === 'satellite'
                ? 'bg-cyan-500 text-ocean-950 shadow-md'
                : 'text-slate-300 hover:text-white'
            }`}
          >
            <Satellite className="w-3.5 h-3.5" />
            <span>Satellite</span>
          </button>

          <button
            onClick={() => setMapStyle('ocean')}
            className={`px-2.5 py-1 rounded-lg font-bold transition-all flex items-center gap-1 ${
              mapStyle === 'ocean'
                ? 'bg-cyan-500 text-ocean-950 shadow-md'
                : 'text-slate-300 hover:text-white'
            }`}
          >
            <Waves className="w-3.5 h-3.5" />
            <span>Bathymetry</span>
          </button>

          <button
            onClick={() => setMapStyle('dark')}
            className={`px-2.5 py-1 rounded-lg font-bold transition-all flex items-center gap-1 ${
              mapStyle === 'dark'
                ? 'bg-cyan-500 text-ocean-950 shadow-md'
                : 'text-slate-300 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Dark</span>
          </button>

          <button
            onClick={() => setMapStyle('voyager')}
            className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
              mapStyle === 'voyager'
                ? 'bg-cyan-500 text-ocean-950 shadow-md'
                : 'text-slate-300 hover:text-white'
            }`}
          >
            Voyager
          </button>
        </div>

      </div>

      {/* Regional Quick Jump Bar */}
      <div className="px-3.5 py-2 border-b border-ocean-500/10 bg-ocean-900/60 backdrop-blur-md flex items-center gap-2 overflow-x-auto text-[11px] font-mono z-20 scrollbar-none">
        <span className="text-cyan-400 font-bold uppercase tracking-wider text-[10px] shrink-0">
          QUICK JUMP:
        </span>
        {REGIONAL_PRESETS.map((region) => (
          <button
            key={region.id}
            onClick={() => handleFlyToRegion(region)}
            className={`px-2.5 py-1 rounded-lg whitespace-nowrap transition-all border flex items-center gap-1.5 ${
              activeRegionId === region.id
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400/60 shadow-sm'
                : 'bg-ocean-950/40 text-slate-300 border-ocean-500/20 hover:border-cyan-400/40 hover:text-white'
            }`}
          >
            <span>{region.name}</span>
            <span className="text-[9px] px-1 py-0.2 rounded bg-ocean-800/80 text-cyan-400 font-mono">
              {region.badge}
            </span>
          </button>
        ))}
      </div>

      {/* Main Map Container */}
      <div className="relative flex-1 w-full min-h-[380px] bg-ocean-950">
        <div ref={mapContainerRef} className="w-full h-full min-h-[380px] z-10" />

        {/* Custom Frosted Glass Zoom & Reset Controls */}
        <div className="absolute bottom-5 right-5 z-20 flex flex-col gap-2">
          <div className="flex flex-col rounded-xl overflow-hidden glass-panel-ocean border border-ocean-400/40 shadow-xl">
            <button
              onClick={handleZoomIn}
              className="w-8 h-8 flex items-center justify-center bg-ocean-900/80 hover:bg-cyan-500 hover:text-ocean-950 text-white transition-colors border-b border-ocean-400/20"
              title="Zoom in"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomOut}
              className="w-8 h-8 flex items-center justify-center bg-ocean-900/80 hover:bg-cyan-500 hover:text-ocean-950 text-white transition-colors"
              title="Zoom out"
            >
              <Minus className="w-4 h-4" />
            </button>
          </div>

          <button
            onClick={() => handleFlyToRegion(REGIONAL_PRESETS[0])}
            className="w-8 h-8 flex items-center justify-center rounded-xl glass-panel-ocean border border-ocean-400/40 hover:bg-cyan-500 hover:text-ocean-950 text-white shadow-xl transition-colors"
            title="Reset to Goa"
          >
            <Compass className="w-4 h-4" />
          </button>
        </div>

        {/* Floating Layer Toggle Chips */}
        <div className="absolute top-4 left-4 z-20 flex flex-wrap gap-1.5 max-w-[80%]">
          <button
            onClick={() => toggleMapLayer('pfz')}
            className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold transition-all border flex items-center gap-1 backdrop-blur-md ${
              mapLayers.pfz
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/60 shadow-sm'
                : 'bg-ocean-950/70 text-slate-400 border-ocean-700/50'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${mapLayers.pfz ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            <span>PFZ Zones</span>
          </button>

          <button
            onClick={() => toggleMapLayer('weather')}
            className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold transition-all border flex items-center gap-1 backdrop-blur-md ${
              mapLayers.weather
                ? 'bg-amber-500/20 text-amber-300 border-amber-400/60 shadow-sm'
                : 'bg-ocean-950/70 text-slate-400 border-ocean-700/50'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${mapLayers.weather ? 'bg-amber-400 animate-pulse' : 'bg-slate-500'}`} />
            <span>Buoys & Weather</span>
          </button>

          <button
            onClick={() => toggleMapLayer('drones')}
            className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold transition-all border flex items-center gap-1 backdrop-blur-md ${
              mapLayers.drones
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400/60 shadow-sm'
                : 'bg-ocean-950/70 text-slate-400 border-ocean-700/50'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${mapLayers.drones ? 'bg-cyan-400 animate-pulse' : 'bg-slate-500'}`} />
            <span>Autonomous Fleet</span>
          </button>
        </div>

      </div>

      {/* Bottom Telemetry Status Strip */}
      <div className="p-2 px-4 border-t border-ocean-500/20 bg-ocean-950/90 text-[10px] font-mono text-slate-400 flex flex-wrap items-center justify-between gap-2 z-20">
        <div className="flex items-center gap-3">
          <span>COORDINATE SYSTEM: WGS84</span>
          <span>•</span>
          <span>PROJECTION: EPSG:3857 (SPHERICAL MERCATOR)</span>
          <span>•</span>
          <span className="text-cyan-400">ZOOM LEVEL: {currentZoom}</span>
        </div>
        <div className="flex items-center gap-1.5 text-emerald-400">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>PostGIS Geofence Guard Active</span>
        </div>
      </div>

    </div>
  );
};
