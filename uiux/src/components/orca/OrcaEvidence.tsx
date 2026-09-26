import React from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  ShieldCheck,
  MapPin,
  Clock,
  Database,
  ExternalLink,
  CheckCircle,
  AlertTriangle,
  FileText,
} from 'lucide-react';

export const OrcaEvidence: React.FC = () => {
  const { evidence, isRunning, activeTool } = useOrcaStore();

  return (
    <div className="flex flex-col h-full glass-panel rounded-2xl p-4 border border-cyan-500/20 shadow-xl overflow-hidden backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-cyan-500/15">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-cyan-400" />
          <h2 className="text-xs font-bold font-mono tracking-wider text-white uppercase">
            EMPIRICAL EVIDENCE CORROBORATION
          </h2>
        </div>
        <span className="text-[10px] font-mono text-cyan-300">
          {evidence.length} SOURCES HARVESTED
        </span>
      </div>

      <div className="flex-1 overflow-y-auto mt-3 space-y-3 pr-1">
        {evidence.length === 0 ? (
          <div className="h-48 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-800 rounded-xl">
            <FileText className="w-8 h-8 text-slate-600 mb-2" />
            <p className="text-xs font-mono text-slate-400">
              {isRunning
                ? 'Harvesting authoritative marine observations...'
                : 'No evidence records in active run. Initiate a query to inspect live INCOIS/NOAA telemetry citations.'}
            </p>
          </div>
        ) : (
          evidence.map((item) => (
            <div
              key={item.id}
              className="p-3.5 rounded-xl bg-slate-900/60 border border-cyan-500/20 text-xs space-y-2 hover:border-cyan-400/40 transition-colors"
            >
              {/* Top row */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 font-semibold border border-cyan-500/30">
                  {item.sourceType}
                </span>
                <div className="flex items-center gap-1.5 text-emerald-400 font-mono text-[11px]">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>{(item.confidence * 100).toFixed(0)}% Confidence</span>
                </div>
              </div>

              {/* Title */}
              <h3 className="text-sm font-semibold text-white">{item.title}</h3>

              {/* Content description */}
              <p className="text-xs text-slate-300 leading-relaxed font-sans">
                {item.content}
              </p>

              {/* Metadata row */}
              <div className="pt-2 border-t border-slate-800/80 grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400">
                <div className="flex items-center gap-1.5 truncate">
                  <Database className="w-3 h-3 text-cyan-400 shrink-0" />
                  <span className="truncate">{item.source}</span>
                </div>
                {item.coordinates && (
                  <div className="flex items-center gap-1.5">
                    <MapPin className="w-3 h-3 text-emerald-400 shrink-0" />
                    <span>
                      {item.coordinates.lat}°N, {item.coordinates.lng}°E
                    </span>
                  </div>
                )}
              </div>

              {/* Provenance Tag */}
              <div className="text-[9px] font-mono text-slate-500">
                Provenance Agent: <span className="text-slate-400">{item.provenance.agentId}</span> via{' '}
                <span className="text-cyan-400">{item.provenance.tool}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
