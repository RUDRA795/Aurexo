import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Thermometer,
  Waves,
  Activity,
  Sliders,
  SlidersHorizontal,
  Navigation,
  Anchor,
  Compass,
  Zap,
} from 'lucide-react';

export const MarineDataCards: React.FC = () => {
  const { marineData, setDayNightMode, dayNightMode, setFocusedTarget } = useOrcaStore();

  // Scenario Lab toggles (matching Reference Video 2 "Scenario Lab: Boats drone, Quickinspect, Grid opacity")
  const [boatsDrone, setBoatsDrone] = useState(true);
  const [quickInspect, setQuickInspect] = useState(false);
  const [gridOpacity, setGridOpacity] = useState(75);

  return (
    <div className="flex flex-col h-full space-y-3 overflow-y-auto pr-1">
      {/* 1. SST Telemetry Glassmorphic Card (from Video 2 "SST 7.75 °C / 28.4 °C") */}
      <div className="glass-panel p-4 rounded-2xl border border-cyan-500/20 shadow-xl">
        <div className="flex items-center justify-between pb-2 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Thermometer className="w-4 h-4 text-amber-400" />
            <h3 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
              OCEAN THERMAL (SST)
            </h3>
          </div>
          <span className="text-[10px] font-mono text-cyan-400">INCOIS-OISST</span>
        </div>

        <div className="flex items-baseline justify-between mt-3">
          <div>
            <span className="text-3xl font-display font-extrabold text-white tracking-tight tabular-nums">
              {marineData.sst.current.toFixed(2)}
            </span>
            <span className="text-sm font-display text-amber-400 ml-1 font-semibold">
              {marineData.sst.unit}
            </span>
          </div>
          <div className="text-right">
            <span className="text-xs font-mono text-emerald-400 block font-semibold">
              {marineData.sst.trend}
            </span>
            <span className="text-[10px] font-mono text-slate-400">Surface mixed layer</span>
          </div>
        </div>

        {/* 3 Circular Arc Gauges (matching Video 2: 34%, 74%, 88%) */}
        <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-slate-800/80 text-center font-mono">
          <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
            <span className="text-[10px] text-slate-400 block">Mixed Layer</span>
            <span className="text-sm font-bold text-cyan-300">34%</span>
            <div className="w-full bg-slate-800 h-1 rounded-full mt-1.5 overflow-hidden">
              <div className="bg-cyan-400 h-full rounded-full" style={{ width: '34%' }} />
            </div>
          </div>

          <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
            <span className="text-[10px] text-slate-400 block">Gradient</span>
            <span className="text-sm font-bold text-amber-300">74%</span>
            <div className="w-full bg-slate-800 h-1 rounded-full mt-1.5 overflow-hidden">
              <div className="bg-amber-400 h-full rounded-full" style={{ width: '74%' }} />
            </div>
          </div>

          <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
            <span className="text-[10px] text-slate-400 block">Front Index</span>
            <span className="text-sm font-bold text-emerald-300">88%</span>
            <div className="w-full bg-slate-800 h-1 rounded-full mt-1.5 overflow-hidden">
              <div className="bg-emerald-400 h-full rounded-full" style={{ width: '88%' }} />
            </div>
          </div>
        </div>
      </div>

      {/* 2. Scenario Lab Card (matching Video 2 "Scenario Lab") */}
      <div className="glass-panel p-4 rounded-2xl border border-cyan-500/20 shadow-xl">
        <div className="flex items-center justify-between pb-2 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
              SCENARIO LAB
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">PARAM CONTROLS</span>
        </div>

        <div className="mt-3 space-y-3 font-mono text-xs">
          {/* Toggle 1: Boats drone */}
          <div className="flex items-center justify-between">
            <span className="text-slate-300">Boats & Drone Sync</span>
            <button
              onClick={() => setBoatsDrone(!boatsDrone)}
              className={`w-10 h-5 rounded-full p-0.5 transition-colors relative ${
                boatsDrone ? 'bg-cyan-500' : 'bg-slate-800'
              }`}
            >
              <div
                className={`w-4 h-4 rounded-full bg-white transition-transform ${
                  boatsDrone ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Toggle 2: Day / Night Lighting Mode */}
          <div className="flex items-center justify-between">
            <span className="text-slate-300">Atmosphere Lighting</span>
            <button
              onClick={() => setDayNightMode(dayNightMode === 'night' ? 'day' : 'night')}
              className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase border transition-colors ${
                dayNightMode === 'night'
                  ? 'bg-indigo-950/60 text-cyan-300 border-cyan-500/40'
                  : 'bg-amber-950/60 text-amber-300 border-amber-500/40'
              }`}
            >
              {dayNightMode === 'night' ? 'Night Recon' : 'Day Ocean'}
            </button>
          </div>

          {/* Slider: Grid Opacity */}
          <div>
            <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
              <span>Grid Bathymetry</span>
              <span className="text-cyan-300 font-bold">{gridOpacity}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="100"
              value={gridOpacity}
              onChange={(e) => setGridOpacity(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
          </div>
        </div>
      </div>

      {/* 3. Real-Time Telemetry & Loss Plot (matching Video 2 "Loss Plot") */}
      <div className="glass-panel p-4 rounded-2xl border border-cyan-500/20 shadow-xl">
        <div className="flex items-center justify-between pb-2 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
              TELEMETRY & LOSS CONVERGENCE
            </h3>
          </div>
          <span className="text-[10px] font-mono text-emerald-400">99.2% ACCURACY</span>
        </div>

        {/* SVG Sparkline Plot */}
        <div className="mt-3 h-24 w-full bg-slate-950/60 rounded-xl p-2 border border-slate-800/80 relative overflow-hidden">
          <svg className="w-full h-full" viewBox="0 0 300 80" preserveAspectRatio="none">
            <defs>
              <linearGradient id="plotGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Grid lines */}
            <line x1="0" y1="20" x2="300" y2="20" stroke="#334155" strokeDasharray="3,3" strokeWidth="0.5" />
            <line x1="0" y1="40" x2="300" y2="40" stroke="#334155" strokeDasharray="3,3" strokeWidth="0.5" />
            <line x1="0" y1="60" x2="300" y2="60" stroke="#334155" strokeDasharray="3,3" strokeWidth="0.5" />

            {/* Area fill */}
            <path
              d="M0,65 Q40,55 80,45 T160,25 T240,15 T300,10 L300,80 L0,80 Z"
              fill="url(#plotGrad)"
            />

            {/* Sparkline curve */}
            <path
              d="M0,65 Q40,55 80,45 T160,25 T240,15 T300,10"
              fill="none"
              stroke="#22d3ee"
              strokeWidth="2.5"
            />

            {/* Moving target dot */}
            <circle cx="300" cy="10" r="3.5" fill="#38bdf8" className="animate-ping" />
            <circle cx="300" cy="10" r="2.5" fill="#ffffff" />
          </svg>

          <div className="absolute bottom-1 right-2 text-[9px] font-mono text-cyan-400">
            Loss: 0.0142 (Converged)
          </div>
        </div>
      </div>

      {/* 4. Autonomous Craft Quick-Status (Aerial Drone & Underwater AUV) */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => setFocusedTarget('drone')}
          className="glass-panel p-3 rounded-xl border border-cyan-500/20 text-left hover:border-cyan-400/50 transition-colors group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-cyan-300">ORCA-AERO-01</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <p className="text-xs font-bold text-white mt-1 group-hover:text-cyan-200">Aerial Drone</p>
          <div className="text-[10px] font-mono text-slate-400 mt-1">
            Alt: {marineData.surveillance.aerialDrone.altitudeMeters}m · Spd: {marineData.surveillance.aerialDrone.speedKnots}kn
          </div>
        </button>

        <button
          onClick={() => setFocusedTarget('auv')}
          className="glass-panel p-3 rounded-xl border border-cyan-500/20 text-left hover:border-emerald-400/50 transition-colors group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-emerald-300">ORCA-SUB-04</span>
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <p className="text-xs font-bold text-white mt-1 group-hover:text-emerald-200">Sub AUV</p>
          <div className="text-[10px] font-mono text-slate-400 mt-1">
            Depth: {marineData.surveillance.underwaterAuv.depthMeters}m · {marineData.surveillance.underwaterAuv.acousticTelemetryDb}dB
          </div>
        </button>
      </div>
    </div>
  );
};
