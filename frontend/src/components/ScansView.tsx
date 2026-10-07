import React, { useState } from 'react';
import type { Scan, GraphData } from '../types';
import { 
  FolderKanban, 
  Terminal, 
  Copy, 
  Check, 
  ArrowRight,
  Clock,
  Share2,
  GitCommit
} from 'lucide-react';

interface ScansViewProps {
  scans: Scan[];
  selectedScanId: string;
  onSelectScan: (scanId: string) => void;
  onNavigateToGraph: () => void;
  graphData: GraphData | null;
}

export const ScansView: React.FC<ScansViewProps> = ({
  scans,
  selectedScanId,
  onSelectScan,
  onNavigateToGraph,
  graphData,
}) => {
  const [copiedScanId, setCopiedScanId] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedScanId(id);
    setTimeout(() => setCopiedScanId(null), 1500);
  };

  const getStatusBadge = (st: string) => {
    const isCompleted = st.toUpperCase().includes('COMPLETED');
    const isRunning = st.toUpperCase().includes('RUNNING');

    if (isRunning) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
          Running
        </span>
      );
    }

    if (isCompleted) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          Completed
        </span>
      );
    }

    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-slate-500/15 text-slate-300 border border-slate-500/30">
        {st}
      </span>
    );
  };

  if (scans.length === 0) {
    return (
      <div className="flex-1 bg-[#0B0D1A] flex flex-col items-center justify-center text-slate-400 gap-3 p-12 select-none">
        <FolderKanban className="w-12 h-12 text-indigo-400/40 stroke-[1.5]" />
        <span className="text-sm font-mono">No scans available.</span>
      </div>
    );
  }

  return (
    <div className="flex-1 bg-[#0B0D1A] flex flex-col overflow-y-auto p-6 space-y-6 select-none font-sans text-slate-200">
      {/* Header */}
      <div className="bg-[#12152A] border border-[#ffffff14] rounded-2xl p-5 space-y-2 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#6366F1]/15 border border-[#6366F1]/40 flex items-center justify-center text-[#6366F1]">
            <FolderKanban className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              Scan Management ({scans.length})
            </h2>
            <p className="text-xs text-slate-400 font-sans">
              Select a target scan to load its graph topology, findings, and replay history
            </p>
          </div>
        </div>
      </div>

      {/* Scans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {scans.map((scan) => {
          const isSelected = scan.id === selectedScanId;
          const isCurrentScanGraph = isSelected && graphData?.scan_id === scan.id;

          return (
            <div
              key={scan.id}
              onClick={() => {
                onSelectScan(scan.id);
                onNavigateToGraph();
              }}
              className={`bg-[#12152A] border rounded-2xl p-5 space-y-4 transition-all cursor-pointer shadow-xl relative group ${
                isSelected
                  ? 'border-[#6366F1] ring-2 ring-[#6366F1]/40 bg-[#161933]'
                  : 'border-[#ffffff14] hover:border-slate-400/50'
              }`}
            >
              {/* Scan Card Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-indigo-300">
                    #{scan.id.slice(0, 8)}
                  </span>
                  <button
                    onClick={(e) => copyToClipboard(scan.id, scan.id, e)}
                    className="text-slate-500 hover:text-slate-200 p-1 rounded cursor-pointer"
                    title="Copy full Scan ID"
                  >
                    {copiedScanId === scan.id ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                {getStatusBadge(scan.status)}
              </div>

              {/* Target URL */}
              <div className="space-y-1">
                <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1">
                  <Terminal className="w-3 h-3 text-amber-400" /> Target URL
                </span>
                <p className="text-sm font-mono font-bold text-slate-100 truncate">
                  {scan.target_url}
                </p>
              </div>

              {/* Counts & Metadata Footer */}
              <div className="pt-3 border-t border-[#ffffff0a] flex items-center justify-between text-xs">
                <div className="flex items-center gap-3 font-mono text-slate-400">
                  <span className="flex items-center gap-1 text-slate-300">
                    <Share2 className="w-3.5 h-3.5 text-indigo-400" />
                    {isCurrentScanGraph ? graphData?.nodes.length : '-'} nodes
                  </span>
                  <span className="flex items-center gap-1 text-slate-300">
                    <GitCommit className="w-3.5 h-3.5 text-cyan-400" />
                    {isCurrentScanGraph ? graphData?.edges.length : '-'} edges
                  </span>
                </div>

                <span className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(scan.created_at).toLocaleDateString()}
                </span>
              </div>

              {/* Hover Action Indicator */}
              <div className="flex items-center justify-end gap-1 text-xs font-mono font-semibold text-indigo-400 group-hover:text-indigo-300 pt-1">
                <span>View Graph</span>
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
