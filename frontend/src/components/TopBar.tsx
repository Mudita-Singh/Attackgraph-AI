import React, { useState } from 'react';
import type { Scan } from '../types';
import { createScan } from '../api/client';
import { 
  Copy, 
  Check, 
  Play, 
  ChevronDown,
  Loader2,
  Plus,
  X,
  Globe
} from 'lucide-react';

interface TopBarProps {
  scans: Scan[];
  selectedScanId: string;
  onSelectScan: (scanId: string) => void;
  onRunAgent: () => void;
  isRunningAgent: boolean;
  onOpenCalibration?: () => void;
  onScanCreated?: (newScan: Scan) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  scans,
  selectedScanId,
  onSelectScan,
  onRunAgent,
  isRunningAgent,
  onScanCreated,
}) => {
  const [copiedField, setCopiedField] = useState<'id' | 'url' | null>(null);
  const [showNewScanModal, setShowNewScanModal] = useState(false);
  const [newTargetUrl, setNewTargetUrl] = useState('http://localhost:3000');
  const [creatingScan, setCreatingScan] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  const currentScan = scans.find((s) => s.id === selectedScanId);

  const copyToClipboard = (text: string, field: 'id' | 'url') => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 1500);
  };

  const handleCreateScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTargetUrl.trim()) return;

    setCreatingScan(true);
    setScanError(null);
    try {
      const scan = await createScan(newTargetUrl.trim());
      setCreatingScan(false);
      setShowNewScanModal(false);
      if (onScanCreated) {
        onScanCreated(scan);
      }
    } catch (err: any) {
      setCreatingScan(false);
      setScanError(err.message || 'Failed to create scan. Ensure target URL is in allowlist.');
    }
  };

  const targetUrl = currentScan?.target_url || 'http://localhost:3000';
  const status = currentScan?.status || 'UNKNOWN';

  const getStatusBadge = (st: string) => {
    const isCompleted = st.toUpperCase().includes('COMPLETED');
    const isRunning = st.toUpperCase().includes('RUNNING') || isRunningAgent;

    if (isRunning) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
          Running
        </span>
      );
    }

    if (isCompleted) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          Completed
        </span>
      );
    }

    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/15 text-slate-300 border border-slate-500/30">
        <span className="w-2 h-2 rounded-full bg-slate-400" />
        {st}
      </span>
    );
  };

  return (
    <header className="h-14 bg-[#0B0D1A] border-b border-[#ffffff14] px-6 flex items-center justify-between gap-4 select-none shrink-0 z-20 relative">
      {/* Left: Scan & Target info cards */}
      <div className="flex items-center gap-3">
        {/* Scan Selector & ID Pill */}
        <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl px-3 py-1 flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">SCAN</span>
          <div className="relative flex items-center">
            <select
              value={selectedScanId}
              onChange={(e) => onSelectScan(e.target.value)}
              className="bg-transparent text-xs font-mono font-semibold text-slate-100 pr-5 focus:outline-none cursor-pointer appearance-none"
            >
              {scans.map((scan) => (
                <option key={scan.id} value={scan.id} className="bg-[#12152A] text-slate-200">
                  #{scan.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-0 pointer-events-none" />
          </div>

          <button
            onClick={() => copyToClipboard(selectedScanId, 'id')}
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800/50 transition-colors cursor-pointer ml-1"
            title="Copy Scan ID"
          >
            {copiedField === 'id' ? (
              <Check className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        {/* Target URL Pill */}
        <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl px-3 py-1 flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">TARGET</span>
          <span className="text-xs font-mono text-indigo-300 font-medium truncate max-w-[200px]">
            {targetUrl}
          </span>
          <button
            onClick={() => copyToClipboard(targetUrl, 'url')}
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800/50 transition-colors cursor-pointer"
            title="Copy Target URL"
          >
            {copiedField === 'url' ? (
              <Check className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        {/* Read-only Status Badge */}
        <div className="bg-[#12152A] border border-[#ffffff14] rounded-xl px-3 py-1 flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">STATUS</span>
          {getStatusBadge(status)}
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* New Scan Button */}
        <button
          onClick={() => setShowNewScanModal(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-[#12152A] text-slate-300 border border-[#ffffff14] hover:bg-slate-800/50 hover:text-slate-100 transition-colors cursor-pointer"
          title="Create a new scan against a target URL"
        >
          <Plus className="w-4 h-4 text-indigo-400" />
          <span>New Scan</span>
        </button>

        {/* Run Agent Button */}
        <button
          onClick={onRunAgent}
          disabled={isRunningAgent || !selectedScanId}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-xl text-xs font-semibold shadow-lg transition-all cursor-pointer ${
            isRunningAgent || !selectedScanId
              ? 'bg-[#6366F1]/50 text-slate-300 cursor-not-allowed'
              : 'bg-[#6366F1] hover:bg-[#4F46E5] text-white shadow-indigo-500/20 active:scale-[0.98]'
          }`}
        >
          {isRunningAgent ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-white" />
              <span>Agent running...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Run Agent</span>
            </>
          )}
        </button>
      </div>

      {/* New Scan Popover / Modal */}
      {showNewScanModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#12152A] border border-[#ffffff14] rounded-2xl p-6 w-full max-w-md space-y-4 shadow-2xl animate-in fade-in zoom-in duration-150">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Globe className="w-5 h-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-slate-100">Create New Scan</h3>
              </div>
              <button
                onClick={() => setShowNewScanModal(false)}
                className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800/50 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateScan} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-mono text-slate-400 block">
                  Target URL (must be in target allowlist)
                </label>
                <input
                  type="url"
                  required
                  value={newTargetUrl}
                  onChange={(e) => setNewTargetUrl(e.target.value)}
                  placeholder="http://localhost:3000"
                  className="w-full bg-[#0B0D1A] border border-[#ffffff14] text-xs font-mono text-slate-100 rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#6366F1]"
                />
              </div>

              {scanError && (
                <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs font-mono">
                  {scanError}
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewScanModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium bg-[#0B0D1A] text-slate-400 hover:text-slate-200 border border-[#ffffff14] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingScan}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#6366F1] hover:bg-[#4F46E5] text-white shadow-lg cursor-pointer disabled:opacity-50 flex items-center gap-2"
                >
                  {creatingScan ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create Scan</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </header>
  );
};
