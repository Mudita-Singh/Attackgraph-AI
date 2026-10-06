import React, { useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Position,
  MarkerType,
} from '@xyflow/react';
import type { Node, Edge, NodeTypes } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import type { GraphData, GraphNode, GraphEdge, ReplayEvent } from '../types';
import { CustomGraphNode } from './CustomNodes';

const nodeTypes: NodeTypes = {
  customNode: CustomGraphNode as any,
};

interface GraphCanvasProps {
  graphData: GraphData | null;
  showRefuted: boolean;
  selectedNodeId?: string | null;
  selectedEdgeId?: string | null;
  onSelectNode: (node: GraphNode | null) => void;
  onSelectEdge: (edge: GraphEdge | null) => void;
  isReplayMode?: boolean;
  replayEvents?: ReplayEvent[];
  replayIndex?: number;
}

const getLayoutedElements = (
  nodes: GraphNode[],
  edges: GraphEdge[],
  showRefuted: boolean,
  isReplayMode?: boolean,
  replayEvents?: ReplayEvent[],
  replayIndex?: number
) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 50 });

  const nodeWidth = 200;
  const nodeHeight = 65;

  // Determine full node and edge list for static layout computation
  let allNodes = nodes;
  let allEdges = edges;

  if (isReplayMode && replayEvents && replayEvents.length > 0) {
    const nodeMap = new Map<string, GraphNode>();
    const edgeMap = new Map<string, GraphEdge>();
    replayEvents.forEach((ev) => {
      if (ev.event_type === 'node_created') {
        const n = ev.data as GraphNode;
        nodeMap.set(n.id, n);
      } else {
        const e = ev.data as GraphEdge;
        edgeMap.set(e.id, e);
      }
    });
    // Add any missing from graphData
    nodes.forEach((n) => nodeMap.set(n.id, n));
    edges.forEach((e) => edgeMap.set(e.id, e));
    allNodes = Array.from(nodeMap.values());
    allEdges = Array.from(edgeMap.values());
  }

  const cols = 3;
  allNodes.forEach((node, idx) => {
    const gridX = (idx % cols) * 240 + 100;
    const gridY = Math.floor(idx / cols) * 110 + 50;
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight, x: gridX, y: gridY });
  });

  if (allEdges.length > 0) {
    allEdges.forEach((edge) => {
      dagreGraph.setEdge(edge.source_node_id, edge.target_node_id);
    });
    dagre.layout(dagreGraph);
  }

  // Determine visible subsets based on mode
  let visibleNodes = allNodes;
  let visibleEdges = allEdges;

  if (isReplayMode && replayEvents && replayEvents.length > 0) {
    const idx = replayIndex ?? 0;
    const slice = replayEvents.slice(0, idx + 1);
    const visibleNodeIds = new Set(slice.filter((ev) => ev.event_type === 'node_created').map((ev) => (ev.data as GraphNode).id));
    const visibleEdgeIds = new Set(slice.filter((ev) => ev.event_type === 'edge_created').map((ev) => (ev.data as GraphEdge).id));

    visibleNodes = allNodes.filter((n) => visibleNodeIds.has(n.id));
    visibleEdges = allEdges.filter((e) => visibleEdgeIds.has(e.id));
  } else if (!showRefuted) {
    visibleEdges = visibleEdges.filter((e) => e.status !== 'refuted' && e.status !== 'human_invalidated');
  }

  const flowNodes: Node[] = visibleNodes.map((node, idx) => {
    const nodeWithPos = dagreGraph.node(node.id);
    const defaultX = (idx % cols) * 240 + 100;
    const defaultY = Math.floor(idx / cols) * 110 + 50;
    return {
      id: node.id,
      type: 'customNode',
      position: {
        x: nodeWithPos ? nodeWithPos.x - nodeWidth / 2 : defaultX,
        y: nodeWithPos ? nodeWithPos.y - nodeHeight / 2 : defaultY,
      },
      data: { node },
      targetPosition: Position.Top,
      sourcePosition: Position.Bottom,
    };
  });

  const flowEdges: Edge[] = visibleEdges.map((edge) => {
    let edgeColor = '#FFAA00'; // unverified default amber
    let strokeWidth = 2;
    let strokeDasharray: string | undefined = '5 5';
    let labelColor = '#8a94a6';

    if (edge.status === 'verified') {
      edgeColor = '#00E676';
      strokeWidth = 2.5;
      strokeDasharray = undefined;
      labelColor = '#00E676';
    } else if (edge.status === 'refuted') {
      edgeColor = '#4A5568';
      strokeWidth = 1.5;
      strokeDasharray = '3 3';
      labelColor = '#4A5568';
    } else if (edge.status === 'human_invalidated') {
      edgeColor = '#E040FB';
      strokeWidth = 1.5;
      strokeDasharray = '4 4';
      labelColor = '#E040FB';
    }

    return {
      id: edge.id,
      source: edge.source_node_id,
      target: edge.target_node_id,
      label: edge.relation_type,
      labelStyle: { fill: labelColor, fontSize: 10, fontFamily: 'monospace', fontWeight: 600 },
      labelBgStyle: { fill: '#10141d', fillOpacity: 0.85, rx: 4, ry: 4 },
      labelBgPadding: [6, 4] as [number, number],
      style: {
        stroke: edgeColor,
        strokeWidth,
        strokeDasharray,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edgeColor,
        width: 16,
        height: 16,
      },
      data: { edge },
    };
  });

  return { flowNodes, flowEdges };
};

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  graphData,
  showRefuted,
  selectedNodeId,
  selectedEdgeId,
  onSelectNode,
  onSelectEdge,
  isReplayMode,
  replayEvents,
  replayIndex,
}) => {
  const { flowNodes, flowEdges } = useMemo(() => {
    if (!graphData && (!replayEvents || replayEvents.length === 0)) {
      return { flowNodes: [], flowEdges: [] };
    }
    return getLayoutedElements(
      graphData?.nodes || [],
      graphData?.edges || [],
      showRefuted,
      isReplayMode,
      replayEvents,
      replayIndex
    );
  }, [graphData, showRefuted, isReplayMode, replayEvents, replayIndex]);

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  React.useEffect(() => {
    setNodes(
      flowNodes.map((n) => ({
        ...n,
        selected: n.id === selectedNodeId,
      }))
    );
  }, [flowNodes, selectedNodeId, setNodes]);

  React.useEffect(() => {
    setEdges(
      flowEdges.map((e) => ({
        ...e,
        selected: e.id === selectedEdgeId,
      }))
    );
  }, [flowEdges, selectedEdgeId, setEdges]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const originalNode = graphData?.nodes.find((n) => n.id === node.id);
      if (originalNode) {
        onSelectNode(originalNode);
        onSelectEdge(null);
      }
    },
    [graphData, onSelectNode, onSelectEdge]
  );

  const handleEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      const originalEdge = graphData?.edges.find((e) => e.id === edge.id);
      if (originalEdge) {
        onSelectEdge(originalEdge);
        onSelectNode(null);
      }
    },
    [graphData, onSelectEdge, onSelectNode]
  );

  const handlePaneClick = useCallback(() => {
    onSelectNode(null);
    onSelectEdge(null);
  }, [onSelectNode, onSelectEdge]);

  if (!graphData) {
    return (
      <div className="flex-1 bg-[#0a0e14] flex items-center justify-center text-xs font-mono text-[#6b7280]">
        No scan graph loaded. Select a scan from the top bar.
      </div>
    );
  }

  return (
    <div className="flex-1 h-full bg-[#0a0e14] relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={handlePaneClick}
        fitView
        minZoom={0.2}
        maxZoom={2.5}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#262c38" gap={24} size={1} />
        <Controls className="!bg-[#10141d] !border-[#262c38] !text-[#e6e6e6] !rounded" />
        <MiniMap
          nodeColor={(n) => {
            const graphNode = (n.data as any)?.node as GraphNode;
            if (graphNode?.is_critical) return '#FF3B3B';
            if (graphNode?.node_type.includes('credential')) return '#FFD600';
            return '#5f6b80';
          }}
          maskColor="rgba(10, 14, 20, 0.8)"
          className="!bg-[#10141d] !border-[#262c38] !rounded"
        />
      </ReactFlow>
    </div>
  );
};
