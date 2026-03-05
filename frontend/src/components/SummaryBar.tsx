import { motion, AnimatePresence } from 'framer-motion';
import { Shield, CheckCircle2 } from 'lucide-react';
import type { PipelineSummary } from '../types';

interface Props {
  summary: PipelineSummary | null;
  status: string;
  ragStatus: string;
  ragChunks: number;
  totalFindings: number;
  connected: boolean;
}

export function SummaryBar({ summary, status, ragStatus, ragChunks, totalFindings, connected }: Props) {
  const verdictColor = summary?.verdict === 'PASS' ? '#10b981' : summary?.verdict === 'REVIEW' ? '#f59e0b' : '#ef4444';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Top Status Row */}
      <div style={{
        display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
        padding: '12px 20px',
        background: '#111827',
        borderRadius: 12,
        border: '1px solid #2a3350',
      }}>
        {/* Connection status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? '#10b981' : '#ef4444',
            boxShadow: connected ? '0 0 6px #10b981' : '0 0 6px #ef4444',
          }} />
          <span style={{ fontSize: 12, color: '#9ca3af' }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        <div style={{ width: 1, height: 20, background: '#2a3350' }} />

        {/* RAG status */}
        <div style={{ fontSize: 12, color: '#9ca3af' }}>
          RAG: <span style={{
            color: ragStatus === 'ready' ? '#10b981' : ragStatus === 'building' ? '#3b82f6' : '#6b7280',
            fontWeight: 600,
          }}>
            {ragStatus === 'ready' ? `Ready (${ragChunks} chunks)` : ragStatus === 'building' ? 'Building index...' : ragStatus}
          </span>
        </div>

        <div style={{ width: 1, height: 20, background: '#2a3350' }} />

        {/* Pipeline status */}
        <div style={{ fontSize: 12, color: '#9ca3af' }}>
          Pipeline: <span style={{
            color: status === 'running' ? '#3b82f6' : status === 'completed' ? '#10b981' : '#6b7280',
            fontWeight: 600,
          }}>
            {status === 'running' ? 'Running...' : status === 'completed' ? 'Complete' : 'Idle'}
          </span>
        </div>

        {/* Findings counter */}
        {totalFindings > 0 && (
          <>
            <div style={{ width: 1, height: 20, background: '#2a3350' }} />
            <div style={{ fontSize: 12, color: '#9ca3af' }}>
              Findings: <span style={{ color: '#e5e7eb', fontWeight: 700 }}>{totalFindings}</span>
            </div>
          </>
        )}

        {/* Verdict */}
        <AnimatePresence>
          {summary && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{ marginLeft: 'auto', display: 'flex', gap: 16, alignItems: 'center' }}
            >
              <div style={{ fontSize: 12, color: '#9ca3af' }}>
                Critical: <span style={{ color: '#ef4444', fontWeight: 700 }}>{summary.critical}</span>
              </div>
              <div style={{ fontSize: 12, color: '#9ca3af' }}>
                High: <span style={{ color: '#f97316', fontWeight: 700 }}>{summary.high}</span>
              </div>
              <div style={{ fontSize: 12, color: '#9ca3af' }}>
                Medium: <span style={{ color: '#f59e0b', fontWeight: 700 }}>{summary.medium}</span>
              </div>
              <div style={{ fontSize: 12, color: '#9ca3af' }}>
                Low: <span style={{ color: '#06b6d4', fontWeight: 700 }}>{summary.low}</span>
              </div>
              <div style={{
                padding: '4px 16px', borderRadius: 20,
                background: `${verdictColor}15`,
                border: `2px solid ${verdictColor}`,
                fontWeight: 800, fontSize: 13, color: verdictColor,
                letterSpacing: 1,
              }}>
                {summary.verdict}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Controls Pass/Fail Tally Row — only after pipeline completes */}
      <AnimatePresence>
        {summary && summary.total_controls > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
              padding: '10px 20px',
              background: 'linear-gradient(135deg, rgba(17,24,39,0.95), rgba(30,37,56,0.95))',
              borderRadius: 12,
              border: '1px solid #2a3350',
            }}
          >
            <Shield size={14} color="#3b82f6" />
            <span style={{ fontSize: 12, fontWeight: 700, color: '#9ca3af', letterSpacing: 0.5 }}>
              CONTROLS TALLY:
            </span>
            <div style={{ width: 1, height: 20, background: '#2a3350' }} />

            <div style={{ fontSize: 12, color: '#9ca3af' }}>
              Total: <span style={{ color: '#e5e7eb', fontWeight: 700 }}>{summary.total_controls}</span>
            </div>
            <div style={{ width: 1, height: 16, background: '#2a3350' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <CheckCircle2 size={13} color="#10b981" />
              <span style={{ fontSize: 12, color: '#10b981', fontWeight: 700 }}>{summary.controls_passed} Compliant</span>
            </div>
            <div style={{ width: 1, height: 16, background: '#2a3350' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 12, color: '#ef4444', fontWeight: 700 }}>{summary.controls_failed} with Findings</span>
            </div>
            <div style={{ width: 1, height: 16, background: '#2a3350' }} />

            {/* Mini bar showing pass/fail ratio */}
            <div style={{
              flex: 1, minWidth: 120, height: 8, borderRadius: 4,
              background: '#1e2538', overflow: 'hidden',
              display: 'flex',
            }}>
              <div style={{
                width: `${summary.total_controls > 0 ? (summary.controls_passed / summary.total_controls * 100) : 0}%`,
                background: 'linear-gradient(90deg, #10b981, #059669)',
                borderRadius: '4px 0 0 4px',
                transition: 'width 0.5s ease',
              }} />
              <div style={{
                flex: 1,
                background: 'linear-gradient(90deg, #ef4444, #dc2626)',
                borderRadius: '0 4px 4px 0',
              }} />
            </div>
            <span style={{ fontSize: 11, color: '#6b7280' }}>
              {summary.total_controls > 0 ? Math.round(summary.controls_passed / summary.total_controls * 100) : 0}% compliant
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
