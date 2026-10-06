import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps, Node } from '@xyflow/react';
import type { GraphNode } from '../types';
import { Key, AlertTriangle, Globe, Lock, ShieldAlert } from 'lucide-react';

export type CustomNode = Node<{ node: GraphNode }, 'customNode'>;

export const CustomGraphNode = memo(({ data, selected }: NodeProps<CustomNode>) => {
  const node = data.node;
  const isCritical = node.is_critical;
  const isUndermined = node.undermined;
  const type = node.node_type.toLowerCase();

  // Determine shape & color scheme
  const isSecret = type.includes('credential') || type.includes('secret') || type.includes('key') || type.includes('token');
  const isFinding = type.includes('finding') || type.includes('vulnerability') || type.includes('access_control') || type.includes('reflected');

  // Colors
  let strokeColor = '#5f6b80';
  let fillColor = '#1a2030';
  let textColor = '#e6e6e6';
  let badgeColor = 'bg-[#262c38] text-[#8a94a6]';

  if (isCritical) {
    strokeColor = '#FF3B3B';
    fillColor = '#2a0e14';
    textColor = '#FF3B3B';
    badgeColor = 'bg-[#FF3B3B]/20 text-[#FF3B3B] border-[#FF3B3B]/50';
  } else if (isSecret) {
    strokeColor = '#FFD600';
    fillColor = '#2a2200';
    textColor = '#FFD600';
    badgeColor = 'bg-[#FFD600]/20 text-[#FFD600] border-[#FFD600]/50';
  } else if (isFinding) {
    strokeColor = '#FFAA00';
    fillColor = '#2a1b00';
    textColor = '#FFAA00';
    badgeColor = 'bg-[#FFAA00]/20 text-[#FFAA00] border-[#FFAA00]/50';
  }

  // Node Icon
  const getIcon = () => {
    if (isCritical) return <ShieldAlert className="w-4 h-4 text-[#FF3B3B]" />;
    if (isSecret) return <Key className="w-4 h-4 text-[#FFD600]" />;
    if (isFinding) return <AlertTriangle className="w-4 h-4 text-[#FFAA00]" />;
    return <Globe className="w-4 h-4 text-[#8a94a6]" />;
  };

  return (
    <div className="relative group">
      {/* Critical Outer Ring SVG */}
      {isCritical && (
        <div className="absolute -inset-2 rounded-xl border-2 border-[#FF3B3B]/40 pointer-events-none animate-pulse">
          <div className="absolute -inset-1 rounded-xl border border-[#FF3B3B]/20" />
        </div>
      )}

      {/* Undermined warning indicator */}
      {isUndermined && !isCritical && (
        <div className="absolute -top-2 -right-2 bg-[#E040FB] text-black font-bold text-[9px] px-1.5 py-0.5 rounded-full shadow z-20 flex items-center gap-0.5 animate-pulse">
          <Lock className="w-2.5 h-2.5" /> UNDERMINED
        </div>
      )}

      {/* Main Node Card */}
      <div
        className={`w-48 px-3 py-2.5 rounded-lg border transition-all cursor-pointer relative z-10 ${
          isUndermined && !isCritical ? 'border-2 border-dashed border-[#E040FB] opacity-70 bg-[#1f1225]' : ''
        } ${
          selected
            ? 'border-[#00E676] ring-2 ring-[#00E676]/30 shadow-lg'
            : 'hover:border-[#333c4a]'
        }`}
        style={{
          backgroundColor: isUndermined && !isCritical ? '#1c1024' : fillColor,
          borderColor: selected ? '#00E676' : (isUndermined && !isCritical ? '#E040FB' : strokeColor),
        }}
      >
        <Handle
          type="target"
          position={Position.Top}
          className="w-2.5 h-2.5 bg-[#262c38] border-2 border-[#8a94a6] !top-[-5px]"
        />

        <div className="flex items-start gap-2">
          <div className="mt-0.5 shrink-0">{getIcon()}</div>
          <div className="flex-1 min-w-0">
            {/* Label */}
            <div
              className={`text-xs font-semibold truncate ${
                node.label.startsWith('/') || node.label.includes(':') ? 'font-mono' : ''
              }`}
              style={{ color: textColor }}
              title={node.label}
            >
              {node.label}
            </div>

            {/* Type badge & ID */}
            <div className="flex items-center justify-between gap-1 mt-1">
              <span className={`text-[9px] uppercase font-mono px-1.5 py-0.2 rounded border ${badgeColor}`}>
                {node.node_type}
              </span>
              <span className="text-[9px] font-mono text-[#6b7280]">
                {node.id.slice(0, 6)}
              </span>
            </div>
          </div>
        </div>

        <Handle
          type="source"
          position={Position.Bottom}
          className="w-2.5 h-2.5 bg-[#262c38] border-2 border-[#8a94a6] !bottom-[-5px]"
        />
      </div>
    </div>
  );
});

CustomGraphNode.displayName = 'CustomGraphNode';
