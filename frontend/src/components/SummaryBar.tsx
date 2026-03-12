import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertTriangle, XCircle, Wifi, WifiOff, Database, Activity } from 'lucide-react';
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

      {/* ── Findings summary — only after analysis completes ─────────── */}
      <AnimatePresence>
        {summary && isDone && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              background: 'linear-gradient(135deg, #0f1628, #111827)',
              borderRadius: 12, border: '1px solid #2a3350',
              overflow: 'hidden',
            }}
          >
            {/* Plain-language headline based on actual code findings */}
            <div style={{
              padding: '12px 20px 6px',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              {summary.total === 0
                ? <CheckCircle2 size={15} color="#10b981" />
                : <AlertTriangle size={15} color="#f59e0b" />}
              <span style={{ fontSize: 13, fontWeight: 700, color: '#e5e7eb' }}>
                {summary.total === 0
                  ? <span>Code scan detected <span style={{ color: '#10b981' }}>no compliance issues</span> in your system.</span>
                  : <>
                      Code scan found{' '}
                      <span style={{ color: '#f59e0b' }}>{summary.total} compliance issue{summary.total !== 1 ? 's' : ''}</span>
                      {' '}in your system — see the{' '}
                      <span style={{ color: '#60a5fa' }}>Compliance Report</span> tab for evidence details,
                      and the <span style={{ color: '#8b5cf6' }}>FDIC Checklist</span> tab for regulatory coverage.
                    </>
                }
              </span>
            </div>

            {/* Severity pills — based on actual agent findings */}
            {summary.total > 0 && (
              <div style={{ padding: '4px 20px 12px' }}>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {[
                    { label: 'Critical', val: summary.critical, color: '#ef4444', Icon: XCircle },
                    { label: 'High',     val: summary.high,     color: '#f97316', Icon: AlertTriangle },
                    { label: 'Medium',   val: summary.medium,   color: '#f59e0b', Icon: AlertTriangle },
                    { label: 'Low',      val: summary.low,      color: '#06b6d4', Icon: AlertTriangle },
                  ].filter(s => s.val > 0).map(({ label, val, color, Icon }) => (
                    <span key={label} style={{
                      padding: '2px 10px', borderRadius: 10, fontSize: 11,
                      background: `${color}15`, border: `1px solid ${color}30`,
                      color, fontWeight: 600,
                      display: 'flex', alignItems: 'center', gap: 4,
                    }}>
                      <Icon size={11} />
                      {val} {label}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
