import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Anchor,
  Activity,
  Waves,
  Sparkles,
  Layers,
  Thermometer,
  ShieldCheck,
  Compass,
  ArrowRight,
  TrendingUp,
  Volume2
} from 'lucide-react';
import underwaterSubImg from '../../assets/images/aurexo_sub_caustics_1790254487627.jpg';

export const AurexoEcosystemSection: React.FC = () => {
  const { marineData, setFocusedTarget, submitQuery, setIsChatOpen } = useOrcaStore();
  const [benthicDepth, setBenthicDepth] = useState(48);

  const handleInspectReef = () => {
    setFocusedTarget('auv');
    submitQuery('Perform deep benthic bio-acoustic scan and coral thermal tolerance diagnosis');
    setIsChatOpen(true);
  };

  return (
    <section className="relative min-h-screen w-full py-16 px-4 md:px-8 max-w-7xl mx-auto flex flex-col justify-center">
      
      {/* Background Submersible Oceanic Caustics Layer */}
      <div className="absolute inset-0 z-0 pointer-events-none rounded-3xl overflow-hidden opacity-35 shadow-2xl">
        <img
          src={underwaterSubImg}
          alt="Aurexo Submersible gliding through crystal clear turquoise ocean waters"
          className="w-full h-full object-cover object-center transform scale-105"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-ocean-950/95 via-ocean-900/80 to-ocean-950/95" />
      </div>

      {/* Section Header */}
      <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Anchor className="w-4 h-4 text-teal-400" />
            <h2 className="text-xs font-mono font-bold tracking-widest text-teal-300 uppercase">
              BENTHIC TWIN • SUBMERSIBLE BIO-ACOUSTICS
            </h2>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-white font-display">
            Acoustic Telemetry & Oceanic Ecosystem Diagnostics
          </h3>
        </div>

        <button
          onClick={handleInspectReef}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-500 text-ocean-950 font-bold text-xs shadow-lg shadow-teal-500/20 hover:from-teal-400 hover:to-cyan-400 active:scale-95 transition-all flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Launch Deep Submersible Scan</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      {/* 3-Column Ecosystem Layout */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        
        {/* LEFT HUD: "Acoustic Telemetry" & "Ecosystem Tracking" */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="glass-card-ocean p-5 rounded-3xl border border-cyan-500/30 shadow-2xl flex-1">
            
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
              <span className="text-xs font-bold font-mono tracking-wider text-cyan-200 uppercase">
                Acoustic Telemetry
              </span>
              <span className="text-[10px] font-mono text-teal-300 bg-teal-950/80 px-2.5 py-0.5 rounded-full font-bold border border-teal-500/40">
                HYDROPHONE 04
              </span>
            </div>

            {/* Rotating Sonar Radar Scope */}
            <div className="my-4 flex flex-col items-center justify-center">
              <div className="relative w-36 h-36 rounded-full border-2 border-teal-400/60 bg-ocean-950/90 shadow-inner flex items-center justify-center overflow-hidden">
                {/* Sonar sweep arm */}
                <div className="absolute inset-0 origin-center animate-radar-sweep bg-[conic-gradient(from_0deg,transparent_0_300deg,rgba(20,184,166,0.45)_360deg)] rounded-full" />
                <div className="w-24 h-24 rounded-full border border-teal-500/30" />
                <div className="w-12 h-12 rounded-full border border-teal-500/30" />
                {/* Targets */}
                <div className="absolute top-8 right-10 w-2.5 h-2.5 rounded-full bg-teal-400 animate-ping" />
                <div className="absolute bottom-10 left-12 w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
                <span className="text-xs font-mono font-bold text-teal-200 z-10 drop-shadow-sm">42.8 kHz</span>
              </div>
              <p className="text-[11px] font-mono text-slate-400 mt-2">
                Bio-Acoustic Marine Frequency Signature
              </p>
            </div>

            {/* Ecosystem Tracking Metrics */}
            <div className="pt-3 border-t border-cyan-500/20 space-y-2">
              <span className="text-[11px] font-mono font-bold text-slate-300 uppercase block">
                Ecosystem Tracking
              </span>
              <div className="p-3 rounded-2xl bg-ocean-900/60 border border-cyan-500/20 flex justify-between items-center text-xs font-mono">
                <span className="text-slate-300 font-semibold">Phytoplankton Bloom</span>
                <span className="font-bold text-emerald-300 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded-md">OPTIMAL (+14%)</span>
              </div>
              <div className="p-3 rounded-2xl bg-ocean-900/60 border border-cyan-500/20 flex justify-between items-center text-xs font-mono">
                <span className="text-slate-300 font-semibold">Coral Thermal Tolerance</span>
                <span className="font-bold text-cyan-200">LOW STRESS (0.4 DHW)</span>
              </div>
              <div className="p-3 rounded-2xl bg-ocean-900/60 border border-cyan-500/20 flex justify-between items-center text-xs font-mono">
                <span className="text-slate-300 font-semibold">Salinity Profile</span>
                <span className="font-bold text-cyan-200">35.2 PSU</span>
              </div>
            </div>

            {/* Benthic Depth Interactive Slider */}
            <div className="mt-4 pt-3 border-t border-cyan-500/20">
              <div className="flex justify-between items-center text-xs font-mono mb-1.5">
                <span className="text-slate-400">Thermocline Depth:</span>
                <span className="font-bold text-cyan-300">{benthicDepth} meters</span>
              </div>
              <input
                type="range"
                min="5"
                max="120"
                value={benthicDepth}
                onChange={(e) => setBenthicDepth(Number(e.target.value))}
                className="w-full h-1.5 bg-ocean-900 rounded-lg appearance-none cursor-pointer accent-teal-400"
              />
            </div>

          </div>
        </div>

        {/* CENTER: Photographic Underwater Viewport with AUV Submersible */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="glass-card-ocean p-5 rounded-3xl border border-cyan-500/30 shadow-2xl flex-1 flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-teal-400 animate-ping" />
                <span className="text-xs font-bold font-mono tracking-wider text-cyan-200 uppercase">
                  Submersible Craft Aurexo-Sub-04
                </span>
              </div>
              <span className="text-[10px] font-mono text-emerald-300 bg-emerald-950/80 px-2.5 py-0.5 rounded-full font-bold border border-emerald-500/40">
                SUBMERGED 48M
              </span>
            </div>

            {/* High-Resolution Submersible Feed Display */}
            <div className="relative flex-1 rounded-2xl overflow-hidden mt-3 min-h-[260px] border border-cyan-500/30 shadow-lg group">
              <img
                src={underwaterSubImg}
                alt="Aurexo Submersible Underwater with caustic sunbeams"
                className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-ocean-950/80 via-transparent to-transparent pointer-events-none" />

              {/* Water Caustics Shimmer Effect */}
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,rgba(6,182,212,0.25)_0%,transparent_60%)] pointer-events-none" />

              {/* Overlay HUD Telemetry Text */}
              <div className="absolute bottom-3.5 left-4 right-4 flex items-center justify-between text-white text-xs font-mono drop-shadow-md">
                <div>
                  <p className="font-bold text-sm">Benthic Reef Survey • Sector C</p>
                  <p className="text-[10px] text-teal-300">Optical Caustics & Multibeam Sonar</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-emerald-300">Temp: 27.6°C</p>
                  <p className="text-[10px] text-cyan-300">Pressure: 4.8 atm</p>
                </div>
              </div>
            </div>

            {/* Bottom Diagnostic Audio Waveform */}
            <div className="mt-3 p-3.5 rounded-2xl bg-ocean-900/60 border border-cyan-500/20 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-300 font-semibold">
                <Volume2 className="w-4 h-4 text-teal-400" />
                <span>Cetacean Bio-Click Filter:</span>
              </div>
              <div className="flex items-end gap-1.5 h-5">
                {[40, 65, 30, 85, 45, 95, 60, 40, 75, 50, 90, 30].map((h, i) => (
                  <span
                    key={i}
                    style={{ height: `${h}%` }}
                    className="w-1.5 bg-gradient-to-t from-teal-400 to-cyan-400 rounded-full animate-pulse shadow-xs shadow-teal-400/50"
                  />
                ))}
              </div>
            </div>

          </div>
        </div>

        {/* RIGHT HUD: "Predictive AI" (90% and 93% Dials) */}
        <div className="lg:col-span-3 flex flex-col gap-4">
          <div className="glass-card-ocean p-5 rounded-3xl border border-cyan-500/30 shadow-2xl flex-1">
            
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
              <span className="text-xs font-bold font-mono tracking-wider text-cyan-200 uppercase">
                Predictive AI
              </span>
              <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/80 px-2.5 py-0.5 rounded-full font-bold border border-cyan-400/40">
                ML TWIN
              </span>
            </div>

            {/* Dials: 90% and 93% */}
            <div className="mt-4 grid grid-cols-2 gap-3 text-center">
              {/* Dial 1: 90% */}
              <div className="flex flex-col items-center p-3 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <div className="relative w-18 h-18 flex items-center justify-center">
                  <svg className="w-full h-full transform -rotate-90 drop-shadow-sm" viewBox="0 0 36 36">
                    <path
                      className="text-ocean-950"
                      strokeWidth="3.2"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="text-teal-400"
                      strokeDasharray="90, 100"
                      strokeWidth="3.2"
                      strokeLinecap="round"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <span className="absolute text-base font-black font-mono text-white">90%</span>
                </div>
                <span className="text-[11px] font-mono font-bold text-cyan-200 mt-1">Bio-Recovery</span>
                <span className="text-[10px] text-slate-400 font-mono">Prediction</span>
              </div>

              {/* Dial 2: 93% */}
              <div className="flex flex-col items-center p-3 rounded-2xl bg-ocean-900/60 border border-cyan-500/20">
                <div className="relative w-18 h-18 flex items-center justify-center">
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
                      strokeDasharray="93, 100"
                      strokeWidth="3.2"
                      strokeLinecap="round"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <span className="absolute text-base font-black font-mono text-white">93%</span>
                </div>
                <span className="text-[11px] font-mono font-bold text-cyan-200 mt-1">Chlorophyll</span>
                <span className="text-[10px] text-slate-400 font-mono">Confidence</span>
              </div>
            </div>

            {/* AI Analytics Status Feed */}
            <div className="mt-4 pt-3 border-t border-cyan-500/20 space-y-2">
              <span className="text-[11px] font-mono font-bold text-slate-300 uppercase block">
                Above AI Analytics
              </span>
              <div className="p-2.5 rounded-lg bg-teal-950/60 border border-teal-500/30 text-[11px] font-mono text-teal-200">
                <div className="flex items-center gap-1 font-bold mb-0.5">
                  <TrendingUp className="w-3.5 h-3.5 text-teal-400" />
                  <span>Upwelling Trend Confirmed</span>
                </div>
                Deep nutrient influx from continental slope rising toward surface shelf.
              </div>
              <div className="p-2.5 rounded-lg bg-cyan-950/60 border border-cyan-500/30 text-[11px] font-mono text-cyan-200">
                <div className="flex items-center gap-1 font-bold mb-0.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Sanctuary Integrity 99.1%</span>
                </div>
                Zero thermal bleaching mortality observed along Lakshadweep transect.
              </div>
            </div>

          </div>
        </div>

      </div>

    </section>
  );
};
