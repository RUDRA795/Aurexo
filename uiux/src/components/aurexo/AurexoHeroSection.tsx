import React from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { HeroArgoFloat } from '../landing/HeroArgoFloat';
import {
  Compass,
  Radio,
  Sparkles,
  ChevronDown,
  Navigation,
  Anchor,
  Wind,
  Layers,
  ArrowRight,
  ShieldCheck,
  Cpu,
  Database,
  Waves
} from 'lucide-react';
import heroDroneImg from '../../assets/images/aurexo_hero_drone_1790254474498.jpg';

interface AurexoHeroSectionProps {
  onExplore: () => void;
}

export const AurexoHeroSection: React.FC<AurexoHeroSectionProps> = ({ onExplore }) => {
  const { submitQuery, setIsChatOpen, setFocusedTarget } = useOrcaStore();

  const handleLaunchScenario = (query: string, target: 'drone' | 'auv' | 'center') => {
    setFocusedTarget(target);
    submitQuery(query);
    setIsChatOpen(true);
  };

  return (
    <section className="relative min-h-screen w-full flex flex-col justify-between pt-28 pb-16 px-4 md:px-8 overflow-hidden">
      
      {/* Background Hero Drone Image Layer */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <img
          src={heroDroneImg}
          alt="Aurexo Maritime Drone soaring over turquoise ocean"
          className="w-full h-full object-cover object-center opacity-30 scale-105 transform animate-pulse duration-[10000ms]"
        />
        {/* Oceanic Bioluminescent Ambient Gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-ocean-950/80 via-ocean-900/60 to-ocean-950/95" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_30%,rgba(5,17,26,0.85)_100%)]" />
      </div>

      {/* Main Grid: Left Copy & SIH Actions, Right Interactive ARGO Float */}
      <div className="relative z-20 max-w-7xl mx-auto my-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-8 items-center pt-4">
        
        {/* Left Column: Heading, Vision & Mission Launchers */}
        <div className="lg:col-span-7 flex flex-col items-center lg:items-start text-center lg:text-left space-y-6">
          
          {/* Top Tagline Pill */}
          <div className="inline-flex items-center gap-2.5 px-4.5 py-1.5 rounded-full glass-panel-ocean border border-cyan-400/40 shadow-lg animate-shimmer">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs font-bold text-cyan-200 font-mono tracking-wider">
              ISRO PS 26176 • MULTI-AGENT MARINE TWIN
            </span>
            <Sparkles className="w-3.5 h-3.5 text-cyan-300" />
          </div>

          {/* Headline inspired by Nereus */}
          <h1 className="text-4xl sm:text-6xl md:text-7xl font-black text-white font-display tracking-tight leading-[1.08]">
            Talk to the{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400">
              Living Ocean.
            </span>
          </h1>

          <p className="text-base sm:text-lg text-slate-300 max-w-xl font-light leading-relaxed">
            Aurexo fuses autonomous aerial maritime drones, benthic submersibles, and satellite telemetry into a zero-hallucination agentic intelligence grid for ocean conservation, fisheries, and coastal safety.
          </p>

          {/* Quick Action Buttons */}
          <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 pt-2">
            <button
              onClick={() => handleLaunchScenario('Where is the nearest verified Potential Fishing Zone (PFZ) today? Search wave, swell, and SST.', 'drone')}
              className="flex items-center gap-2 px-6 py-3.5 rounded-2xl bg-gradient-to-r from-cyan-500 to-teal-500 text-ocean-950 font-black text-xs font-mono shadow-lg hover:shadow-cyan-500/30 active:scale-95 transition-all duration-200 cursor-pointer"
            >
              <Waves className="w-4 h-4 stroke-[2.5]" />
              <span>EXPLORE PFZ & SATELLITE SST</span>
            </button>

            <button
              onClick={() => handleLaunchScenario('I am fishing out of Rameshwaram. Can I head towards the Palk Strait boundary? Check IMBL geofence.', 'center')}
              className="flex items-center gap-2 px-6 py-3.5 rounded-2xl glass-panel-ocean border border-cyan-400/40 text-cyan-200 font-bold text-xs font-mono hover:bg-cyan-500/20 active:scale-95 transition-all duration-200 cursor-pointer"
            >
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>CHECK IMBL GEOFENCE</span>
            </button>
          </div>

          {/* Metadata Highlights */}
          <div className="pt-4 border-t border-cyan-500/20 flex flex-wrap items-center justify-center lg:justify-start gap-5 text-xs font-mono text-slate-400">
            <div className="flex items-center gap-1.5 text-cyan-300">
              <Database className="w-3.5 h-3.5" />
              <span>4,000+ ARGO Floats</span>
            </div>
            <span>•</span>
            <div>INCOIS WFS & THREDDS</div>
            <span>•</span>
            <div className="text-emerald-400 font-semibold">PostGIS 3.5 Geofenced</div>
          </div>

        </div>

        {/* Right Column: Stylized Nereus ARGO Float with Live Telemetry */}
        <div className="lg:col-span-5 flex flex-col items-center justify-center">
          <HeroArgoFloat />
        </div>

      </div>

      {/* Interactive SIH Mission Chips (Bottom Bar) */}
      <div className="relative z-20 max-w-6xl mx-auto w-full pt-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          
          <button
            onClick={() => handleLaunchScenario('Where is the nearest Potential Fishing Zone (PFZ) today?', 'drone')}
            className="p-3.5 rounded-2xl glass-card-ocean text-left transition-all hover:border-cyan-400/60 group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="w-7 h-7 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                <Navigation className="w-3.5 h-3.5 text-cyan-300 group-hover:rotate-12 transition-transform" />
              </div>
              <span className="text-[10px] font-mono text-cyan-400 font-bold">INCOIS PFZ</span>
            </div>
            <div className="text-xs font-bold text-white mb-0.5">Where is the nearest PFZ?</div>
            <p className="text-[11px] text-slate-400 line-clamp-1">Locate thermal chlorophyll front off Goa shelf</p>
          </button>

          <button
            onClick={() => handleLaunchScenario('Is it safe to venture into the sea tomorrow morning? Check wave height, swell, and wind.', 'center')}
            className="p-3.5 rounded-2xl glass-card-ocean text-left transition-all hover:border-teal-400/60 group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="w-7 h-7 rounded-xl bg-teal-500/20 flex items-center justify-center">
                <Wind className="w-3.5 h-3.5 text-teal-300 group-hover:rotate-12 transition-transform" />
              </div>
              <span className="text-[10px] font-mono text-teal-400 font-bold">SAFETY GATE</span>
            </div>
            <div className="text-xs font-bold text-white mb-0.5">Is it safe to venture tomorrow?</div>
            <p className="text-[11px] text-slate-400 line-clamp-1">Operational wave height & swell verification</p>
          </button>

          <button
            onClick={() => handleLaunchScenario('I am fishing out of Rameshwaram. Can I head towards the Palk Strait boundary?', 'center')}
            className="p-3.5 rounded-2xl glass-card-ocean text-left transition-all hover:border-amber-400/60 group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="w-7 h-7 rounded-xl bg-amber-500/20 flex items-center justify-center">
                <ShieldCheck className="w-3.5 h-3.5 text-amber-300 group-hover:rotate-12 transition-transform" />
              </div>
              <span className="text-[10px] font-mono text-amber-400 font-bold">IMBL GUARD</span>
            </div>
            <div className="text-xs font-bold text-white mb-0.5">Check Rameshwaram IMBL</div>
            <p className="text-[11px] text-slate-400 line-clamp-1">Standoff buffer & geofencing alerts</p>
          </button>

          <button
            onClick={() => handleLaunchScenario('Research why fish productivity has declined in the Arabian Sea over the last five years.', 'auv')}
            className="p-3.5 rounded-2xl glass-card-ocean text-left transition-all hover:border-emerald-400/60 group cursor-pointer"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="w-7 h-7 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                <Compass className="w-3.5 h-3.5 text-emerald-300 group-hover:rotate-12 transition-transform" />
              </div>
              <span className="text-[10px] font-mono text-emerald-400 font-bold">DEEP RESEARCH</span>
            </div>
            <div className="text-xs font-bold text-white mb-0.5">Arabian Sea 5-Yr Trends</div>
            <p className="text-[11px] text-slate-400 line-clamp-1">Synthesizes satellite SST & CMFRI papers</p>
          </button>

        </div>
      </div>

      {/* Bottom Scroll Prompt */}
      <div className="relative z-20 flex flex-col items-center justify-center mt-6">
        <button
          onClick={onExplore}
          className="flex flex-col items-center gap-1.5 text-slate-400 hover:text-cyan-300 transition-colors group cursor-pointer"
        >
          <span className="text-[11px] font-mono tracking-widest font-bold uppercase text-cyan-400">
            Scroll to explore Aurexo Command Suite
          </span>
          <div className="w-8 h-8 rounded-full bg-ocean-900/80 border border-cyan-500/30 shadow-md flex items-center justify-center group-hover:translate-y-1 transition-transform">
            <ChevronDown className="w-4 h-4 text-cyan-400 animate-bounce" />
          </div>
        </button>
      </div>

    </section>
  );
};
