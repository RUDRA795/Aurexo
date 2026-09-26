import React from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  CheckCircle2,
  Clock,
  Cpu,
  Layers,
  Search,
  Thermometer,
  Wind,
  ShieldCheck,
  AlertCircle,
  Radio,
  ExternalLink,
} from 'lucide-react';

export const OrcaTimeline: React.FC = () => {
  const { agentStatus, toolCalls, activeTool, isRunning, cancelRun } = useOrcaStore();

  const getToolIcon = (tool: string) => {
    if (tool.includes('pfz')) return <Layers className="w-3.5 h-3.5 text-emerald-400" />;
    if (tool.includes('sst')) return <Thermometer className="w-3.5 h-3.5 text-amber-400" />;
    if (tool.includes('weather')) return <Wind className="w-3.5 h-3.5 text-cyan-400" />;
    if (tool.includes('advisory')) return <Search className="w-3.5 h-3.5 text-purple-400" />;
    return <Cpu className="w-3.5 h-3.5 text-blue-400" />;
  };

  // Operational states for the HUD (as shown in Reference Video 2)
  const hudAgents = [
    { name: 'PFZ REASONER', state: 'PROCESSING', progress: 98, active: agentStatus.includes('pfz') || isRunning },
    { name: 'OCEANOGRAPHY SST', state: 'SEARCHING', progress: 82, active: agentStatus.includes('sst') || isRunning },
    { name: 'MET-OCEAN HAZARD', state: 'VERIFYING', progress: 91, active: agentStatus.includes('weather') || isRunning },
    { name: 'COASTAL CONSENSUS', state: 'VERIFIED', progress: 96, active: agentStatus === 'complete' },
  ];

  return (
    <div className="flex flex-col h-full glass-panel rounded-2xl p-4 border border-cyan-500/20 shadow-xl overflow-hidden backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-cyan-500/15">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
          <h2 className="text-xs font-bold font-mono tracking-wider text-white uppercase">
            AI AGENT HUD
          </h2>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-cyan-400 animate-ping' : 'bg-emerald-400'}`} />
          <span className="text-[10px] font-mono text-cyan-300">
            {isRunning ? 'EXEC ACTIVE' : 'IDLE LISTENING'}
          </span>
        </div>
      </div>

      {/* Collaborative Agents Activity List (matching Video 2) */}
      <div className="mt-3 space-y-2">
        <span className="text-[10px] font-mono uppercase text-slate-400">Collaborative Fleet</span>
        {hudAgents.map((ag, i) => (
          <div
            key={i}
            className={`p-2.5 rounded-xl border transition-all ${
              ag.active
                ? 'bg-cyan-950/40 border-cyan-500/40 shadow-[0_0_12px_rgba(6,182,212,0.1)]'
                : 'bg-slate-900/40 border-slate-800 text-slate-400'
            }`}
          >
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="font-semibold text-slate-200">{ag.name}</span>
              <div className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${ag.active ? 'bg-cyan-400 animate-pulse' : 'bg-slate-600'}`} />
                <span className={ag.active ? 'text-cyan-300' : 'text-slate-500'}>{ag.state}</span>
                <span className="text-slate-400 font-bold">{ag.progress}%</span>
              </div>
            </div>
            {/* Progress bar */}
            <div className="w-full bg-slate-900 h-1 rounded-full mt-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${ag.active ? ag.progress : 20}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Operational Execution Timeline */}
      <div className="mt-4 flex-1 flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono uppercase text-slate-400">Execution Timeline</span>
          {isRunning && (
            <button
              onClick={cancelRun}
              className="text-[10px] font-mono text-rose-400 hover:text-rose-300 underline"
            >
              Abort Run
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {toolCalls.length === 0 ? (
            <div className="p-4 rounded-xl border border-dashed border-slate-800 text-center text-xs text-slate-500 font-mono">
              Awaiting query dispatch from Chat HUD or scenario trigger.
            </div>
          ) : (
            toolCalls.map((tc, idx) => (
              <div
                key={idx}
                className="p-2.5 rounded-xl bg-slate-900/60 border border-cyan-500/20 text-xs space-y-1"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    {getToolIcon(tc.tool)}
                    <span className="font-mono font-semibold text-cyan-200 uppercase">
                      {tc.tool.replace(/_/g, ' ')}
                    </span>
                  </div>
                  {tc.status === 'completed' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Clock className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                  )}
                </div>

                {tc.output && (
                  <div className="bg-slate-950/70 p-2 rounded-lg font-mono text-[11px] text-slate-300 border border-slate-800">
                    <span className="text-slate-500 text-[10px]">Output Summary:</span>
                    <pre className="text-[10px] text-cyan-300 overflow-x-auto whitespace-pre-wrap mt-0.5">
                      {JSON.stringify(tc.output, null, 2).slice(0, 160)}
                    </pre>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
