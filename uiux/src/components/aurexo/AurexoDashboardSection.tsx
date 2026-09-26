import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { NereusMarineMap } from '../map/NereusMarineMap';
import { AurexoMarineMap } from './AurexoMarineMap';
import {
  Activity,
  Compass,
  Navigation,
  Wind,
  Thermometer,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Cpu,
  Layers,
  Sparkles,
  ArrowUpRight,
  Clock,
  CheckCircle2,
  Radio,
  Satellite
} from 'lucide-react';

export const AurexoDashboardSection: React.FC = () => {
  const { marineData, agentStatus, isRunning, toolCalls, cancelRun } = useOrcaStore();
  const [viewEngine, setViewEngine] = useState<'google_satellite' | 'radar'>('google_satellite');

  const getToolBadgeColor = (tool: string) => {
    if (tool.includes('pfz')) return 'bg-cyan-950/80 text-cyan-300 border-cyan-500/40';
    if (tool.includes('sst')) return 'bg-amber-950/80 text-amber-300 border-amber-500/40';
    if (tool.includes('weather')) return 'bg-teal-950/80 text-teal-300 border-teal-500/40';
    return 'bg-sky-950/80 text-sky-300 border-sky-500/40';
  };

  return (
    <section className="relative min-h-screen w-full py-16 px-4 md:px-8 max-w-7xl mx-auto flex flex-col justify-center">
      
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-300 uppercase">
              AUREXO COMMAND CENTER • LIVE TELEMETRY
            </h2>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-white font-display">
            Autonomous Maritime Fleet & Spatial Operations
          </h3>
        </div>

        {/* Status Pill */}
        <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl glass-panel-ocean border border-cyan-500/30 text-xs font-mono">
          <span className="text-slate-400">MISSION STATUS:</span>
          <span className="font-bold text-emerald-300 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded-md">
            REAL-TIME NOMINAL
          </span>
        </div>
      </div>

      {/* Main 3-Column Command Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        
        {/* LEFT HUD: "Track Tracking" Card */}
        <div className="lg:col-span-3 flex flex-col gap-4">
          <div className="glass-card-ocean p-5 rounded-3xl border border-cyan-500/30 shadow-2xl">
            
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
              <span className="text-xs font-bold font-mono tracking-wider text-cyan-200 uppercase">
                Track Tracking
              </span>
              <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/80 px-2.5 py-0.5 rounded-full font-bold border border-cyan-400/40">
                AERO-01
              </span>
            </div>

            {/* Metric 3.58 and -38% */}
            <div className="mt-4 flex items-baseline justify-between">
              <div>
                <span className="text-4xl font-black font-display text-white tracking-tight">
                  3.58
                </span>
                <span className="text-xs text-cyan-300/60 font-mono ml-1">nmi</span>
              </div>
              <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-950/80 text-emerald-300 text-xs font-bold font-mono border border-emerald-500/40 shadow-xs">
                <TrendingDown className="w-3.5 h-3.5" />
                <span>-38%</span>
              </div>
            </div>
            <p className="text-[11px] text-slate-400 font-mono mt-1">
              Cross-track deviation vs. planned corridor
            </p>

            {/* Flight & Course Metrics */}
            <div className="mt-4 pt-3 border-t border-cyan-500/20 grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="p-2.5 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-[10px] text-slate-400 block">Ground Speed</span>
                <span className="font-bold text-white text-sm">18.4 kt</span>
              </div>
              <div className="p-2.5 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-[10px] text-slate-400 block">Prevision</span>
                <span className="font-bold text-cyan-300 text-sm">1.58</span>
              </div>
              <div className="p-2.5 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-[10px] text-slate-400 block">Course True</span>
                <span className="font-bold text-white text-sm">042° NE</span>
              </div>
              <div className="p-2.5 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-[10px] text-slate-400 block">Altitude</span>
                <span className="font-bold text-white text-sm">120 m</span>
              </div>
            </div>

            {/* Circular Compass Gauge "159" */}
            <div className="mt-4 p-3.5 rounded-2xl bg-ocean-900/80 border border-cyan-500/30 shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="relative w-12 h-12 rounded-full border-2 border-cyan-400 bg-ocean-950 shadow-inner flex items-center justify-center">
                  <Navigation className="w-5 h-5 text-cyan-300 rotate-[159deg]" />
                  <div className="absolute inset-0 rounded-full border border-dashed border-cyan-400/50 animate-spin duration-[15000ms]" />
                </div>
                <div>
                  <span className="text-xl font-black font-mono text-white">159°</span>
                  <p className="text-[10px] text-slate-400 font-mono">Current Heading</p>
                </div>
              </div>
              <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/90 px-2.5 py-1 rounded-md font-bold border border-cyan-400/40">
                LOCKED
              </span>
            </div>

          </div>

          {/* Sensor Nodes Online */}
          <div className="glass-panel-ocean p-4 rounded-2xl border border-cyan-500/20 shadow-md">
            <span className="text-[11px] font-mono font-bold text-slate-400 uppercase block mb-2">
              Sensor Nodes Online
            </span>
            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex items-center justify-between p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-slate-300">Goa Coastal Radar</span>
                <span className="text-emerald-400 font-bold">ACTIVE</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-slate-300">INCOIS Wave Buoy 03</span>
                <span className="text-emerald-400 font-bold">1.35m Swell</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-slate-300">Submersible AUV-04</span>
                <span className="text-cyan-300 font-bold">Telemetry OK</span>
              </div>
            </div>
          </div>
        </div>

        {/* CENTER: Interactive Spatial Marine Map (Nereus Leaflet Map) */}
        <div className="lg:col-span-6 flex flex-col gap-4">
          
          {/* Map Engine View Selector */}
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono font-bold text-slate-300 uppercase">
                Marine Spatial Surface:
              </span>
            </div>
            <div className="flex items-center gap-1 bg-ocean-900/90 p-0.5 rounded-xl border border-cyan-500/30 text-xs font-mono">
              <button
                onClick={() => setViewEngine('google_satellite')}
                className={`px-3 py-1 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
                  viewEngine === 'google_satellite'
                    ? 'bg-cyan-500 text-ocean-950 shadow-xs'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Satellite className="w-3.5 h-3.5" />
                <span>Satellite & Bathymetry</span>
              </button>
              <button
                onClick={() => setViewEngine('radar')}
                className={`px-3 py-1 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
                  viewEngine === 'radar'
                    ? 'bg-cyan-500 text-ocean-950 shadow-xs'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Compass className="w-3.5 h-3.5" />
                <span>Tactical Vector</span>
              </button>
            </div>
          </div>

          {viewEngine === 'google_satellite' ? (
            <NereusMarineMap className="w-full h-[480px] md:h-[510px]" />
          ) : (
            <AurexoMarineMap />
          )}

          {/* Agent Activity Execution Stream */}
          <div className="glass-panel-ocean p-4 rounded-2xl border border-cyan-500/30 shadow-lg">
            <div className="flex items-center justify-between pb-2.5 border-b border-cyan-500/20">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
                <span className="text-xs font-bold font-mono text-cyan-200 uppercase">
                  Aurexo Multi-Agent Execution Stream
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-cyan-400 animate-ping' : 'bg-emerald-400'}`} />
                <span className="text-[10px] font-mono text-slate-300 font-medium">
                  {isRunning ? 'RUNNING' : 'SYNCED'}
                </span>
                {isRunning && (
                  <button
                    onClick={cancelRun}
                    className="text-[10px] font-mono text-rose-400 hover:text-rose-300 underline ml-2 cursor-pointer"
                  >
                    Stop
                  </button>
                )}
              </div>
            </div>

            {/* Invocations */}
            <div className="mt-3 space-y-2 max-h-40 overflow-y-auto pr-1">
              {toolCalls.length === 0 ? (
                <div className="p-3 rounded-xl bg-ocean-950/60 border border-dashed border-cyan-500/30 text-center text-xs font-mono text-slate-400">
                  Aurexo reasoning agents ready. Ask a query or launch an analysis chip from above.
                </div>
              ) : (
                toolCalls.map((tc, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-xl bg-ocean-900/70 border border-cyan-500/20 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${getToolBadgeColor(tc.tool)}`}>
                        {tc.tool}
                      </span>
                      <span className="text-slate-300 font-mono text-[11px]">
                        {tc.status === 'completed' ? 'Output corroboration locked' : 'Querying external satellite API...'}
                      </span>
                    </div>
                    {tc.status === 'completed' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Clock className="w-4 h-4 text-cyan-400 animate-spin" />
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* RIGHT HUD: "Premium Analytics" Card */}
        <div className="lg:col-span-3 flex flex-col gap-4">
          <div className="glass-card-ocean p-5 rounded-3xl border border-cyan-500/30 shadow-2xl">
            
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
              <span className="text-xs font-bold font-mono tracking-wider text-cyan-200 uppercase">
                Premium Analytics
              </span>
              <span className="text-[10px] font-mono text-emerald-300 bg-emerald-950/80 px-2.5 py-0.5 rounded-full font-bold border border-emerald-500/40">
                LIVE 60FPS
              </span>
            </div>

            {/* Weather Metrics */}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase font-bold">Water SST</span>
                  <Thermometer className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <span className="text-3xl font-black font-display text-white">
                  {marineData?.sst?.current ? `${marineData.sst.current}°` : '28.4°'}
                </span>
                <span className="text-[10px] text-cyan-300/60 font-mono block mt-0.5">Celsius</span>
              </div>

              <div className="p-3.5 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase font-bold">Humidity</span>
                  <Wind className="w-3.5 h-3.5 text-cyan-400" />
                </div>
                <span className="text-3xl font-black font-display text-white">
                  38%
                </span>
                <span className="text-[10px] text-cyan-300/60 font-mono block mt-0.5">Met-Ocean</span>
              </div>
            </div>

            {/* Circular Consensus Dials */}
            <div className="mt-5 pt-4 border-t border-cyan-500/20">
              <span className="text-[11px] font-mono font-bold text-slate-300 uppercase block mb-3">
                Coordination Freds & Consensus
              </span>

              <div className="grid grid-cols-2 gap-4 text-center">
                {/* Dial 1: 88% */}
                <div className="flex flex-col items-center">
                  <div className="relative w-20 h-20 flex items-center justify-center">
                    <svg className="w-full h-full transform -rotate-90 drop-shadow-sm" viewBox="0 0 36 36">
                      <path
                        className="text-ocean-950"
                        strokeWidth="3.2"
                        stroke="currentColor"
                        fill="none"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                      <path
                        className="text-cyan-400"
                        strokeDasharray="88, 100"
                        strokeWidth="3.2"
                        strokeLinecap="round"
                        stroke="currentColor"
                        fill="none"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                    </svg>
                    <span className="absolute text-base font-black font-mono text-white">88%</span>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-cyan-200 mt-1">Coord freds</span>
                  <span className="text-[10px] text-slate-400 font-mono">Aerial-Drone</span>
                </div>

                {/* Dial 2: 96% */}
                <div className="flex flex-col items-center">
                  <div className="relative w-20 h-20 flex items-center justify-center">
                    <svg className="w-full h-full transform -rotate-90 drop-shadow-sm" viewBox="0 0 36 36">
                      <path
                        className="text-ocean-950"
                        strokeWidth="3.2"
                        stroke="currentColor"
                        fill="none"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                      <path
                        className="text-emerald-400"
                        strokeDasharray="96, 100"
                        strokeWidth="3.2"
                        strokeLinecap="round"
                        stroke="currentColor"
                        fill="none"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                    </svg>
                    <span className="absolute text-base font-black font-mono text-white">96%</span>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-cyan-200 mt-1">Consensus</span>
                  <span className="text-[10px] text-slate-400 font-mono">INCOIS-PFZ</span>
                </div>
              </div>
            </div>

            {/* Premium Analytic Comparative Bars */}
            <div className="mt-5 pt-4 border-t border-cyan-500/20 space-y-2.5">
              <span className="text-[11px] font-mono font-bold text-slate-300 uppercase block">
                Premium Analytic Bands
              </span>

              <div>
                <div className="flex justify-between text-[11px] font-mono text-slate-300 mb-1">
                  <span>Chlorophyll Index</span>
                  <span className="font-bold text-cyan-200">0.84 mg/m³</span>
                </div>
                <div className="w-full bg-ocean-950 h-1.5 rounded-full overflow-hidden border border-cyan-500/20">
                  <div className="bg-gradient-to-r from-teal-400 to-emerald-400 h-full w-[78%] rounded-full shadow-xs shadow-teal-400/50" />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] font-mono text-slate-300 mb-1">
                  <span>Wave Swell Hazard</span>
                  <span className="font-bold text-cyan-200">1.35 m (Safe)</span>
                </div>
                <div className="w-full bg-ocean-950 h-1.5 rounded-full overflow-hidden border border-cyan-500/20">
                  <div className="bg-gradient-to-r from-sky-400 to-cyan-400 h-full w-[35%] rounded-full shadow-xs shadow-cyan-400/50" />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] font-mono text-slate-300 mb-1">
                  <span>Reef Temperature Tolerance</span>
                  <span className="font-bold text-amber-300">+0.3° anomaly</span>
                </div>
                <div className="w-full bg-ocean-950 h-1.5 rounded-full overflow-hidden border border-cyan-500/20">
                  <div className="bg-gradient-to-r from-amber-400 to-rose-400 h-full w-[24%] rounded-full shadow-xs shadow-amber-400/50" />
                </div>
              </div>
            </div>

          </div>
        </div>

      </div>

    </section>
  );
};
