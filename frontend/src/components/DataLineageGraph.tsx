import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  BackgroundVariant,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Database, Cpu, FileOutput, Loader2, ArrowRight } from 'lucide-react';

const API_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws')
  .replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

// ── Color scheme ────────────────────────────────────────────────────
const NODE_COLORS: Record<string, { bg: string; border: string; accent: string }> = {
  source:  { bg: '#0f1d2e', border: '#1d4ed8', accent: '#3b82f6' },
  process: { bg: '#1a1525', border: '#7c3aed', accent: '#8b5cf6' },
  output:  { bg: '#0f1f1a', border: '#059669', accent: '#10b981' },
};

const NODE_ICONS: Record<string, typeof Database> = {
  source: Database,
  process: Cpu,
  output: FileOutput,
};

// ── Custom Node Component ───────────────────────────────────────────
function LineageNode({ data }: { data: { label: string; nodeType: string } }) {
  const colors = NODE_COLORS[data.nodeType] || NODE_COLORS.source;
  const Icon = NODE_ICONS[data.nodeType] || Database;
  const lines = data.label.split('\n');

  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: 10,
      background: colors.bg,
      border: `2px solid ${colors.border}`,
      minWidth: 200,
      boxShadow: `0 0 20px ${colors.accent}15`,
    }}>
      <Handle type="target" position={Position.Left} style={{ background: colors.accent, width: 8, height: 8, border: 'none' }} />
      <Handle type="source" position={Position.Right} style={{ background: colors.accent, width: 8, height: 8, border: 'none' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon size={16} color={colors.accent} />
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e5e7eb' }}>{lines[0]}</div>
          {lines[1] && <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>{lines[1]}</div>}
        </div>
      </div>
      <div style={{
        position: 'absolute', top: -8, right: 8,
        fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
        padding: '1px 6px', borderRadius: 4,
        background: colors.accent + '20', color: colors.accent,
        border: `1px solid ${colors.accent}40`,
      }}>
        {data.nodeType}
      </div>
    </div>
  );
}

const nodeTypes = { lineageNode: LineageNode };

// ── Field Coverage indicator ────────────────────────────────────────
interface FieldInfo {
  description: string;
  traced: boolean;
  paths: string[];
}

interface LineageStats {
  source_systems: number;
  processing_steps: number;
  outputs: number;
  total_flows: number;
  critical_fields_total: number;
  critical_fields_traced: number;
  lineage_coverage_pct: number;
}

interface LineageData {
  nodes: { id: string; type: string; label: string; x: number; y: number }[];
  edges: { source: string; target: string; label: string; fields: string[] }[];
  field_coverage: Record<string, FieldInfo>;
  stats: LineageStats;
}

// ── Main Component ──────────────────────────────────────────────────
interface DataLineageGraphProps {
  pipelineStatus: string;
  selectedSystem: string;
}

export function DataLineageGraph({ pipelineStatus, selectedSystem }: DataLineageGraphProps) {
  const [data, setData] = useState<LineageData | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFields, setShowFields] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);

  useEffect(() => {
    if (pipelineStatus !== 'completed' || dataLoaded) return;
    setLoading(true);
    (async () => {
      try {
        const url = selectedSystem
          ? `${API_BASE}/api/lineage/graph?system_id=${encodeURIComponent(selectedSystem)}`
          : `${API_BASE}/api/lineage/graph`;
        const res = await fetch(url);
        const json = await res.json();
        setData(json);
      } catch (e) {
        console.error('Failed to fetch lineage graph:', e);
      } finally {
        setLoading(false);
        setDataLoaded(true);
      }
    })();
  }, [pipelineStatus, dataLoaded]);

  // Reset data when the selected operational system changes
  useEffect(() => {
    setDataLoaded(false);
    setData(null);
  }, [selectedSystem]);

  const nodes: Node[] = useMemo(() => {
    if (!data) return [];
    return data.nodes.map(n => ({
      id: n.id,
      type: 'lineageNode',
      position: { x: n.x, y: n.y },
      data: { label: n.label, nodeType: n.type },
    }));
  }, [data]);

  const edges: Edge[] = useMemo(() => {
    if (!data) return [];
    return data.edges.map((e, i) => ({
      id: `edge-${i}`,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      animated: true,
      label: e.label,
      labelStyle: { fontSize: 9, fill: '#9ca3af', fontWeight: 500 },
      labelBgStyle: { fill: '#0a0e1a', fillOpacity: 0.9 },
      labelBgPadding: [4, 6] as [number, number],
      labelBgBorderRadius: 4,
      style: {
        stroke: e.source.startsWith('src_') ? '#3b82f6' :
                e.target.startsWith('out_') ? '#10b981' : '#8b5cf6',
        strokeWidth: 1.5,
      },
    }));
  }, [data]);

  const toggleFields = useCallback(() => setShowFields(prev => !prev), []);

  // Show "waiting for analysis" when pipeline hasn't run yet
  if (pipelineStatus === 'idle' && !dataLoaded) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
        height: 400, background: '#111827', borderRadius: 16, border: '1px solid #2a3350',
        gap: 16,
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: '50%',
          background: 'linear-gradient(135deg, #8b5cf620, #10b98120)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: '2px solid #8b5cf640',
        }}>
          <ArrowRight size={32} color="#8b5cf6" />
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#e5e7eb' }}>Data Lineage Graph</div>
        <div style={{ fontSize: 13, color: '#6b7280', textAlign: 'center', maxWidth: 420, lineHeight: 1.6 }}>
          Run the AI analysis pipeline to trace data flows across source systems,
          processing steps, and output files.
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 12, color: '#8b5cf6', background: '#8b5cf610',
          padding: '8px 16px', borderRadius: 8, border: '1px solid #8b5cf630',
        }}>
          <Database size={14} />
          <span>Click <strong>Analyze Compliance</strong> above to start</span>
        </div>
      </div>
    );
  }

  // Show spinner during analysis
  if (pipelineStatus === 'running') {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
        height: 400, background: '#111827', borderRadius: 16, border: '1px solid #2a3350',
        gap: 16,
      }}>
        <Loader2 size={40} color="#8b5cf6" style={{ animation: 'spin 1s linear infinite' }} />
        <div style={{ fontSize: 16, fontWeight: 700, color: '#e5e7eb' }}>Building Lineage Graph</div>
        <div style={{ fontSize: 12, color: '#6b7280' }}>
          Tracing data flows through legacy deposit system...
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400, color: '#6b7280', gap: 8 }}>
        <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
        Loading lineage graph...
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ textAlign: 'center', color: '#6b7280', padding: 40 }}>
        Failed to load data lineage graph.
      </div>
    );
  }

  const { stats, field_coverage } = data;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Stats Bar */}
      <div style={{
        display: 'flex', gap: 10, flexWrap: 'wrap',
        padding: 12, background: '#111827', borderRadius: 12, border: '1px solid #2a3350',
      }}>
        {[
          { label: 'Source Systems', value: stats.source_systems, color: '#3b82f6' },
          { label: 'Processing Steps', value: stats.processing_steps, color: '#8b5cf6' },
          { label: 'Outputs', value: stats.outputs, color: '#10b981' },
          { label: 'Data Flows', value: stats.total_flows, color: '#f59e0b' },
          { label: 'Critical Fields', value: `${stats.critical_fields_traced}/${stats.critical_fields_total}`, color: '#06b6d4' },
          { label: 'Lineage Coverage', value: `${stats.lineage_coverage_pct}%`, color: stats.lineage_coverage_pct === 100 ? '#10b981' : '#f59e0b' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            flex: 1, minWidth: 120, textAlign: 'center',
            padding: '8px 10px', borderRadius: 8,
            background: '#0d1117', border: `1px solid ${color}25`,
          }}>
            <div style={{ fontSize: 18, fontWeight: 800, color }}>{value}</div>
            <div style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Flow Legend */}
      <div style={{
        display: 'flex', gap: 20, alignItems: 'center',
        padding: '8px 16px', background: '#111827', borderRadius: 8,
        border: '1px solid #2a3350', fontSize: 11,
      }}>
        <span style={{ color: '#6b7280', fontWeight: 600 }}>FLOW:</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Database size={12} color="#3b82f6" />
          <span style={{ color: '#3b82f6' }}>Source Systems</span>
        </div>
        <ArrowRight size={12} color="#6b7280" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Cpu size={12} color="#8b5cf6" />
          <span style={{ color: '#8b5cf6' }}>Processing</span>
        </div>
        <ArrowRight size={12} color="#6b7280" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <FileOutput size={12} color="#10b981" />
          <span style={{ color: '#10b981' }}>FDIC Outputs</span>
        </div>
        <div style={{ flex: 1 }} />
        <button
          onClick={toggleFields}
          style={{
            padding: '4px 12px', borderRadius: 6,
            background: showFields ? '#06b6d420' : '#1e2538',
            border: `1px solid ${showFields ? '#06b6d4' : '#2a3350'}`,
            color: showFields ? '#06b6d4' : '#9ca3af',
            fontSize: 11, fontWeight: 600, cursor: 'pointer',
          }}
        >
          {showFields ? 'Hide' : 'Show'} Critical Fields ({stats.critical_fields_traced}/{stats.critical_fields_total})
        </button>
      </div>

      {/* Critical Fields Panel */}
      {showFields && (
        <div style={{
          padding: 12, background: '#111827', borderRadius: 12, border: '1px solid #2a3350',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#9ca3af', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Critical Field Lineage Traceability
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 6 }}>
            {Object.entries(field_coverage).map(([field, info]) => (
              <div key={field} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 10px', borderRadius: 6,
                background: info.traced ? '#10b98108' : '#ef444408',
                border: `1px solid ${info.traced ? '#10b98120' : '#ef444420'}`,
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: info.traced ? '#10b981' : '#ef4444',
                  flexShrink: 0,
                }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#e5e7eb', fontFamily: "'JetBrains Mono', monospace" }}>
                    {field}
                  </div>
                  <div style={{ fontSize: 9, color: '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {info.description}
                  </div>
                </div>
                <div style={{
                  marginLeft: 'auto', fontSize: 9, fontWeight: 600,
                  color: info.traced ? '#10b981' : '#ef4444',
                }}>
                  {info.traced ? `${info.paths.length} path${info.paths.length > 1 ? 's' : ''}` : 'NOT TRACED'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Graph */}
      <div style={{
        width: '100%', height: 700, borderRadius: 12,
        overflow: 'hidden', border: '1px solid #2a3350', background: '#0a0e1a',
      }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2538" />
          <Controls showInteractive={false} />
          <MiniMap
            nodeColor={(n) => {
              const nodeType = (n.data?.nodeType as string) || 'source';
              return NODE_COLORS[nodeType]?.accent || '#6b7280';
            }}
            style={{ background: '#0a0e1a', borderRadius: 8 }}
            maskColor="rgba(0,0,0,0.7)"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
