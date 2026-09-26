import React from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { ShieldCheck, Check, AlertOctagon, RefreshCw, CheckCircle2 } from 'lucide-react';

export const OrcaVerification: React.FC = () => {
  const { verification, isRunning, agentStatus } = useOrcaStore();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'VERIFIED':
        return 'text-emerald-400 border-emerald-500/50 bg-emerald-500/10';
      case 'PARTIALLY_VERIFIED':
        return 'text-amber-400 border-amber-500/50 bg-amber-500/10';
      case 'CONFLICT_DETECTED':
        return 'text-rose-400 border-rose-500/50 bg-rose-500/10';
      default:
        return 'text-cyan-400 border-cyan-500/50 bg-cyan-500/10';
    }
  };

  return (
    <div className="flex flex-col h-full glass-panel rounded-2xl p-4 border border-cyan-500/20 shadow-xl overflow-hidden backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-cyan-500/15">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <h2 className="text-xs font-bold font-mono tracking-wider text-white uppercase">
            CROSS-AGENT VERIFICATION GATE
          </h2>
        </div>
        <span className="text-[10px] font-mono text-cyan-300">SAFETY ARBITRATION</span>
      </div>

      <div className="flex-1 overflow-y-auto mt-4 space-y-4 pr-1">
        {/* Verification Ring Graphic */}
        <div className="flex flex-col items-center justify-center p-6 bg-slate-900/60 rounded-2xl border border-cyan-500/20 relative">
          <div className="relative w-36 h-36 flex items-center justify-center">
            {/* SVG Circular Validation Ring */}
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="42"
                stroke="#1e293b"
                strokeWidth="6"
                fill="none"
              />
              <circle
                cx="50"
                cy="50"
                r="42"
                stroke={verification?.status === 'VERIFIED' ? '#10b981' : '#06b6d4'}
                strokeWidth="6"
                strokeDasharray="264"
                strokeDashoffset={
                  verification
                    ? 264 - (264 * verification.confidenceScore) / 100
                    : isRunning
                    ? 100
                    : 264
                }
                strokeLinecap="round"
                fill="none"
                className="transition-all duration-1000 ease-out"
              />
            </svg>

            {/* Inner Content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              {isRunning ? (
                <>
                  <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin mb-1" />
                  <span className="text-[10px] font-mono text-cyan-300 uppercase">Validating</span>
                </>
              ) : verification ? (
                <>
                  <span className="text-3xl font-display font-extrabold text-white tracking-tight tabular-nums">
                    {verification.confidenceScore}%
                  </span>
                  <span className="text-[9px] font-mono text-slate-400 uppercase mt-0.5">
                    Consensus
                  </span>
                </>
              ) : (
                <>
                  <span className="text-xs font-mono text-slate-400">GATE STANDBY</span>
                </>
              )}
            </div>
          </div>

          {/* Status Label */}
          <div className="mt-3">
            <span
              className={`px-3 py-1 rounded-full text-xs font-mono font-bold tracking-wider uppercase border ${
                verification ? getStatusColor(verification.status) : 'text-slate-400 border-slate-700 bg-slate-900'
              }`}
            >
              {verification ? verification.status : 'AWAITING VERIFICATION'}
            </span>
          </div>

          {verification?.consistencyNote && (
            <p className="text-xs font-sans text-slate-300 text-center mt-2.5 max-w-sm">
              {verification.consistencyNote}
            </p>
          )}
        </div>

        {/* Validation Rings Breakdown Checklist */}
        <div className="space-y-2">
          <span className="text-[10px] font-mono uppercase text-slate-400">
            Validation Gates & Invariants
          </span>
          {verification?.validationRings && verification.validationRings.length > 0 ? (
            verification.validationRings.map((gate, i) => (
              <div
                key={i}
                className="p-3 rounded-xl bg-slate-900/50 border border-slate-800 flex items-start gap-3"
              >
                <div
                  className={`mt-0.5 p-1 rounded-md ${
                    gate.passed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                  }`}
                >
                  {gate.passed ? <Check className="w-3.5 h-3.5" /> : <AlertOctagon className="w-3.5 h-3.5" />}
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-white">{gate.name}</h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">{gate.detail}</p>
                </div>
              </div>
            ))
          ) : (
            <div className="p-3 rounded-xl border border-slate-800 text-xs text-slate-500 font-mono text-center">
              Active verification gates will execute automatically on model completion.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
