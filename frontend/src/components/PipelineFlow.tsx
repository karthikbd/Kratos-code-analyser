import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AgentNode } from './AgentNode';
import type { AgentDef } from '../types';

const nodeTypes = { agentNode: AgentNode };

interface Props {
  agents: AgentDef[];
}

export function PipelineFlow({ agents }: Props) {
  const defaultAgents: AgentDef[] = useMemo(() => [
    { id: 'layer1', name: 'ORC Static Analyzer', layer: 1, description: '', regulation: '12 CFR Part 330 / IT Guide Section 4', status: 'idle', findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
    { id: 'layer2', name: 'Data Completeness Validator', layer: 2, description: '', regulation: 'IT Guide Sections 2.3.2-2.3.3', status: 'idle', findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
    { id: 'layer3', name: 'Calculation Engine Verifier', layer: 3, description: '', regulation: 'Compliance Manual Sections 6, 10', status: 'idle', findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
    { id: 'layer4', name: 'Output Pipeline Inspector', layer: 4, description: '', regulation: 'IT Guide Section 5 / Appendix A', status: 'idle', findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
    { id: 'layer5', name: 'Behavioral Compliance Tester', layer: 5, description: '', regulation: 'Compliance Manual Sections 4, 5', status: 'idle', findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
    { id: 'layer6', name: 'Certification Generator', layer: 6, description: '', regulation: '12 CFR 370.10(a) / Appendix B', status: 'idle', findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
    { id: 'layer7', name: 'Data Lineage Tracer', layer: 7, description: '', regulation: '12 CFR 370.3(b) / IT Guide §§2.1, 5.1-5.4', status: 'idle', findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
  ], []);

  const agentData = agents.length > 0 ? agents : defaultAgents;

  // Layout: single vertical column — each node stacked with generous spacing
  const nodes: Node[] = useMemo(() => {
    const centerX = 200;
    const rowGap = 160;
    const startY = 30;

    return agentData.map((agent, i) => ({
      id: agent.id,
      type: 'agentNode',
      position: {
        x: centerX,
        y: startY + i * rowGap,
      },
      data: { agent },
    }));
  }, [agentData]);

  const edges: Edge[] = useMemo(() => {
    const edgeList: Edge[] = [];
    for (let i = 0; i < agentData.length - 1; i++) {
      const curr = agentData[i];
      const next = agentData[i + 1];

      let color = '#2a3350';
      let animated = false;
      if (curr.status === 'completed' && next.status === 'running') {
        color = '#3b82f6';
        animated = true;
      } else if (curr.status === 'completed') {
        color = '#10b981';
      } else if (curr.status === 'running') {
        color = '#3b82f6';
        animated = true;
      }

      edgeList.push({
        id: `${curr.id}-${next.id}`,
        source: curr.id,
        target: next.id,
        type: 'smoothstep',
        animated,
        style: { stroke: color, strokeWidth: 2 },
      });
    }
    return edgeList;
  }, [agentData]);

  return (
    <div style={{ width: '100%', height: 1210, borderRadius: 12, overflow: 'hidden', border: '1px solid #2a3350', background: '#0a0e1a' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2538" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            const status = (n.data?.agent as AgentDef)?.status;
            if (status === 'running') return '#3b82f6';
            if (status === 'completed') return '#10b981';
            if (status === 'failed') return '#ef4444';
            return '#2a3350';
          }}
          maskColor="rgba(10,14,26,0.8)"
        />
      </ReactFlow>
    </div>
  );
}
