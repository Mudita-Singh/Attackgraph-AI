import React, { useState, useEffect } from 'react';
import type { GraphNode, GraphEdge, Evidence } from '../types';
import { fetchNodeEvidence, submitHumanReview } from '../api/client';
import {
  Info,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  FileText,
  Clock,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Lock,
} from 'lucide-react';

interface InspectorPanelProps {
  scanId: string;
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  nodes: GraphNode[];
  onRefetchGraph: () => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  scanId,
  selectedNode,
  selectedEdge,
  nodes,
  onRefetchGraph,
}) => {
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState<string | null>(null);
  const [expandedEvidenceId, setExpandedEvidenceId] = useState<string | null>(null);

  // Fetch node evidence when node selection changes
  useEffect(() => {
    if (selectedNode) {
      setLoadingEvidence(true);
      fetchNodeEvidence(scanId, selectedNode.id)
        .then((res) => {
          setEvidenceList(res);
          setLoadingEvidence(false);
        })
        .catch((err) => {
          console.error('Error fetching evidence:', err);
          setLoadingEvidence(false);
        });
    } else {
      setEvidenceList([]);
    }
  }, [scanId, selectedNode]);

  // Handle Edge Human Review (Confirm / Invalidate)
  const handleReview = async (decision: 'confirm' | 'refute') => {
    if (!selectedEdge) return;
    setSubmittingReview(true);
    setReviewSuccessMsg(null);
    try {
      const res = await submitHumanReview(
        scanId,
        selectedEdge.id,
        decision,
        'frontend_user',
        `Human review ${decision} executed via inspector panel`
      );
      setSubmittingReview(false);
      setReviewSuccessMsg(
        decision === 'confirm'
          ? 'Edge status updated to VERIFIED.'
          : `Edge INVALIDATED. ${
              res.propagation_result?.undermined_nodes.length || 0
            } downstream node(s) marked undermined.`
      );
      onRefetchGraph();
    } catch (err: any) {
      console.error('Human review failed:', err);
      setSubmittingReview(false);
    }
  };

  const sourceNode = selectedEdge ? nodes.find((n) => n.id === selectedEdge.source_node_id) : null;
  const targetNode = selectedEdge ? nodes.find((n) => n.id === selectedEdge.target_node_id) : null;

  return (
    <aside className="w-80 bg-[#10141d] border-l border-[#262c38] flex flex-col shrink-0 select-none overflow-y-auto z-10">
      {/* Header */}
      <div className="h-10 px-3 border-b border-[#262c38] flex items-center gap-2 bg-[#0a0e14]/50">
        <Info className="w-3.5 h-3.5 text-[#FFAA00]" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[#e6e6e6]">
          Inspector Panel
        </h2>
      </div>

      <div className="p-3 space-y-4">
        {/* State 1: Nothing Selected */}
        {!selectedNode && !selectedEdge && (
          <div className="text-center py-10 space-y-2">
            <Info className="w-8 h-8 text-[#6b7280] mx-auto opacity-50" />
            <p className="text-xs text-[#8a94a6]">No node or edge selected.</p>
            <p className="text-[11px] text-[#6b7280]">
              Click any node or edge on the canvas to inspect evidence, properties, or confirm/invalidate findings.
            </p>
          </div>
        )}

        {/* State 2: Node Selected */}
        {selectedNode && (
          <div className="space-y-4">
            {/* Node Title & Badges */}
            <div className="bg-[#0a0e14] p-3 rounded border border-[#262c38] space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-mono text-[#8a94a6]">
                  ID: {selectedNode.id}
                </span>
                <span className="text-[9px] uppercase font-mono px-2 py-0.5 rounded bg-[#1a2030] text-[#e6e6e6] border border-[#333c4a]">
                  {selectedNode.node_type}
                </span>
              </div>

              <h3 className="text-sm font-bold text-[#e6e6e6] font-mono break-all">
                {selectedNode.label}
              </h3>

              {/* Critical Node Alert */}
              {selectedNode.is_critical && (
                <div className="p-2 rounded bg-[#FF3B3B]/10 border border-[#FF3B3B]/40 text-[#FF3B3B] text-xs font-medium flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <div>
                    <div className="font-bold">CRITICAL BOTTLENECK NODE</div>
                    <div className="text-[10px] text-[#FF3B3B]/80 font-normal">
                      Remediating this node breaks downstream attack paths.
                    </div>
                  </div>
                </div>
              )}

              {/* Undermined Warning */}
              {selectedNode.undermined && (
                <div className="p-2 rounded bg-[#E040FB]/10 border border-[#E040FB]/40 text-[#E040FB] text-xs font-medium flex items-start gap-2">
                  <Lock className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-bold">PATH UNDERMINED</div>
                    <div className="text-[10px] text-[#E040FB]/80 font-normal">
                      {selectedNode.properties?.undermined_reason || 'Supporting attack path was invalidated.'}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Properties */}
            <div className="space-y-1.5">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#8a94a6]">
                Properties
              </h4>
              <div className="bg-[#0a0e14] p-2.5 rounded border border-[#262c38] space-y-1.5 font-mono text-xs">
                {Object.keys(selectedNode.properties || {}).length === 0 ? (
                  <span className="text-[#6b7280] italic text-[11px]">No extra properties</span>
                ) : (
                  Object.entries(selectedNode.properties || {}).map(([key, value]) => (
                    <div key={key} className="flex justify-between items-start gap-2 text-[11px]">
                      <span className="text-[#6b7280]">{key}:</span>
                      <span className="text-[#e6e6e6] text-right font-mono truncate max-w-[170px]">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Linked Evidence List */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#8a94a6]">
                  Linked Evidence ({evidenceList.length})
                </h4>
              </div>

              {loadingEvidence ? (
                <div className="text-xs text-[#6b7280] font-mono py-4 text-center animate-pulse">
                  Fetching evidence...
                </div>
              ) : evidenceList.length === 0 ? (
                <div className="text-xs text-[#6b7280] font-mono p-3 bg-[#0a0e14] rounded border border-[#262c38] text-center">
                  No linked evidence found.
                </div>
              ) : (
                <div className="space-y-2">
                  {evidenceList.map((ev) => (
                    <div
                      key={ev.id}
                      className="bg-[#0a0e14] border border-[#262c38] rounded p-2.5 space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-mono text-[#FFAA00] font-semibold flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5" />
                          {ev.tool_name}
                        </span>
                        <span className="text-[10px] text-[#6b7280] font-mono flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(ev.timestamp).toLocaleTimeString()}
                        </span>
                      </div>

                      {/* Parsed Findings */}
                      {ev.parsed_findings && (
                        <div className="bg-[#10141d] p-2 rounded border border-[#262c38] font-mono text-[11px] space-y-1">
                          {Object.entries(ev.parsed_findings).map(([k, v]) => (
                            <div key={k} className="flex justify-between gap-2">
                              <span className="text-[#6b7280]">{k}:</span>
                              <span className="text-[#e6e6e6] truncate max-w-[150px]">
                                {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Raw Output Accordion */}
                      {ev.raw_output && (
                        <div>
                          <button
                            onClick={() =>
                              setExpandedEvidenceId(expandedEvidenceId === ev.id ? null : ev.id)
                            }
                            className="text-[10px] font-mono text-[#8a94a6] hover:text-[#e6e6e6] flex items-center gap-1 cursor-pointer"
                          >
                            {expandedEvidenceId === ev.id ? (
                              <ChevronDown className="w-3 h-3" />
                            ) : (
                              <ChevronRight className="w-3 h-3" />
                            )}
                            <span>{expandedEvidenceId === ev.id ? 'Hide Raw Output' : 'View Raw Output'}</span>
                          </button>
                          {expandedEvidenceId === ev.id && (
                            <pre className="mt-1.5 p-2 bg-[#10141d] text-[#e6e6e6] font-mono text-[10px] rounded border border-[#262c38] max-h-40 overflow-y-auto whitespace-pre-wrap break-all">
                              {ev.raw_output}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* State 3: Edge Selected */}
        {selectedEdge && (
          <div className="space-y-4">
            {/* Edge Connection Header */}
            <div className="bg-[#0a0e14] p-3 rounded border border-[#262c38] space-y-2">
              <div className="flex items-center justify-between gap-1 text-[10px] font-mono text-[#6b7280]">
                <span>EDGE {selectedEdge.id.slice(0, 8)}</span>
                <span
                  className={`px-2 py-0.5 rounded uppercase font-bold text-[10px] ${
                    selectedEdge.status === 'verified'
                      ? 'bg-[#00E676]/20 text-[#00E676] border border-[#00E676]/40'
                      : selectedEdge.status === 'human_invalidated'
                      ? 'bg-[#E040FB]/20 text-[#E040FB] border border-[#E040FB]/40'
                      : selectedEdge.status === 'refuted'
                      ? 'bg-[#4A5568]/20 text-[#8a94a6] border border-[#4A5568]/40'
                      : 'bg-[#FFAA00]/20 text-[#FFAA00] border border-[#FFAA00]/40'
                  }`}
                >
                  {selectedEdge.status}
                </span>
              </div>

              {/* Source -> Target */}
              <div className="space-y-1 font-mono text-xs text-[#e6e6e6]">
                <div className="truncate text-[#8a94a6]">{sourceNode?.label || selectedEdge.source_node_id}</div>
                <div className="flex items-center gap-2 text-[#FFAA00] font-bold">
                  <ArrowRight className="w-4 h-4 shrink-0" />
                  <span>{selectedEdge.relation_type}</span>
                </div>
                <div className="truncate text-[#8a94a6]">{targetNode?.label || selectedEdge.target_node_id}</div>
              </div>
            </div>

            {/* Confidence Score Bar */}
            <div className="bg-[#0a0e14] p-3 rounded border border-[#262c38] space-y-2">
              <div className="flex justify-between items-center text-xs font-semibold">
                <span className="text-[#8a94a6]">Path Confidence</span>
                <span className="font-mono text-[#00E676]">
                  {selectedEdge.confidence != null
                    ? `${(selectedEdge.confidence * 100).toFixed(0)}%`
                    : 'N/A'}
                </span>
              </div>
              <div className="w-full h-2 bg-[#10141d] rounded-full overflow-hidden border border-[#262c38]">
                <div
                  className="h-full bg-gradient-to-r from-[#FFAA00] to-[#00E676] transition-all duration-300"
                  style={{
                    width: `${
                      selectedEdge.confidence != null ? selectedEdge.confidence * 100 : 50
                    }%`,
                  }}
                />
              </div>
              {selectedEdge.pattern_key && (
                <div className="text-[10px] font-mono text-[#6b7280]">
                  Pattern: <span className="text-[#e6e6e6]">{selectedEdge.pattern_key}</span>
                </div>
              )}
            </div>

            {/* LLM Reasoning */}
            {selectedEdge.reasoning && (
              <div className="space-y-1">
                <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#8a94a6]">
                  Edge Reasoning
                </h4>
                <div className="bg-[#0a0e14] p-2.5 rounded border border-[#262c38] text-xs text-[#e6e6e6] leading-relaxed">
                  {selectedEdge.reasoning}
                </div>
              </div>
            )}

            {/* Human Review Decision Buttons */}
            <div className="space-y-2 pt-2 border-t border-[#262c38]">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[#8a94a6]">
                Human Review Action
              </h4>

              {reviewSuccessMsg && (
                <div className="p-2.5 rounded bg-[#00E676]/10 border border-[#00E676]/30 text-[#00E676] text-xs font-mono">
                  {reviewSuccessMsg}
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => handleReview('confirm')}
                  disabled={submittingReview}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 rounded text-xs font-bold bg-[#00E676]/20 hover:bg-[#00E676]/30 text-[#00E676] border border-[#00E676]/40 cursor-pointer transition-colors disabled:opacity-50"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Confirm</span>
                </button>

                <button
                  onClick={() => handleReview('refute')}
                  disabled={submittingReview}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 rounded text-xs font-bold bg-[#E040FB]/20 hover:bg-[#E040FB]/30 text-[#E040FB] border border-[#E040FB]/40 cursor-pointer transition-colors disabled:opacity-50"
                >
                  <XCircle className="w-4 h-4" />
                  <span>Invalidate</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
