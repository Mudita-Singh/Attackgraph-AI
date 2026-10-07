import React from 'react';
import { Play, Pause, SkipForward, SkipBack, RotateCcw, History } from 'lucide-react';
import type { ReplayEvent, GraphNode, GraphEdge } from '../types';

interface ReplayControlsProps {
  events: ReplayEvent[];
  currentIndex: number;
  isPlaying: boolean;
  onIndexChange: (index: number) => void;
  onPlayPause: () => void;
  onReset: () => void;
  speed?: number;
  onSpeedChange?: (speed: number) => void;
}

export const ReplayControls: React.FC<ReplayControlsProps> = ({
  events,
  currentIndex,
  isPlaying,
  onIndexChange,
  onPlayPause,
  onReset,
  speed = 1,
  onSpeedChange,
}) => {
  if (events.length === 0) {
    return (
      <div className="bg-[#12152A] border-t border-[#ffffff14] px-6 py-3 flex items-center justify-center text-xs font-mono text-slate-400 gap-2">
        <History className="w-4 h-4 text-indigo-400" />
        <span>No replay events found for this scan.</span>
      </div>
    );
  }

  const currentEvent = events[currentIndex];
  const maxIndex = events.length - 1;

  const getEventDetailText = (event?: ReplayEvent) => {
    if (!event) return 'Initialization';
    if (event.event_type === 'node_created') {
      const node = event.data as GraphNode;
      const stepStr = event.step_number != null ? ` (Step ${event.step_number})` : '';
      return `Created Node [${node.node_type}]: ${node.label}${stepStr}`;
    } else {
      const edge = event.data as GraphEdge;
      const stepStr = event.step_number != null ? ` (Step ${event.step_number})` : '';
      return `Created Edge [${edge.relation_type}]: ${edge.status}${stepStr}`;
    }
  };

  const handleStepBack = () => {
    if (currentIndex > 0) onIndexChange(currentIndex - 1);
  };

  const handleStepForward = () => {
    if (currentIndex < maxIndex) onIndexChange(currentIndex + 1);
  };

  return (
    <div className="h-16 bg-[#12152A]/95 backdrop-blur-md border-t border-[#ffffff14] px-4 flex items-center justify-between gap-4 z-30 select-none shadow-2xl shrink-0 text-xs font-mono">
      {/* Playback Controls & Range Scrubber */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-1 bg-[#0B0D1A] p-1 rounded-xl border border-[#ffffff14]">
          <button
            onClick={onReset}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg transition-colors cursor-pointer"
            title="Reset to beginning"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={handleStepBack}
            disabled={currentIndex <= 0}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg transition-colors cursor-pointer disabled:opacity-30 disabled:hover:bg-transparent"
            title="Step Back"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onPlayPause}
            className="p-1.5 bg-[#6366F1] hover:bg-[#4F46E5] text-white font-bold rounded-lg transition-all shadow-md flex items-center justify-center cursor-pointer"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current ml-0.5" />}
          </button>

          <button
            onClick={handleStepForward}
            disabled={currentIndex >= maxIndex}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg transition-colors cursor-pointer disabled:opacity-30 disabled:hover:bg-transparent"
            title="Step Forward"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Speed Selector */}
        {onSpeedChange && (
          <div className="flex items-center bg-[#0B0D1A] border border-[#ffffff14] rounded-xl p-0.5 text-xs">
            {[0.5, 1, 2].map((s) => (
              <button
                key={s}
                onClick={() => onSpeedChange(s)}
                className={`px-2 py-0.5 rounded-lg transition-all cursor-pointer text-[11px] ${
                  speed === s
                    ? 'bg-[#6366F1] text-white font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Center: Range Scrubber */}
      <div className="flex-1 max-w-xl flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={maxIndex}
          value={currentIndex}
          onChange={(e) => onIndexChange(Number(e.target.value))}
          className="w-full h-1.5 bg-[#0B0D1A] rounded-lg appearance-none cursor-pointer accent-[#6366F1]"
        />
      </div>

      {/* Right: Counter & Truncated Event Readout */}
      <div className="flex items-center gap-3 shrink-0 min-w-0">
        <span className="text-slate-200 font-semibold shrink-0">
          Event {currentIndex + 1}/{events.length}
          {currentEvent?.step_number != null && (
            <span className="text-indigo-400 ml-1">(Step #{currentEvent.step_number})</span>
          )}
        </span>

        <div 
          className="text-slate-300 truncate max-w-[280px] bg-[#0B0D1A] px-2.5 py-1 rounded-xl border border-[#ffffff14] flex items-center gap-1.5 shrink-0"
          title={getEventDetailText(currentEvent)}
        >
          <span className={`text-[9px] font-bold px-1 py-0.2 rounded uppercase shrink-0 ${
            currentEvent?.event_type === 'node_created' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-cyan-500/20 text-cyan-400'
          }`}>
            {currentEvent?.event_type === 'node_created' ? 'NODE' : 'EDGE'}
          </span>
          <span className="truncate text-xs">{getEventDetailText(currentEvent)}</span>
        </div>
      </div>
    </div>
  );
};
