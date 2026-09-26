import React, { useState } from 'react';
import { Compass, Activity, Radio, Layers, Thermometer, ShieldCheck } from 'lucide-react';

export const HeroArgoFloat: React.FC = () => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="relative group cursor-pointer p-4 transition-transform duration-300"
    >
      {/* Scanning Ring pulse effect when hovered */}
      <div
        className={`absolute inset-0 rounded-full border border-cyan-400/40 transition-all duration-500 pointer-events-none ${
          isHovered ? 'scale-150 opacity-100 animate-ping' : 'scale-90 opacity-0'
        }`}
      />

      {/* Stylized SVG ARGO Float Vehicle */}
      <div className="relative w-32 h-64 mx-auto animate-float flex flex-col items-center justify-center">
        {/* Antenna */}
        <div className="w-1.5 h-12 bg-gradient-to-t from-slate-400 to-cyan-500 rounded-t relative">
          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_12px_#06B6D4]" />
        </div>

        {/* Float Cap */}
        <div className="w-16 h-6 rounded-t-xl bg-gradient-to-r from-ocean-700 via-ocean-600 to-teal-500 border border-cyan-400/60 shadow-md" />

        {/* Main Hull */}
        <div className="w-22 h-38 bg-gradient-to-b from-white via-cyan-50 to-sky-100 border-2 border-cyan-400/70 rounded-b-2xl shadow-xl flex flex-col items-center justify-between p-3 relative overflow-hidden">
          <div className="w-full flex items-center justify-between text-[9px] font-mono text-ocean-800 px-1 border-b border-cyan-200 pb-1 font-bold">
            <span>ARGO SOLO-II</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          </div>

          <div className="flex flex-col items-center gap-1 my-auto">
            <Radio className="w-5 h-5 text-cyan-600 animate-pulse" />
            <span className="text-[10px] font-mono font-bold text-ocean-950 tracking-wider">
              INCOIS-2902746
            </span>
          </div>

          {/* Sensor Head */}
          <div className="w-full flex justify-center border-t border-cyan-200 pt-1">
            <div className="w-10 h-4 rounded-b bg-cyan-200/90 border border-cyan-300" />
          </div>
        </div>

        {/* Bottom Ballast Weight */}
        <div className="w-8 h-8 rounded-b-full bg-slate-800 border border-slate-600 shadow-md mt-1" />
      </div>

      {/* Hover Telemetry Glass Tooltip */}
      <div
        className={`absolute left-1/2 -translate-x-1/2 top-full mt-2 w-72 p-4 rounded-2xl bg-ocean-950/95 border border-cyan-400/40 backdrop-blur-2xl shadow-2xl transition-all duration-300 z-30 pointer-events-none ${
          isHovered ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-95'
        }`}
      >
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-cyan-500/20 text-xs">
          <div className="flex items-center gap-1.5 text-white font-extrabold font-mono">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span>ARGO FLOAT #2902746</span>
          </div>
          <span className="px-2 py-0.5 rounded text-[9px] font-mono bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-400/40">
            ● SYNCED
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-300">
          <div className="flex items-center gap-1 text-slate-400">
            <Layers className="w-3 h-3 text-cyan-400" />
            <span>DEPTH:</span>
            <span className="font-bold text-white">742 m</span>
          </div>
          <div className="flex items-center gap-1 text-slate-400">
            <Thermometer className="w-3 h-3 text-amber-400" />
            <span>SST:</span>
            <span className="font-bold text-amber-300">28.7 °C</span>
          </div>
          <div className="flex items-center gap-1 text-slate-400">
            <Compass className="w-3 h-3 text-teal-400" />
            <span>SALINITY:</span>
            <span className="font-bold text-teal-300">35.6 PSU</span>
          </div>
          <div className="flex items-center gap-1 text-slate-400">
            <span>REGION:</span>
            <span className="font-bold text-cyan-300 truncate">Goa Shelf</span>
          </div>
        </div>

        <div className="mt-2.5 pt-2 border-t border-cyan-500/20 text-[10px] text-cyan-400 font-mono text-center font-bold flex items-center justify-center gap-1">
          <ShieldCheck className="w-3 h-3 text-emerald-400" />
          <span>Real-time ISRO / INCOIS Calibrated</span>
        </div>
      </div>
    </div>
  );
};
