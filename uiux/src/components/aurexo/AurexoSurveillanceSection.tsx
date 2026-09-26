import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { MarineGlobe } from '../map/MarineGlobe';
import { NereusMarineMap } from '../map/NereusMarineMap';
import {
  Globe,
  Radio,
  Satellite,
  Shield,
  Eye,
  Crosshair,
  Radar,
  Maximize2,
  Video,
  Layers,
  Sparkles
} from 'lucide-react';
import heroDroneImg from '../../assets/images/aurexo_hero_drone_1790254474498.jpg';
import underwaterSubImg from '../../assets/images/aurexo_sub_caustics_1790254487627.jpg';

export const AurexoSurveillanceSection: React.FC = () => {
  const { marineData, agentStatus } = useOrcaStore();
  const [activeFeed, setActiveFeed] = useState<'drone' | 'auv' | 'radar'>('drone');
  const [surveillanceMode, setSurveillanceMode] = useState<'satellite' | 'globe'>('satellite');

  return (
    <section className="relative min-h-screen w-full py-16 px-4 md:px-8 max-w-7xl mx-auto flex flex-col justify-center">
      
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Globe className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-300 uppercase">
              DIGITAL TWIN GLOBE & MULTI-DOMAIN SURVEILLANCE
            </h2>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-white font-display">
            Multi-Domain Coastal Archipelago & Satellite Surveillance
          </h3>
        </div>

        {/* Satellite Link Badge */}
        <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl glass-panel-ocean border border-cyan-500/30 text-xs font-mono">
          <Satellite className="w-4 h-4 text-cyan-400 animate-pulse" />
          <span className="text-slate-300">ORBITAL CONSTELLATION:</span>
          <span className="font-bold text-cyan-200 bg-cyan-950/80 px-2 py-0.5 rounded-md border border-cyan-500/40">
            SENTINEL-3 / OCEANSAT-3
          </span>
        </div>
      </div>

      {/* Main Grid: 3D Marine Globe in Center, flanked by Multi-Sensor Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        
        {/* CENTER-LEFT: Satellite Coastal / 3D Marine Globe */}
        <div className="lg:col-span-8 flex flex-col">
          <div className="glass-card-ocean p-5 rounded-3xl border border-cyan-500/30 shadow-2xl flex-1 flex flex-col min-h-[460px] md:min-h-[520px]">
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                <span className="text-xs font-bold font-mono text-cyan-200 uppercase">
                  {surveillanceMode === 'satellite'
                    ? 'High-Resolution Satellite Coastal Archipelago (Leaflet)'
                    : 'Indian Ocean Basin 3D Spatial Twin (Drag to Rotate)'}
                </span>
              </div>

              {/* View Switcher Button */}
              <div className="flex items-center gap-1 bg-ocean-900/90 p-0.5 rounded-xl border border-cyan-500/30 text-xs font-mono">
                <button
                  onClick={() => setSurveillanceMode('satellite')}
                  className={`px-2.5 py-1 rounded-lg font-bold transition-all flex items-center gap-1 ${
                    surveillanceMode === 'satellite'
                      ? 'bg-cyan-500 text-ocean-950 shadow-xs'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Satellite className="w-3.5 h-3.5" />
                  <span>Marine Map</span>
                </button>
                <button
                  onClick={() => setSurveillanceMode('globe')}
                  className={`px-2.5 py-1 rounded-lg font-bold transition-all flex items-center gap-1 ${
                    surveillanceMode === 'globe'
                      ? 'bg-cyan-500 text-ocean-950 shadow-xs'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" />
                  <span>3D Globe</span>
                </button>
              </div>
            </div>

            {/* Viewport Surface */}
            <div className="flex-1 relative rounded-xl overflow-hidden mt-3 border border-cyan-500/30">
              {surveillanceMode === 'satellite' ? (
                <NereusMarineMap className="w-full h-full min-h-[420px]" />
              ) : (
                <MarineGlobe />
              )}
            </div>

            {/* Orbiting Satellite Ground Stations */}
            <div className="mt-3 pt-3 border-t border-cyan-500/20 grid grid-cols-3 gap-2 text-center text-xs font-mono">
              <div className="p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-slate-400 block text-[10px]">INCOIS Hyderabad</span>
                <span className="font-bold text-cyan-200 text-[11px]">Relay 12.4 Gb/s</span>
              </div>
              <div className="p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-slate-400 block text-[10px]">Oceansat-3 Scatterometer</span>
                <span className="font-bold text-cyan-200 text-[11px]">Swath 1420 km</span>
              </div>
              <div className="p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20">
                <span className="text-slate-400 block text-[10px]">IMD Met Radar Goa</span>
                <span className="font-bold text-emerald-300 text-[11px]">Doppler Synced</span>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: Multi-Domain Sensor Matrix Feeds (Drone FLIR, Sub Multibeam, Radar) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="glass-card-ocean p-5 rounded-3xl border border-cyan-500/30 shadow-2xl flex-1 flex flex-col">
            
            <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
              <span className="text-xs font-bold font-mono tracking-wider text-cyan-200 uppercase">
                Surveillance Matrix
              </span>
              <span className="text-[10px] font-mono text-emerald-300 bg-emerald-950/80 px-2 py-0.5 rounded-md font-semibold border border-emerald-500/40">
                3 FEEDS ONLINE
              </span>
            </div>

            {/* Feed Selector Tabs */}
            <div className="grid grid-cols-3 gap-1 my-3 p-1 rounded-xl bg-ocean-900/90 border border-cyan-500/30 text-xs font-mono">
              <button
                onClick={() => setActiveFeed('drone')}
                className={`py-1.5 rounded-lg font-semibold transition-all ${
                  activeFeed === 'drone'
                    ? 'bg-cyan-500 text-ocean-950 shadow-sm font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Aerial Drone
              </button>
              <button
                onClick={() => setActiveFeed('auv')}
                className={`py-1.5 rounded-lg font-semibold transition-all ${
                  activeFeed === 'auv'
                    ? 'bg-cyan-500 text-ocean-950 shadow-sm font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Sub AUV
              </button>
              <button
                onClick={() => setActiveFeed('radar')}
                className={`py-1.5 rounded-lg font-semibold transition-all ${
                  activeFeed === 'radar'
                    ? 'bg-cyan-500 text-ocean-950 shadow-sm font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Coastal Radar
              </button>
            </div>

            {/* Active Feed Window */}
            <div className="relative flex-1 rounded-xl overflow-hidden min-h-[220px] border border-cyan-500/30 shadow-inner group">
              {activeFeed === 'drone' && (
                <img
                  src={heroDroneImg}
                  alt="Aerial Drone Video Feed"
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
              )}
              {activeFeed === 'auv' && (
                <img
                  src={underwaterSubImg}
                  alt="AUV Submersible Video Feed"
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
              )}
              {activeFeed === 'radar' && (
                <div className="w-full h-full bg-ocean-950 flex items-center justify-center p-4">
                  <div className="relative w-36 h-36 rounded-full border border-cyan-500/40 flex items-center justify-center">
                    <div className="absolute inset-0 rounded-full animate-radar-sweep bg-[conic-gradient(from_0deg,transparent_0_300deg,rgba(6,182,212,0.4)_360deg)]" />
                    <span className="text-cyan-400 font-mono text-xs">SWEEP 360°</span>
                  </div>
                </div>
              )}

              {/* Feed Status Overlay */}
              <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-ocean-950/80 backdrop-blur-md text-white font-mono text-[10px] border border-cyan-500/30">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
                <span>REC LIVE</span>
              </div>
              <div className="absolute bottom-2.5 right-2.5 px-2 py-0.5 rounded-md bg-ocean-950/80 backdrop-blur-md text-cyan-300 font-mono text-[10px] border border-cyan-500/30">
                FPS: 60 • 4K HDR
              </div>
            </div>

            {/* Vessel Threat & Activity Scan Log */}
            <div className="mt-3 pt-3 border-t border-cyan-500/20 space-y-1.5 text-xs font-mono">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Target Detection Log
              </span>
              <div className="p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20 flex justify-between items-center">
                <span className="text-slate-300">IND-4190012 (Artisanal)</span>
                <span className="text-emerald-400 font-bold">PERMITTED</span>
              </div>
              <div className="p-2 rounded-lg bg-ocean-900/60 border border-cyan-500/20 flex justify-between items-center">
                <span className="text-slate-300">UNIDENTIFIED-TRAWLER-9</span>
                <span className="text-amber-400 font-bold">MONITORING</span>
              </div>
            </div>

          </div>
        </div>

      </div>

    </section>
  );
};
