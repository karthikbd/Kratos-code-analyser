import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Wifi, WifiOff, Database, Activity } from 'lucide-react';
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
  const isRunning = status === 'running';
  const isDone    = status === 'completed';

  const verdictColor =
    summary?.verdict === 'PASS'   ? '#10b981' :
    summary?.verdict === 'REVIEW' ? '#f59e0b' : '#ef4444';

  const verdictLabel =
    summary?.verdict === 'PASS'   ? '✅  COMPLIANT' :
    summary?.verdict === 'REVIEW' ? '⚠️  NEEDS REVIEW' :
    summary?.verdict === 'FAIL'   ? '❌  NON-COMPLIANT' : '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

      {/* ── Top status ribbon ──────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
        padding: '10px 20px',
        background: '#111827', borderRadius: 12, border: '1px solid #2a3350',
        fontSize: 12,
      }}>
        {/* Connection dot */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {connected
            ? <Wifi size={13} color="#10b981" />
            : <WifiOff size={13} color="#ef4444" />}
          <span style={{ color: connected ? '#10b981' : '#ef4444', fontWeight: 600 }}>
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>

        <div style={{ width: 1, height: 18, background: '#2a3350' }} />

        {/* RAG — plain-language label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Database size={12} color="#8b5cf6" />
          <span style={{ color: '#9ca3af' }}>
            FDIC Docs:{' '}
            <span style={{
              color: ragStatus === 'ready' ? '#10b981' : ragStatus === 'building' ? '#60a5fa' : '#6b7280',
              fontWeight: 600,
            }}>
              {ragStatus === 'ready'
                ? `${ragChunks} regulation sections ready`
                : ragStatus === 'building' ? 'Loading regulation text…' : 'Not loaded'}
            </span>
          </span>
        </div>

        <div style={{ width: 1, height: 18, background: '#2a3350' }} />

        {/* Pipeline — plain language */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Activity size={12} color={isRunning ? '#3b82f6' : isDone ? '#10b981' : '#6b7280'} />
          <span style={{ color: '#9ca3af' }}>
            Scan:{' '}
            <span style={{
              color: isRunning ? '#60a5fa' : isDone ? '#10b981' : '#6b7280',
              fontWeight: 600,
            }}>
              {isRunning ? 'Analyzing your code…' : isDone ? 'Analysis complete' : 'Ready'}
            </span>
          </span>
        </div>

        {/* Live counter while running */}
        {isRunning && totalFindings > 0 && (
          <>
            <div style={{ width: 1, height: 18, background: '#2a3350' }} />
            <span style={{ color: '#f59e0b', fontWeight: 700 }}>
              {totalFindings} issues found so far…
            </span>
          </>
        )}

        {/* Verdict pill — right-aligned */}
        {summary && (
          <div style={{ marginLeft: 'auto' }}>
            <span style={{
              padding: '4px 18px', borderRadius: 20,
              background: `${verdictColor}18`, border: `2px solid ${verdictColor}`,
              fontWeight: 800, fontSize: 13, color: verdictColor, letterSpacing: 0.5,
            }}>
              {verdictLabel || summary.verdict}
            </span>
          </div>
        )}
      </div>

      {/* ── Post-scan guidance — only after analysis completes ──────── */}
      <AnimatePresence>
        {summary && isDone && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              background: 'linear-gradient(135deg, #0f1628, #111827)',
              borderRadius: 12, border: '1px solid #2a3350',
              padding: '10px 20px',
              display: 'flex', alignItems: 'center', gap: 10,
            }}
          >
            <CheckCircle2 size={14} color="#10b981" />
            <span style={{ fontSize: 12, color: '#9ca3af' }}>
              Pipeline analysis complete. Open the{' '}
              <strong style={{ color: '#e5e7eb' }}>Compliance Report</strong> tab, then click{' '}
              <strong style={{ color: '#8b5cf6' }}>Check Against FDIC Rulebook</strong>{' '}
              to compare extracted code values against FDIC-required thresholds from the regulatory documents.
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
