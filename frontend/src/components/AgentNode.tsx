import { memo, useMemo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { motion } from 'framer-motion';
import { Shield, AlertTriangle, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import type { AgentDef } from '../types';

/** Custom React Flow node representing a single analyzer agent */
function AgentNodeInner({ data }: NodeProps) {
  const agent = data.agent as AgentDef;
  const status = agent.status;

  const statusConfig = useMemo(() => {
    switch (status) {
      case 'running':
        return { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)', icon: Loader2, label: 'Analyzing...' };
      case 'completed':
        return { color: '#10b981', bg: 'rgba(16,185,129,0.12)', icon: CheckCircle, label: 'Complete' };
      case 'failed':
        return { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', icon: XCircle, label: 'Failed' };
      default:
        return { color: '#6b7280', bg: 'rgba(107,114,128,0.08)', icon: Shield, label: 'Waiting' };
    }
  }, [status]);

  const totalFindings = Object.values(agent.finding_counts || {}).reduce((a, b) => a + b, 0);
  const critCount = agent.finding_counts?.CRITICAL || 0;
  const highCount = agent.finding_counts?.HIGH || 0;

  const StatusIcon = statusConfig.icon;

  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{
        scale: 1,
        opacity: 1,
        boxShadow: status === 'running'
          ? ['0 0 8px rgba(59,130,246,0.3)', '0 0 24px rgba(59,130,246,0.6)', '0 0 8px rgba(59,130,246,0.3)']
          : '0 2px 8px rgba(0,0,0,0.3)',
      }}
      transition={status === 'running' ? { boxShadow: { repeat: Infinity, duration: 1.5 } } : { duration: 0.4 }}
      style={{
        background: statusConfig.bg,
        border: `2px solid ${statusConfig.color}`,
        borderRadius: 12,
        padding: '16px 20px',
        minWidth: 260,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Scan line animation when running */}
      {status === 'running' && (
        <motion.div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 2,
            background: `linear-gradient(90deg, transparent, ${statusConfig.color}, transparent)`,
          }}
          animate={{ top: ['0%', '100%'] }}
          transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
        />
      )}

      <Handle type="target" position={Position.Top} style={{ background: statusConfig.color, width: 10, height: 10, border: '2px solid #1e2538' }} />
      <Handle type="source" position={Position.Bottom} style={{ background: statusConfig.color, width: 10, height: 10, border: '2px solid #1e2538' }} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: `linear-gradient(135deg, ${statusConfig.color}22, ${statusConfig.color}44)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <StatusIcon
            size={18}
            color={statusConfig.color}
            className={status === 'running' ? 'animate-spin' : ''}
            style={status === 'running' ? { animation: 'spin 1s linear infinite' } : {}}
          />
        </div>
        <div>
          <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase' }}>
            Layer {agent.layer}
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#e5e7eb' }}>
            {agent.name}
          </div>
        </div>
      </div>

      {/* Regulation reference */}
      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8, lineHeight: 1.3 }}>
        {agent.regulation}
      </div>

      {/* Status bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12 }}>
        <span style={{ color: statusConfig.color, fontWeight: 600 }}>
          {statusConfig.label}
        </span>
        {status === 'completed' && (
          <div style={{ display: 'flex', gap: 8 }}>
            {critCount > 0 && (
              <span style={{ color: '#ef4444', fontWeight: 700 }}>
                {critCount} CRIT
              </span>
            )}
            {highCount > 0 && (
              <span style={{ color: '#f97316', fontWeight: 700 }}>
                {highCount} HIGH
              </span>
            )}
            <span style={{ color: '#9ca3af' }}>
              {totalFindings} total
            </span>
          </div>
        )}
        {status === 'completed' && agent.duration_ms > 0 && (
          <span style={{ color: '#6b7280', fontSize: 10 }}>
            {agent.duration_ms}ms
          </span>
        )}
      </div>
    </motion.div>
  );
}

export const AgentNode = memo(AgentNodeInner);
