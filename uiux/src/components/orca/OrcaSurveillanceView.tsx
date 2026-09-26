import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Video,
  Crosshair,
  Compass,
  Battery,
  Shield,
  Eye,
  Maximize2,
  Navigation,
} from 'lucide-react';

const ASSET_AERIAL = '/src/assets/images/orca_aerial_drone_1790253431565.jpg';
const ASSET_AUV = '/src/assets/images/orca_underwater_auv_1790253447145.jpg';

export const OrcaSurveillanceView: React.FC = () => {
  const { marineData } = useOrcaStore();
  const [activeFeed, setActiveFeed] = useState<'drone' | 'auv'>('drone');

  return (
    <div className="w-full h-full flex flex-col p-6 space-y-4 overflow-y-auto">
      {/* Top Bar */}
      <div className="flex items-center justify-between glass-panel p-4 rounded-2xl border border-cyan-500/20">
        <div>
          <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block">
            AUTONOMOUS SURVEILLANCE & RECONNAISSANCE FLEET
          </span>
          <h2 className="text-xl font-display font-bold text-white mt-0.5">
            Active Multi-Domain Sensory Feed
          </h2>
        </div>

        {/* Feed Switcher */}
        <div className="flex items-center gap-2 bg-slate-950/80 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveFeed('drone')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors flex items-center gap-2 ${
              activeFeed === 'drone'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            ORCA-AERO-01 (Air)
          </button>
          <button
            onClick={() => setActiveFeed('auv')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors flex items-center gap-2 ${
              activeFeed === 'auv'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            ORCA-SUB-04 (Underwater)
          </button>
        </div>
      </div>

      {/* Main Viewport Card */}
      <div className="relative flex-1 min-h-[420px] rounded-2xl overflow-hidden border border-cyan-500/30 glass-panel-active shadow-2xl">
        {/* Background Image / Video Feed Simulation */}
        <img
          src={activeFeed === 'drone' ? ASSET_AERIAL : ASSET_AUV}
          alt={activeFeed === 'drone' ? 'Aerial Drone Camera' : 'Underwater AUV Feed'}
          referrerPolicy="no-referrer"
          className="absolute inset-0 w-full h-full object-cover filter brightness-90 contrast-110"
        />

        {/* Dark Vignette Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-transparent to-slate-950/60 pointer-events-none" />

        {/* High-Tech Tactical HUD Overlay */}
        <div className="absolute inset-0 p-6 flex flex-col justify-between pointer-events-none z-10 font-mono">
          {/* Top telemetry bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-950/80 border border-white/20 text-xs text-cyan-300">
                <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                LIVE OPTICAL / SONAR STREAM
              </span>
              <span className="text-xs text-slate-300 bg-slate-950/80 px-2 py-1 rounded border border-slate-800">
                FPS: 60.0 · LATENCY: 24ms
              </span>
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-300 bg-slate-950/80 px-3 py-1 rounded-lg border border-slate-800">
              <Battery className="w-3.5 h-3.5 text-emerald-400" />
              <span>{activeFeed === 'drone' ? '87% BATTERY' : '94% FUEL CELL'}</span>
            </div>
          </div>

          {/* Central Target Crosshair */}
          <div className="relative mx-auto my-auto w-48 h-48 border border-cyan-400/30 rounded-full flex items-center justify-center pointer-events-none">
            <div className="w-24 h-24 border border-cyan-400/60 border-dashed rounded-full animate-radar-sweep" />
            <div className="w-3 h-3 bg-cyan-400/40 rounded-full" />
            {/* Crosshair ticks */}
            <div className="absolute top-0 bottom-0 left-1/2 w-[1px] bg-cyan-400/30" />
            <div className="absolute left-0 right-0 top-1/2 h-[1px] bg-cyan-400/30" />
            <span className="absolute -bottom-6 text-[10px] text-cyan-300 bg-slate-950/70 px-2 py-0.5 rounded">
              TARGET LOCK: THERMAL FRONT
            </span>
          </div>

          {/* Bottom telemetry indicators */}
          <div className="flex items-center justify-between text-xs bg-slate-950/80 p-3 rounded-xl border border-slate-800 backdrop-blur-md">
            <div>
              <span className="text-slate-400 text-[10px] block">POSITION REF</span>
              <span className="text-white font-bold">
                {activeFeed === 'drone'
                  ? `${marineData.surveillance.aerialDrone.coordinates[0]}° N, ${marineData.surveillance.aerialDrone.coordinates[1]}° E`
                  : `${marineData.surveillance.underwaterAuv.coordinates[0]}° N, ${marineData.surveillance.underwaterAuv.coordinates[1]}° E`}
              </span>
            </div>

            <div>
              <span className="text-slate-400 text-[10px] block">ALTITUDE / DEPTH</span>
              <span className="text-cyan-300 font-bold">
                {activeFeed === 'drone'
                  ? `${marineData.surveillance.aerialDrone.altitudeMeters}m MSL`
                  : `${marineData.surveillance.underwaterAuv.depthMeters}m BSF`}
              </span>
            </div>

            <div>
              <span className="text-slate-400 text-[10px] block">CRUISING SPEED</span>
              <span className="text-emerald-300 font-bold">
                {activeFeed === 'drone'
                  ? `${marineData.surveillance.aerialDrone.speedKnots} KNOTS`
                  : '8.4 KNOTS'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
