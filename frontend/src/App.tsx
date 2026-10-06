import { useState, useEffect, useCallback, useMemo } from 'react';
import type { Scan, GraphData, GraphNode, GraphEdge, AgentLog, ReplayEvent } from './types';
import { fetchScans, fetchScanGraph, fetchAgentLog, fetchReplayEvents } from './api/client';
import { TopBar } from './components/TopBar';
import { ActivityLog } from './components/ActivityLog';
import { GraphCanvas } from './components/GraphCanvas';
import { InspectorPanel } from './components/InspectorPanel';
import { ReplayControls } from './components/ReplayControls';
import { CalibrationView } from './components/CalibrationView';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export function App() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [selectedScanId, setSelectedScanId] = useState<string>('');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>([]);
  const [showRefuted, setShowRefuted] = useState<boolean>(false);
  const [showCalibrationView, setShowCalibrationView] = useState<boolean>(false);

  // Replay Mode State
  const [isReplayMode, setIsReplayMode] = useState<boolean>(false);
  const [replayEvents, setReplayEvents] = useState<ReplayEvent[]>([]);
  const [replayIndex, setReplayIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);

  const [loadingScans, setLoadingScans] = useState<boolean>(true);
  const [loadingGraph, setLoadingGraph] = useState<boolean>(false);
  const [loadingLogs, setLoadingLogs] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load all scans on mount
  useEffect(() => {
    setLoadingScans(true);
    fetchScans()
      .then((data) => {
        setScans(data);
        if (data.length > 0) {
          setSelectedScanId(data[0].id);
        }
        setLoadingScans(false);
      })
      .catch((err) => {
        console.error('Failed to load scans:', err);
        setErrorMsg('Failed to connect to backend API at http://127.0.0.1:8000.');
        setLoadingScans(false);
      });
  }, []);

  // Fetch Graph Data, Agent Logs, and Replay Events when selectedScanId changes
  const loadScanDetails = useCallback((scanId: string) => {
    if (!scanId) return;

    setLoadingGraph(true);
    setSelectedNode(null);
    setSelectedEdge(null);

    fetchScanGraph(scanId)
      .then((data) => {
        setGraphData(data);
        setLoadingGraph(false);
      })
      .catch((err) => {
        console.error(`Failed to load graph for scan ${scanId}:`, err);
        setErrorMsg(`Failed to load graph for scan ${scanId}`);
        setLoadingGraph(false);
      });

    setLoadingLogs(true);
    fetchAgentLog(scanId)
      .then((data) => {
        setAgentLogs(data);
        setLoadingLogs(false);
      })
      .catch((err) => {
        console.error(`Failed to load agent log for scan ${scanId}:`, err);
        setLoadingLogs(false);
      });

    fetchReplayEvents(scanId)
      .then((events) => {
        setReplayEvents(events);
        setReplayIndex(events.length > 0 ? events.length - 1 : 0);
      })
      .catch((err) => {
        console.error(`Failed to load replay events for scan ${scanId}:`, err);
      });
  }, []);

  useEffect(() => {
    if (selectedScanId) {
      loadScanDetails(selectedScanId);
    }
  }, [selectedScanId, loadScanDetails]);

  // Handle Playback Timer in Replay Mode
  useEffect(() => {
    let timer: any = null;
    if (isPlaying && isReplayMode && replayEvents.length > 0) {
      timer = setInterval(() => {
        setReplayIndex((prev) => {
          if (prev >= replayEvents.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isPlaying, isReplayMode, replayEvents]);

  // Refetch graph when human review occurs
  const handleRefetchGraph = useCallback(() => {
    if (selectedScanId) {
      fetchScanGraph(selectedScanId)
        .then((data) => setGraphData(data))
        .catch((err) => console.error('Error refetching graph:', err));

      fetchReplayEvents(selectedScanId)
        .then((events) => setReplayEvents(events))
        .catch((err) => console.error('Error refetching replay events:', err));
    }
  }, [selectedScanId]);

  // Active step number for two-way ActivityLog sync
  const activeStepNumber = useMemo(() => {
    if (!isReplayMode || replayEvents.length === 0) return null;
    const currentEv = replayEvents[replayIndex];
    return currentEv?.step_number ?? null;
  }, [isReplayMode, replayEvents, replayIndex]);

  // Handle clicking a step in ActivityLog sidebar to jump replay position
  const handleSelectStepFromLog = useCallback((stepNumber: number) => {
    if (!isReplayMode) return;
    const targetIdx = replayEvents.findIndex((ev) => ev.step_number === stepNumber);
    if (targetIdx !== -1) {
      setReplayIndex(targetIdx);
    }
  }, [isReplayMode, replayEvents]);

  // Count hidden refuted edges
  const hiddenEdgeCount = useMemo(() => {
    if (!graphData || showRefuted) return 0;
    return graphData.edges.filter(
      (e) => e.status === 'refuted' || e.status === 'human_invalidated'
    ).length;
  }, [graphData, showRefuted]);

  // Count critical nodes
  const criticalCount = useMemo(() => {
    if (!graphData) return 0;
    return graphData.nodes.filter((n) => n.is_critical).length;
  }, [graphData]);

  if (loadingScans) {
    return (
      <div className="h-screen w-screen bg-[#0a0e14] flex flex-col items-center justify-center text-xs font-mono text-[#8a94a6] gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-[#FFAA00]" />
        <span>INITIALIZING ATTACKGRAPH SOC FRONTEND...</span>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen bg-[#0a0e14] flex flex-col overflow-hidden">
      {/* Error Alert Bar */}
      {errorMsg && (
        <div className="bg-[#FF3B3B]/20 border-b border-[#FF3B3B]/40 text-[#FF3B3B] px-4 py-1.5 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button
            onClick={() => setErrorMsg(null)}
            className="text-xs hover:underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Top Navigation Bar */}
      <TopBar
        scans={scans}
        selectedScanId={selectedScanId}
        onSelectScan={setSelectedScanId}
        showRefuted={showRefuted}
        onToggleShowRefuted={() => setShowRefuted((prev) => !prev)}
        hiddenEdgeCount={hiddenEdgeCount}
        criticalCount={criticalCount}
        isReplayMode={isReplayMode}
        onToggleReplayMode={() => {
          setIsReplayMode((prev) => {
            const nextMode = !prev;
            if (nextMode && replayEvents.length > 0) {
              setReplayIndex(0); // Start replay at beginning when toggling ON
            }
            return nextMode;
          });
          setIsPlaying(false);
        }}
        onOpenCalibration={() => setShowCalibrationView(true)}
      />

      {/* Three-Pane Workspace */}
      <div className="flex-1 flex flex-row overflow-hidden relative">
        {/* Left Sidebar: Activity Log */}
        <ActivityLog
          logs={agentLogs}
          loading={loadingLogs}
          activeStepNumber={activeStepNumber}
          onSelectStep={handleSelectStepFromLog}
        />

        {/* Center: Graph Canvas + Replay Controls Overlay */}
        <main className="flex-1 flex flex-col relative h-full overflow-hidden">
          {loadingGraph && (
            <div className="absolute inset-0 bg-[#0a0e14]/70 z-30 flex items-center justify-center text-xs font-mono text-[#FFAA00] gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Rendering Scan Graph...</span>
            </div>
          )}

          <div className="flex-1 relative">
            <GraphCanvas
              graphData={graphData}
              showRefuted={showRefuted}
              selectedNodeId={selectedNode?.id}
              selectedEdgeId={selectedEdge?.id}
              onSelectNode={setSelectedNode}
              onSelectEdge={setSelectedEdge}
              isReplayMode={isReplayMode}
              replayEvents={replayEvents}
              replayIndex={replayIndex}
            />
          </div>

          {/* Replay Scrubber Controls at bottom of center panel */}
          {isReplayMode && (
            <ReplayControls
              events={replayEvents}
              currentIndex={replayIndex}
              isPlaying={isPlaying}
              onIndexChange={setReplayIndex}
              onPlayPause={() => setIsPlaying((prev) => !prev)}
              onReset={() => {
                setReplayIndex(0);
                setIsPlaying(false);
              }}
            />
          )}
        </main>

        {/* Right Sidebar: Inspector Panel */}
        <InspectorPanel
          scanId={selectedScanId}
          selectedNode={selectedNode}
          selectedEdge={selectedEdge}
          nodes={graphData?.nodes || []}
          onRefetchGraph={handleRefetchGraph}
        />
      </div>

      {/* Offline Calibration View Overlay */}
      {showCalibrationView && (
        <CalibrationView
          scans={scans}
          onClose={() => setShowCalibrationView(false)}
        />
      )}
    </div>
  );
}

export default App;
