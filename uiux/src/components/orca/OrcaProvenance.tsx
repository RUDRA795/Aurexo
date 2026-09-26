import React from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { GitCommit, ArrowRight, Database, Bot, Cpu, CheckCircle2, User } from 'lucide-react';

export const OrcaProvenance: React.FC = () => {
  const { provenance } = useOrcaStore();

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'query':
        return <User className="w-4 h-4 text-cyan-400" />;
      case 'agent':
        return <Bot className="w-4 h-4 text-purple-400" />;
      case 'tool':
        return <Cpu className="w-4 h-4 text-blue-400" />;
      case 'source':
        return <Database className="w-4 h-4 text-emerald-400" />;
      default:
        return <CheckCircle2 className="w-4 h-4 text-slate-300" />;
    }
  };

  return (
    <div className="flex flex-col h-full glass-panel rounded-2xl p-4 border border-cyan-500/20 shadow-xl overflow-hidden backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-cyan-500/15">
        <div className="flex items-center gap-2">
          <GitCommit className="w-4 h-4 text-cyan-400" />
          <h2 className="text-xs font-bold font-mono tracking-wider text-white uppercase">
            REASONING PROVENANCE & DATA LINEAGE
          </h2>
        </div>
        <span className="text-[10px] font-mono text-cyan-300">GRAPH LINEAGE</span>
      </div>

      <div className="flex-1 overflow-y-auto mt-4 space-y-3 pr-1">
        <p className="text-xs text-slate-400 font-sans">
          Deterministic execution trace verifying zero hallucination: each conclusion directly links to its triggering agent, executed tool, and raw source observation.
        </p>

        {/* Provenance Sequence Chain */}
        <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-cyan-500/20">
          {provenance.nodes.map((node, i) => (
            <div key={node.id} className="relative group">
              {/* Node indicator */}
              <div className="absolute -left-6 top-1.5 w-5 h-5 rounded-full bg-slate-900 border border-cyan-400 flex items-center justify-center">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              </div>

              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/40 transition-colors">
                <div className="flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2">
                    {getNodeIcon(node.type)}
                    <span className="font-bold text-white uppercase">{node.label}</span>
                  </div>
                  <span className="text-[10px] text-cyan-400 px-1.5 py-0.5 rounded bg-cyan-500/10 uppercase">
                    {node.type}
                  </span>
                </div>

                {node.meta && (
                  <div className="mt-2 text-[11px] font-mono text-slate-400 bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
                    <pre className="overflow-x-auto">{JSON.stringify(node.meta, null, 2)}</pre>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
