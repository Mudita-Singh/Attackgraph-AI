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
}

export const ReplayControls: React.FC<ReplayControlsProps> = ({
  events,
  currentIndex,
  isPlaying,
  onIndexChange,
  onPlayPause,
  onReset,
}) => {
  if (events.length === 0) {
    return (
      <div className="bg-[#10141d] border-t border-[#262c38] px-4 py-2 flex items-center justify-center text-xs font-mono text-[#8a94a6]">
        <History className="w-4 h-4 mr-2 text-[#E040FB]" />
        No replay events found for this scan.
      </div>
    );
  }

  const currentEvent = events[currentIndex];
  const maxIndex = events.length - 1;

  const getEventDetailText = (event?: ReplayEvent) => {
    if (!event) return 'Initialization';
    if (event.event_type === 'node_created') {
      const node = event.data as GraphNode;
      return `Created Node [${node.node_type}]: ${node.label}`;
    } else {
      const edge = event.data as GraphEdge;
      return `Created Edge [${edge.relation_type}]: ${edge.status}`;
    }
  };

  const currentStep = currentEvent?.step_number;
  const stepText = currentStep !== null && currentStep !== undefined
    ? `Step ${currentStep} (${currentIndex + 1}/${events.length})`
    : `Event ${currentIndex + 1} of ${events.length}`;

  const handleStepBack = () => {
    if (currentIndex > 0) onIndexChange(currentIndex - 1);
  };

  const handleStepForward = () => {
    if (currentIndex < maxIndex) onIndexChange(currentIndex + 1);
  };

  return (
    <div className="bg-[#10141d]/95 backdrop-blur border-t border-[#262c38] px-6 py-3 flex flex-col gap-2 z-30 select-none shadow-2xl">
      {/* Top row: Counter & Event Readout */}
      <div className="flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="bg-[#E040FB]/20 text-[#E040FB] font-bold px-2 py-0.5 rounded border border-[#E040FB]/40 flex items-center gap-1">
            <History className="w-3.5 h-3.5" /> REPLAY
          </span>
          <span className="text-[#e6e6e6] font-semibold">{stepText}</span>
        </div>

        <div className="text-[#8a94a6] truncate max-w-xl bg-[#0a0e14] px-3 py-1 rounded border border-[#262c38]">
          <span className="text-[#00E676] font-bold mr-2">
            {currentEvent?.event_type === 'node_created' ? '● NODE' : '➔ EDGE'}
          </span>
          {getEventDetailText(currentEvent)}
        </div>
      </div>

      {/* Bottom row: Media Controls + Scrubber Slider */}
      <div className="flex items-center gap-4">
        {/* Buttons */}
        <div className="flex items-center gap-1 bg-[#0a0e14] p-1 rounded-lg border border-[#262c38]">
          <button
            onClick={onReset}
            className="p-1.5 text-[#8a94a6] hover:text-[#e6e6e6] hover:bg-[#262c38] rounded transition"
            title="Reset to beginning"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={handleStepBack}
            disabled={currentIndex <= 0}
            className="p-1.5 text-[#8a94a6] hover:text-[#e6e6e6] hover:bg-[#262c38] rounded transition disabled:opacity-30 disabled:hover:bg-transparent"
            title="Step Back"
          >
            <SkipBack className="w-4 h-4" />
          </button>

          <button
            onClick={onPlayPause}
            className="p-1.5 bg-[#E040FB] hover:bg-[#d030eb] text-black font-bold rounded transition shadow-md flex items-center justify-center"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? <Pause className="w-4 h-4 fill-black" /> : <Play className="w-4 h-4 fill-black ml-0.5" />}
          </button>

          <button
            onClick={handleStepForward}
            disabled={currentIndex >= maxIndex}
            className="p-1.5 text-[#8a94a6] hover:text-[#e6e6e6] hover:bg-[#262c38] rounded transition disabled:opacity-30 disabled:hover:bg-transparent"
            title="Step Forward"
          >
            <SkipForward className="w-4 h-4" />
          </button>
        </div>

        {/* Scrubber slider */}
        <div className="flex-1 flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={maxIndex}
            value={currentIndex}
            onChange={(e) => onIndexChange(Number(e.target.value))}
            className="w-full h-2 bg-[#1a2030] rounded-lg appearance-none cursor-pointer accent-[#E040FB]"
          />
        </div>
      </div>
    </div>
  );
};
