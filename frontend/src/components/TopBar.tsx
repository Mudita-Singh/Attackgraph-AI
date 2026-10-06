import React from 'react';
import type { Scan } from '../types';
import { Shield, Eye, EyeOff, Terminal, Activity, History, BarChart3 } from 'lucide-react';

interface TopBarProps {
  scans: Scan[];
  selectedScanId: string;
  onSelectScan: (scanId: string) => void;
  showRefuted: boolean;
  onToggleShowRefuted: () => void;
  hiddenEdgeCount: number;
  criticalCount: number;
  isReplayMode: boolean;
  onToggleReplayMode: () => void;
  onOpenCalibration: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  scans,
  selectedScanId,
  onSelectScan,
  showRefuted,
  onToggleShowRefuted,
  hiddenEdgeCount,
  criticalCount,
  isReplayMode,
  onToggleReplayMode,
  onOpenCalibration,
}) => {
  const currentScan = scans.find((s) => s.id === selectedScanId);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
      case 'AGENT_LOOP_COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold bg-[#00E676]/10 text-[#00E676] border border-[#00E676]/30">
            <Activity className="w-3 h-3" />
            {status}
          </span>
        );
      case 'RUNNING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold bg-[#FFAA00]/10 text-[#FFAA00] border border-[#FFAA00]/30 animate-pulse">
            <Activity className="w-3 h-3 animate-spin" />
            RUNNING
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold bg-[#8a94a6]/10 text-[#8a94a6] border border-[#8a94a6]/30">
            {status}
          </span>
        );
    }
  };

  return (
    <header className="h-14 bg-[#10141d] border-b border-[#262c38] px-4 flex items-center justify-between gap-4 select-none shrink-0 z-20">
      {/* Brand & Logo */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-[#FF3B3B]/10 border border-[#FF3B3B]/30 flex items-center justify-center text-[#FF3B3B]">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-wider text-[#e6e6e6] uppercase flex items-center gap-2">
            ATTACKGRAPH <span className="text-[#FF3B3B] text-xs font-mono font-normal">AI SOC v0.1</span>
          </h1>
        </div>
      </div>

      {/* Center Scan Selector & Target Info */}
      <div className="flex items-center gap-4 bg-[#0a0e14] px-3 py-1.5 rounded border border-[#262c38]">
        <label className="text-xs text-[#8a94a6] font-medium flex items-center gap-1.5 shrink-0">
          <Terminal className="w-3.5 h-3.5 text-[#FFAA00]" />
          Scan:
        </label>
        <select
          value={selectedScanId}
          onChange={(e) => onSelectScan(e.target.value)}
          className="bg-[#10141d] text-[#e6e6e6] text-xs font-mono border border-[#333c4a] rounded px-2.5 py-1 focus:outline-none focus:border-[#FFAA00] cursor-pointer"
        >
          {scans.map((scan) => (
            <option key={scan.id} value={scan.id}>
              {scan.target_url} ({scan.id.slice(0, 8)})
            </option>
          ))}
        </select>

        {currentScan && (
          <div className="flex items-center gap-3 border-l border-[#262c38] pl-3">
            <div className="text-xs font-mono text-[#8a94a6] truncate max-w-[220px]">
              <span className="text-[#6b7280]">Target:</span>{' '}
              <span className="text-[#e6e6e6]">{currentScan.target_url}</span>
            </div>
            {getStatusBadge(currentScan.status)}
          </div>
        )}
      </div>

      {/* Controls & Badges */}
      <div className="flex items-center gap-4">
        {criticalCount > 0 && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#FF3B3B]/10 border border-[#FF3B3B]/40 text-[#FF3B3B] text-xs font-semibold animate-pulse">
            <span className="w-2 h-2 rounded-full bg-[#FF3B3B]" />
            {criticalCount} CRITICAL BOTTLENECK
          </div>
        )}

        <button
          onClick={onOpenCalibration}
          className="flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium border bg-[#10141d] text-[#FFAA00] border-[#FFAA00]/30 hover:border-[#FFAA00] hover:bg-[#FFAA00]/10 transition-colors cursor-pointer"
          title="Open Offline Calibration Report (Section 11.5)"
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Calibration</span>
        </button>

        <button
          onClick={onToggleReplayMode}
          className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium border transition-colors cursor-pointer ${
            isReplayMode
              ? 'bg-[#E040FB] text-black border-[#E040FB] font-bold shadow-lg shadow-[#E040FB]/20'
              : 'bg-[#10141d] text-[#8a94a6] border-[#262c38] hover:text-[#e6e6e6] hover:border-[#333c4a]'
          }`}
          title="Toggle Replay Mode (playback step-by-step discovery)"
        >
          <History className="w-3.5 h-3.5" />
          <span>{isReplayMode ? 'Exit Replay' : 'Replay Mode'}</span>
        </button>

        <button
          onClick={onToggleShowRefuted}
          className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium border transition-colors cursor-pointer ${
            showRefuted
              ? 'bg-[#E040FB]/15 text-[#E040FB] border-[#E040FB]/40'
              : 'bg-[#10141d] text-[#8a94a6] border-[#262c38] hover:text-[#e6e6e6] hover:border-[#333c4a]'
          }`}
          title="Toggle display of refuted and human-invalidated edges"
        >
          {showRefuted ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
          <span>{showRefuted ? 'Showing Refuted Edges' : 'Show Refuted Edges'}</span>
          {!showRefuted && hiddenEdgeCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-[#4A5568] text-[#e6e6e6] text-[10px] font-mono">
              +{hiddenEdgeCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
};
