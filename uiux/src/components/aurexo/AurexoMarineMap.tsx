import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Navigation,
  Anchor,
  Layers,
  Eye,
  Crosshair,
  Compass,
  Wind,
  Thermometer,
  ShieldAlert,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RotateCcw
} from 'lucide-react';

export const AurexoMarineMap: React.FC = () => {
  const { mapLayers, toggleMapLayer, marineData, agentStatus, setFocusedTarget } = useOrcaStore();
  const [zoomLevel, setZoomLevel] = useState(1);
  const [activePin, setActivePin] = useState<string | null>('target_drone');

  return (
    <div className="relative w-full h-[460px] md:h-[500px] rounded-2xl overflow-hidden glass-panel border border-white/80 shadow-lg flex flex-col">
      
      {/* Top Map Header Controls */}
      <div className="p-3.5 border-b border-sky-100/80 bg-white/60 backdrop-blur-md flex items-center justify-between z-20">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-500 animate-ping" />
          <span className="text-xs font-bold text-slate-800 font-display tracking-wide uppercase">
            Spatial Marine Telemetry Grid
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-100 text-sky-800 font-semibold">
            INCOIS ARABIAN SEA BASIN
          </span>
        </div>

        {/* Layer Toggles Pill */}
        <div className="flex items-center gap-1.5 overflow-x-auto text-[11px] font-mono">
          <button
            onClick={() => toggleMapLayer('pfz')}
            className={`px-2 py-0.5 rounded-md font-semibold transition-all ${
              mapLayers.pfz
                ? 'bg-cyan-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-500 hover:text-slate-800'
            }`}
          >
            PFZ
          </button>
          <button
            onClick={() => toggleMapLayer('sst')}
            className={`px-2 py-0.5 rounded-md font-semibold transition-all ${
              mapLayers.sst
                ? 'bg-amber-500 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-500 hover:text-slate-800'
            }`}
          >
            SST
          </button>
          <button
            onClick={() => toggleMapLayer('weather')}
            className={`px-2 py-0.5 rounded-md font-semibold transition-all ${
              mapLayers.weather
                ? 'bg-teal-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-500 hover:text-slate-800'
            }`}
          >
            WIND
          </button>
          <button
            onClick={() => toggleMapLayer('drones')}
            className={`px-2 py-0.5 rounded-md font-semibold transition-all ${
              mapLayers.drones
                ? 'bg-indigo-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-500 hover:text-slate-800'
            }`}
          >
            DRONES
          </button>
        </div>
      </div>

      {/* Map Surface Render with SVG Coastal Shelf and Live Target Overlays */}
      <div className="relative flex-1 bg-gradient-to-b from-sky-100 via-sky-50 to-cyan-100/60 overflow-hidden cursor-grab active:cursor-grabbing">
        
        {/* Radar Circular Grid & Bearing Marks */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-40">
          <div className="w-[380px] h-[380px] rounded-full border border-cyan-400/40" />
          <div className="absolute w-[240px] h-[240px] rounded-full border border-dashed border-cyan-500/50" />
          <div className="absolute w-[100px] h-[100px] rounded-full border border-cyan-600/30" />
          <div className="absolute h-full w-[1px] bg-cyan-400/20" />
          <div className="absolute w-full h-[1px] bg-cyan-400/20" />
        </div>

        {/* Coastal Shelf SVG Representation (Western Indian Coastline) */}
        <svg
          viewBox="0 0 600 400"
          className="absolute inset-0 w-full h-full object-cover pointer-events-none transition-transform duration-500"
          style={{ transform: `scale(${zoomLevel})` }}
        >
          {/* Depth Contours (Bathymetry) */}
          {mapLayers.bathymetry && (
            <g opacity="0.35" stroke="#0ea5e9" strokeWidth="1" fill="none" strokeDasharray="3 3">
              <path d="M 520 0 Q 420 180 460 400" />
              <path d="M 440 0 Q 340 180 380 400" />
              <path d="M 360 0 Q 260 180 300 400" />
            </g>
          )}

          {/* Continental Coastline (Land Mass) */}
          <path
            d="M 600 0 L 510 0 Q 430 120 480 230 Q 520 310 490 400 L 600 400 Z"
            fill="#e2e8f0"
            stroke="#cbd5e1"
            strokeWidth="2"
          />

          {/* Lakshadweep Atoll Islands */}
          <ellipse cx="210" cy="280" rx="12" ry="6" fill="#cbd5e1" stroke="#94a3b8" />
          <ellipse cx="230" cy="320" rx="9" ry="5" fill="#cbd5e1" stroke="#94a3b8" />
          <ellipse cx="195" cy="240" rx="8" ry="4" fill="#cbd5e1" stroke="#94a3b8" />

          {/* PFZ Potential Fishing Zone Hotspot Polygons */}
          {mapLayers.pfz && (
            <g>
              {/* Hotspot 1: Goa Shelf */}
              <polygon
                points="280,140 370,120 390,190 310,210"
                fill="rgba(6, 182, 212, 0.22)"
                stroke="#0891b2"
                strokeWidth="2"
                strokeDasharray="4 2"
                className="animate-pulse"
              />
              <text x="325" y="165" fill="#0369a1" fontSize="11" fontWeight="bold" fontFamily="monospace">
                PFZ ZONE A-1
              </text>
              <text x="315" y="180" fill="#0284c7" fontSize="9" fontFamily="monospace">
                Chlorophyll: 0.84 mg/m³
              </text>

              {/* Hotspot 2: Kochi Break */}
              <polygon
                points="250,290 320,270 340,330 270,350"
                fill="rgba(16, 185, 129, 0.2)"
                stroke="#059669"
                strokeWidth="1.5"
              />
              <text x="275" y="315" fill="#047857" fontSize="10" fontWeight="bold" fontFamily="monospace">
                PFZ ZONE B-3
              </text>
            </g>
          )}

          {/* SST Thermal Front Gradient Line */}
          {mapLayers.sst && (
            <g opacity="0.6">
              <path d="M 220 50 Q 290 180 340 380" stroke="#f59e0b" strokeWidth="2.5" fill="none" strokeDasharray="6 3" />
              <text x="250" y="70" fill="#b45309" fontSize="9" fontFamily="monospace">SST Front 28.5°C</text>
            </g>
          )}

          {/* Swell Vector Arrows */}
          {mapLayers.weather && (
            <g stroke="#0284c7" strokeWidth="1.2" opacity="0.4">
              <line x1="120" y1="120" x2="160" y2="100" markerEnd="url(#arrow)" />
              <line x1="180" y1="220" x2="220" y2="200" />
              <line x1="140" y1="310" x2="180" y2="290" />
            </g>
          )}
        </svg>

        {/* Spatial Target Markers directly on map (Matching Reference Video) */}

        {/* 1. Aurexo Drone Pin with Flight Track */}
        <div
          onClick={() => {
            setActivePin('target_drone');
            setFocusedTarget('drone');
          }}
          className="absolute top-[32%] left-[48%] -translate-x-1/2 -translate-y-1/2 cursor-pointer z-30 group"
        >
          {/* Target Radar Halo */}
          <div className="absolute -inset-3 rounded-full border border-cyan-500/50 animate-ping pointer-events-none" />
          
          <div className="relative flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/95 border border-cyan-400 shadow-md group-hover:scale-110 transition-transform">
            <Navigation className="w-3.5 h-3.5 text-cyan-600 rotate-45" />
            <span className="text-[10px] font-mono font-bold text-slate-900">
              AUREXO-AERO-01
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>

          {/* Detailed Callout Card (From Video: Speed, Prevision, Altitude) */}
          {activePin === 'target_drone' && (
            <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-48 p-2.5 rounded-xl bg-white/95 backdrop-blur-md border border-cyan-300 shadow-xl pointer-events-auto">
              <div className="flex items-center justify-between text-[11px] font-bold text-slate-800 border-b border-slate-100 pb-1 mb-1.5">
                <span>SURVEILLANCE DRONE</span>
                <span className="text-cyan-700 font-mono">18.4 kt</span>
              </div>
              <div className="grid grid-cols-2 gap-1 text-[10px] font-mono text-slate-600">
                <div>Altitude: <span className="font-bold text-slate-800">120m</span></div>
                <div>Prevision: <span className="font-bold text-emerald-700">1.58</span></div>
                <div>Course: <span className="font-bold text-slate-800">042° NE</span></div>
                <div>Signal: <span className="font-bold text-cyan-700">99.4%</span></div>
              </div>
            </div>
          )}
        </div>

        {/* 2. Boat / Non-op Marker (From Video 00:02) */}
        <div
          onClick={() => setActivePin('target_boat')}
          className="absolute top-[48%] left-[26%] -translate-x-1/2 -translate-y-1/2 cursor-pointer z-20 group"
        >
          <div className="relative flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/90 border border-amber-300 shadow-sm group-hover:scale-105 transition-transform">
            <div className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-[10px] font-mono font-semibold text-slate-800">
              Boat / Non-op
            </span>
          </div>

          {activePin === 'target_boat' && (
            <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-44 p-2.5 rounded-xl bg-white/95 backdrop-blur-md border border-amber-200 shadow-xl">
              <p className="text-[11px] font-bold text-slate-800 font-mono">AIS: IND-4190012</p>
              <p className="text-[10px] text-slate-500 font-mono">Status: Stationary / Trawling</p>
              <p className="text-[10px] text-slate-500 font-mono">SST at Hull: 28.3°C</p>
            </div>
          )}
        </div>

        {/* 3. Submersible AUV Pin */}
        <div
          onClick={() => {
            setActivePin('target_auv');
            setFocusedTarget('auv');
          }}
          className="absolute top-[68%] left-[38%] -translate-x-1/2 -translate-y-1/2 cursor-pointer z-20 group"
        >
          <div className="relative flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/90 border border-teal-300 shadow-sm group-hover:scale-105 transition-transform">
            <Anchor className="w-3 h-3 text-teal-600" />
            <span className="text-[10px] font-mono font-semibold text-slate-800">
              AUREXO-SUB-04
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-teal-500 animate-ping" />
          </div>
        </div>

        {/* Zoom & Reset Floating Controls */}
        <div className="absolute bottom-3 right-3 flex flex-col gap-1 z-20">
          <button
            onClick={() => setZoomLevel((z) => Math.min(1.8, z + 0.2))}
            className="w-7 h-7 rounded-lg bg-white/90 border border-slate-200 shadow-sm flex items-center justify-center text-slate-700 hover:text-cyan-700 transition-colors"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoomLevel((z) => Math.max(0.8, z - 0.2))}
            className="w-7 h-7 rounded-lg bg-white/90 border border-slate-200 shadow-sm flex items-center justify-center text-slate-700 hover:text-cyan-700 transition-colors"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoomLevel(1)}
            className="w-7 h-7 rounded-lg bg-white/90 border border-slate-200 shadow-sm flex items-center justify-center text-slate-700 hover:text-cyan-700 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Compass Rose Indicator */}
        <div className="absolute top-3 right-3 flex items-center gap-1 px-2 py-1 rounded-lg bg-white/80 border border-slate-200 text-[10px] font-mono font-bold text-slate-700 z-10">
          <Compass className="w-3.5 h-3.5 text-cyan-600 animate-spin duration-[12000ms]" />
          <span>N 000°</span>
        </div>

      </div>

      {/* Bottom Status Ticker */}
      <div className="px-3.5 py-2 border-t border-sky-100 bg-white/70 backdrop-blur-md flex items-center justify-between text-[11px] font-mono text-slate-600 z-20">
        <div className="flex items-center gap-3">
          <span>Lat: 15°25'N • Long: 73°48'E</span>
          <span className="hidden sm:inline text-slate-300">|</span>
          <span className="hidden sm:inline">Depth: 48m Shelf</span>
        </div>
        <div className="flex items-center gap-1 text-emerald-700 font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span>Telemetry Link 100% Locked</span>
        </div>
      </div>

    </div>
  );
};
