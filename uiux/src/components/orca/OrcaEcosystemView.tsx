import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Waves,
  Thermometer,
  Wind,
  Compass,
  Layers,
  MapPin,
  Shield,
  Activity,
  Droplet,
} from 'lucide-react';

export const OrcaEcosystemView: React.FC = () => {
  const { marineData, mapLayers, toggleMapLayer } = useOrcaStore();
  const [selectedDepth, setSelectedDepth] = useState<number>(50);

  return (
    <div className="w-full h-full flex flex-col p-6 space-y-4 overflow-y-auto">
      {/* Top Banner */}
      <div className="flex items-center justify-between glass-panel p-4 rounded-2xl border border-cyan-500/20">
        <div>
          <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block">
            ECOSYSTEM DIAGNOSTIC & BATHYMETRIC ANALYSIS
          </span>
          <h2 className="text-xl font-display font-bold text-white mt-0.5">
            Central Arabian Sea & Konkan Continental Shelf
          </h2>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="bg-slate-900/80 px-3 py-1.5 rounded-xl border border-slate-700">
            <span className="text-slate-400 block text-[10px]">ACOUSTIC TELEMETRY</span>
            <span className="text-emerald-400 font-bold">
              {marineData.surveillance.underwaterAuv.acousticTelemetryDb} dB
            </span>
          </div>
          <div className="bg-slate-900/80 px-3 py-1.5 rounded-xl border border-slate-700">
            <span className="text-slate-400 block text-[10px]">CHLOROPHYLL BIO</span>
            <span className="text-cyan-300 font-bold">
              {marineData.chlorophyll.value} mg/m³ ({marineData.chlorophyll.status})
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1">
        {/* Left: Bathymetric Profile */}
        <div className="lg:col-span-2 glass-panel p-5 rounded-2xl border border-cyan-500/20 flex flex-col justify-between">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                Cross-Sectional Continental Shelf & Thermocline
              </h3>
            </div>
            <span className="text-[10px] font-mono text-slate-400">DEPTH RESOLUTION: 1.0M</span>
          </div>

          {/* Bathymetry Canvas / Visualization */}
          <div className="relative my-4 h-64 bg-slate-950/70 rounded-xl border border-slate-800 p-4 flex flex-col justify-between overflow-hidden">
            {/* Water layer lines */}
            <div className="absolute inset-0 opacity-20 pointer-events-none">
              <div className="w-full h-1/4 border-b border-cyan-400 border-dashed" />
              <div className="w-full h-1/2 border-b border-cyan-400 border-dashed" />
              <div className="w-full h-3/4 border-b border-amber-400 border-dashed" />
            </div>

            {/* Depth Markers */}
            <div className="flex justify-between text-[10px] font-mono text-slate-500 z-10">
              <span>0m (Surface Mixed Layer)</span>
              <span className="text-cyan-400">Thermocline Layer (~35m)</span>
              <span>120m (Benthic Floor)</span>
            </div>

            {/* SVG Seafloor profile */}
            <svg className="w-full h-36" viewBox="0 0 600 120" preserveAspectRatio="none">
              <defs>
                <linearGradient id="bathyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#083344" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#022c22" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#0f172a" stopOpacity="1" />
                </linearGradient>
              </defs>
              <path
                d="M0,20 Q150,45 300,30 T450,85 T600,110 L600,120 L0,120 Z"
                fill="url(#bathyGrad)"
                stroke="#06b6d4"
                strokeWidth="1.5"
              />
              {/* Fish Shoal Marker */}
              <circle cx="340" cy="40" r="5" fill="#10b981" className="animate-ping" />
              <circle cx="340" cy="40" r="4" fill="#34d399" />
            </svg>

            <div className="flex items-center justify-between text-xs font-mono text-cyan-300 z-10">
              <span>INCOIS PFZ Pelagic Boundary: 65m Depth</span>
              <span className="text-emerald-400">Biological Productivity Index: 92/100</span>
            </div>
          </div>

          {/* Depth Slider */}
          <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800 flex items-center gap-4">
            <span className="text-xs font-mono text-slate-300 whitespace-nowrap">
              Inspection Depth: <strong className="text-cyan-300">{selectedDepth}m</strong>
            </span>
            <input
              type="range"
              min="5"
              max="120"
              value={selectedDepth}
              onChange={(e) => setSelectedDepth(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
          </div>
        </div>

        {/* Right: Oceanic Parameters List */}
        <div className="glass-panel p-5 rounded-2xl border border-cyan-500/20 flex flex-col justify-between space-y-3">
          <div className="pb-3 border-b border-white/10 flex items-center justify-between">
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Telemetry Parameters
            </h3>
            <span className="text-[10px] font-mono text-emerald-400">UPDATED REAL-TIME</span>
          </div>

          <div className="space-y-2.5 font-mono text-xs flex-1">
            <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Wind Vectors</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-lg font-bold text-cyan-300">
                  {marineData.weather.windSpeedKnots} kn
                </span>
                <span className="text-xs text-slate-300">{marineData.weather.windDirection}</span>
              </div>
            </div>

            <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Significant Wave Height</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-lg font-bold text-amber-300">
                  {marineData.weather.waveHeightMeters} m
                </span>
                <span className="text-xs text-slate-300">Period: {marineData.weather.swellPeriodSeconds}s</span>
              </div>
            </div>

            <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">PFZ Nearest Vector</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-lg font-bold text-emerald-300">
                  {marineData.pfz.nearestZoneDistanceKm} km
                </span>
                <span className="text-xs text-slate-300">Bearing: {marineData.pfz.bearingDegrees}°</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
