import React, { useState } from 'react';
import type { GraphData } from '../types';
import { 
  Share2, 
  GitCommit, 
  CheckCircle2, 
  ShieldAlert, 
  Crown,
  Key, 
  AlertTriangle, 
  HelpCircle,
  Gauge
} from 'lucide-react';

interface StatCardsProps {
  graphData: GraphData | null;
}

export const StatCards: React.FC<StatCardsProps> = ({ graphData }) => {
  const [showTooltip, setShowTooltip] = useState(false);

  const nodes = graphData?.nodes || [];
  const edges = graphData?.edges || [];

  const nodeCount = nodes.length;
  const edgeCount = edges.length;

  const verifiedEdges = edges.filter((e) => e.status === 'verified').length;
  const verifiedPct = edgeCount > 0 ? Math.round((verifiedEdges / edgeCount) * 100) : 0;

  const findingTypes = ['access_control_finding', 'reflected_input_finding', 'vulnerability'];
  const findings = nodes.filter((n) => findingTypes.includes(n.node_type));
  const findingCount = findings.length;

  const firstCriticalNode = nodes.find((n) => n.is_critical);
  const criticalLabel = firstCriticalNode ? firstCriticalNode.label : 'None';

  const secretCount = nodes.filter((n) => n.node_type === 'potential_secret').length;
  const underminedCount = nodes.filter((n) => n.undermined).length;

  // Compute average edge confidence (excluding refuted, human_invalidated, and has_endpoint edges)
  const validConfidences = edges
    .filter((e) => e.status !== 'refuted' && e.status !== 'human_invalidated' && e.relation_type !== 'has_endpoint')
    .map((e) => e.confidence)
    .filter((c): c is number => c !== undefined && c !== null);

  const avgConfidence = validConfidences.length > 0
    ? Math.round((validConfidences.reduce((a, b) => a + b, 0) / validConfidences.length) * 100)
    : null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 px-3 py-2 bg-[#0B0D1A] border-b border-[#ffffff14] shrink-0 font-sans">
      {/* 1. Nodes */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px]">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Nodes</span>
          <Share2 className="w-3.5 h-3.5 text-indigo-400" />
        </div>
        <div className="text-[20px] font-semibold font-mono text-slate-100 leading-none">
          {nodeCount}
        </div>
      </div>

      {/* 2. Edges */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px]">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Edges</span>
          <GitCommit className="w-3.5 h-3.5 text-cyan-400" />
        </div>
        <div className="text-[20px] font-semibold font-mono text-slate-100 leading-none">
          {edgeCount}
        </div>
      </div>

      {/* 3. Verified Edges */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px]">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Verified</span>
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <div className="flex items-baseline gap-1 leading-none">
          <span className="text-[20px] font-semibold font-mono text-slate-100">{verifiedEdges}</span>
          <span className="text-[11px] font-mono text-emerald-400">({verifiedPct}%)</span>
        </div>
      </div>

      {/* 4. Findings */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px]">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Findings</span>
          <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
        </div>
        <div className="text-[20px] font-semibold font-mono text-slate-100 leading-none">
          {findingCount}
        </div>
      </div>

      {/* 5. Critical Bottleneck */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px]">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Critical bottleneck</span>
          <Crown className="w-3.5 h-3.5 text-rose-500" />
        </div>
        <div 
          className="text-xs font-semibold text-rose-400 truncate leading-none"
          title={criticalLabel}
        >
          {criticalLabel}
        </div>
      </div>

      {/* 6. Secrets */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px]">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Secrets</span>
          <Key className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <div className="text-[20px] font-semibold font-mono text-slate-100 leading-none">
          {secretCount}
        </div>
      </div>

      {/* 7. Undermined */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px]">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span>Undermined</span>
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
        </div>
        <div className="text-[20px] font-semibold font-mono text-slate-100 leading-none">
          {underminedCount}
        </div>
      </div>

      {/* 8. Avg Confidence */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl p-2.5 flex flex-col justify-between h-[64px] relative">
        <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
          <span className="flex items-center gap-1">
            Avg Confidence
            <button
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              className="text-slate-500 hover:text-slate-300 cursor-help"
            >
              <HelpCircle className="w-3 h-3" />
            </button>
          </span>
          <Gauge className="w-3.5 h-3.5 text-indigo-400" />
        </div>

        {showTooltip && (
          <div className="absolute top-10 left-3 right-3 bg-[#1A1D3B] text-slate-200 text-[11px] p-2 rounded-lg border border-[#ffffff1c] shadow-xl z-30 font-sans">
            Stated confidence, not calibrated accuracy
          </div>
        )}

        <div className="text-[20px] font-semibold font-mono text-slate-100 leading-none">
          {avgConfidence !== null ? `${avgConfidence}%` : '-'}
        </div>
      </div>
    </div>
  );
};
