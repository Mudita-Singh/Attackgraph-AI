import React, { useState, useEffect } from 'react';
import type { Scan, CalibrationReport } from '../types';
import { fetchGlobalCalibration, fetchScanCalibration } from '../api/client';
import { BarChart3, AlertTriangle, RefreshCw } from 'lucide-react';

interface CalibrationViewProps {
  scans: Scan[];
  onClose: () => void;
}

export const CalibrationView: React.FC<CalibrationViewProps> = ({
  scans,
  onClose,
}) => {
  const [scope, setScope] = useState<'global' | string>('global');
  const [report, setReport] = useState<CalibrationReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const promise = scope === 'global'
      ? fetchGlobalCalibration()
      : fetchScanCalibration(scope);

    promise
      .then((data) => {
        setReport(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Calibration fetch error:', err);
        setError(`Failed to load calibration report: ${err.message}`);
        setLoading(false);
      });
  }, [scope]);

  return (
    <div className="fixed inset-0 bg-[#0a0e14]/90 backdrop-blur-md z-50 flex flex-col overflow-hidden select-none">
      {/* Modal Header */}
      <header className="h-14 bg-[#10141d] border-b border-[#262c38] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-[#FFAA00]/10 border border-[#FFAA00]/30 flex items-center justify-center text-[#FFAA00]">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-wider text-[#e6e6e6] uppercase flex items-center gap-2">
              OFFLINE CALIBRATION & EVALUATION <span className="text-[#FFAA00] text-xs font-mono font-normal">Section 11.5</span>
            </h2>
          </div>
        </div>

        {/* Scope Selector */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-[#0a0e14] px-3 py-1.5 rounded border border-[#262c38]">
            <span className="text-xs font-mono text-[#8a94a6]">Scope:</span>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              className="bg-[#10141d] text-[#e6e6e6] text-xs font-mono border border-[#333c4a] rounded px-2.5 py-1 cursor-pointer focus:outline-none focus:border-[#FFAA00]"
            >
              <option value="global">All Scans (Aggregated)</option>
              {scans.map((s) => (
                <option key={s.id} value={s.id}>
                  Scan {s.id.slice(0, 8)} ({s.target_url})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={onClose}
            className="px-3 py-1.5 bg-[#262c38] hover:bg-[#333c4a] text-[#e6e6e6] text-xs font-mono rounded transition cursor-pointer"
          >
            Close View
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-8 max-w-6xl mx-auto w-full space-y-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-xs font-mono text-[#FFAA00] gap-2">
            <RefreshCw className="w-5 h-5 animate-spin" />
            <span>Computing Calibration Metrics...</span>
          </div>
        ) : error ? (
          <div className="bg-[#FF3B3B]/20 border border-[#FF3B3B]/40 text-[#FF3B3B] p-4 rounded-lg font-mono text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : report ? (
          <>
            {/* Prominent Sample Size Warning Banner */}
            {report.sample_size_warning && (
              <div className="bg-[#FFAA00]/15 border-2 border-[#FFAA00]/50 rounded-xl p-4 flex items-start gap-3 shadow-lg">
                <AlertTriangle className="w-5 h-5 text-[#FFAA00] shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[#FFAA00] mb-0.5 font-mono">
                    STATISTICAL SAMPLE SIZE WARNING (Section 35/36)
                  </h4>
                  <p className="text-xs font-mono text-[#e6e6e6] leading-relaxed">
                    {report.sample_size_warning}
                  </p>
                </div>
              </div>
            )}

            {/* Headline Metrics Grid */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-[#10141d] border border-[#262c38] p-4 rounded-xl flex flex-col justify-between shadow-md">
                <span className="text-[11px] font-mono uppercase text-[#8a94a6]">Expected Calibration Error (ECE)</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-[#FFAA00]">
                    {report.ece !== null ? report.ece.toFixed(4) : 'N/A'}
                  </span>
                  {report.ece !== null && (
                    <span className="text-xs font-mono text-[#8a94a6]">
                      ({(report.ece * 100).toFixed(1)}%)
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-mono text-[#6b7280] mt-1">Weighted confidence vs outcome delta</span>
              </div>

              <div className="bg-[#10141d] border border-[#262c38] p-4 rounded-xl flex flex-col justify-between shadow-md">
                <span className="text-[11px] font-mono uppercase text-[#8a94a6]">Brier Score</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-[#00E676]">
                    {report.brier_score !== null ? report.brier_score.toFixed(4) : 'N/A'}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-[#6b7280] mt-1">Mean squared error (0.0 = perfect)</span>
              </div>

              <div className="bg-[#10141d] border border-[#262c38] p-4 rounded-xl flex flex-col justify-between shadow-md">
                <span className="text-[11px] font-mono uppercase text-[#8a94a6]">Evaluated Edges</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-[#e6e6e6]">
                    {report.total_edges_with_outcome}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-[#00E676] mt-1">Has ground truth outcome</span>
              </div>

              <div className="bg-[#10141d] border border-[#262c38] p-4 rounded-xl flex flex-col justify-between shadow-md">
                <span className="text-[11px] font-mono uppercase text-[#8a94a6]">Unverified Excluded</span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-[#4A5568]">
                    {report.total_edges_unverified_excluded}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-[#8a94a6] mt-1">Awaiting verification resolution</span>
              </div>
            </div>

            {/* 5-Bucket Comparison Table / Bar Display */}
            <div className="bg-[#10141d] border border-[#262c38] rounded-xl p-6 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-[#262c38] pb-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#e6e6e6] font-mono flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-[#FFAA00]" />
                  CONFIDENCE RANGE BUCKET CALIBRATION (Section 11.5)
                </h3>
                <span className="text-[11px] font-mono text-[#8a94a6]">
                  Comparing Stated Confidence vs Observed Correctness Rate
                </span>
              </div>

              <div className="space-y-4">
                {report.buckets.map((b) => {
                  const hasData = b.count > 0;
                  const statedPct = b.mean_stated_confidence !== null ? b.mean_stated_confidence * 100 : 0;
                  const obsPct = b.observed_rate !== null ? b.observed_rate * 100 : 0;

                  return (
                    <div
                      key={b.range}
                      className="bg-[#0a0e14] border border-[#262c38] rounded-lg p-4 font-mono text-xs space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="bg-[#262c38] text-[#FFAA00] font-bold px-2 py-0.5 rounded text-xs">
                            Range {b.range}
                          </span>
                          <span className="text-[#8a94a6]">
                            Sample Count: <strong className="text-[#e6e6e6]">{b.count}</strong>
                          </span>
                        </div>

                        {hasData ? (
                          <div className="flex items-center gap-4 text-xs">
                            <span>
                              Stated Conf: <strong className="text-[#FFAA00]">{statedPct.toFixed(1)}%</strong>
                            </span>
                            <span>
                              Observed Rate: <strong className="text-[#00E676]">{obsPct.toFixed(1)}%</strong>
                            </span>
                          </div>
                        ) : (
                          <span className="text-[#6b7280] italic text-[11px] px-2 py-0.5 rounded bg-[#10141d] border border-[#262c38]">
                            {b.note || 'no data in this range'}
                          </span>
                        )}
                      </div>

                      {/* Visual Bar Comparisons */}
                      {hasData ? (
                        <div className="space-y-1.5 pt-1">
                          {/* Stated Confidence Bar */}
                          <div className="flex items-center gap-3">
                            <span className="w-28 text-[10px] text-[#8a94a6] text-right shrink-0">Stated Conf</span>
                            <div className="flex-1 bg-[#10141d] h-3 rounded overflow-hidden border border-[#262c38] relative">
                              <div
                                className="bg-[#FFAA00] h-full transition-all duration-500 rounded"
                                style={{ width: `${statedPct}%` }}
                              />
                            </div>
                            <span className="w-12 text-[10px] text-[#FFAA00] font-bold">{statedPct.toFixed(0)}%</span>
                          </div>

                          {/* Observed Correctness Bar */}
                          <div className="flex items-center gap-3">
                            <span className="w-28 text-[10px] text-[#8a94a6] text-right shrink-0">Observed Rate</span>
                            <div className="flex-1 bg-[#10141d] h-3 rounded overflow-hidden border border-[#262c38] relative">
                              <div
                                className="bg-[#00E676] h-full transition-all duration-500 rounded"
                                style={{ width: `${obsPct}%` }}
                              />
                            </div>
                            <span className="w-12 text-[10px] text-[#00E676] font-bold">{obsPct.toFixed(0)}%</span>
                          </div>
                        </div>
                      ) : (
                        <div className="h-6 bg-[#10141d] rounded border border-[#262c38]/50 flex items-center justify-center text-[10px] text-[#6b7280]">
                          Bucket is empty - no edges fell into range {b.range}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};
