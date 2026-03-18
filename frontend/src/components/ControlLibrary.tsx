import { useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  Loader2, BookOpen,
  FileCode2, Download, GitCompare,
} from 'lucide-react';
import type { AgentDef } from '../types';

const API_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws')
  .replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#06b6d4',
};

interface ControlLibraryProps {
  pipelineStatus: string;
  selectedSystem: string;
  /** Layer 0 agent output — used to show "what we found in code vs FDIC requirement" table */
  agents?: AgentDef[];
}

export function ControlLibrary({ pipelineStatus, selectedSystem, agents = [] }: ControlLibraryProps) {
  const [compared, setCompared] = useState(false);

  // Download full compliance report as JSON
  const downloadReport = useCallback(() => {
    if (!selectedSystem) return;
    const url = `${API_BASE}/api/report/${encodeURIComponent(selectedSystem)}`;
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `kratos_report_${selectedSystem}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [selectedSystem]);

  // Show "waiting for analysis" when pipeline hasn't run yet
  if (pipelineStatus === 'idle') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
          height: 400, background: '#111827', borderRadius: 16, border: '1px solid #2a3350',
          gap: 16,
        }}
      >
        <div style={{
          width: 72, height: 72, borderRadius: '50%',
          background: 'linear-gradient(135deg, #3b82f620, #8b5cf620)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: '2px solid #3b82f640',
        }}>
          <BookOpen size={32} color="#3b82f6" />
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#e5e7eb' }}>Compliance Report</div>
        <div style={{ fontSize: 13, color: '#6b7280', textAlign: 'center', maxWidth: 420, lineHeight: 1.6 }}>
          Run the AI analysis to check your system's code against FDIC compliance rules.
          Results will appear here with a breakdown of what passed and what needs attention.
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 12, color: '#3b82f6', background: '#3b82f610',
          padding: '8px 16px', borderRadius: 8, border: '1px solid #3b82f630',
        }}>
          <Shield size={14} />
          <span>Click <strong>Analyze</strong> above to start</span>
        </div>
      </motion.div>
    );
  }

  // Show spinner during analysis
  if (pipelineStatus === 'running') {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        style={{
          display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
          height: 400, background: '#111827', borderRadius: 16, border: '1px solid #2a3350',
          gap: 16,
        }}
      >
        <Loader2 size={40} color="#8b5cf6" style={{ animation: 'spin 1s linear infinite' }} />
        <div style={{ fontSize: 16, fontWeight: 700, color: '#e5e7eb' }}>Analysis in Progress</div>
        <div style={{ fontSize: 12, color: '#6b7280' }}>
          AI agents are scanning source code against FDIC Part 370 regulatory controls...
        </div>
      </motion.div>
    );
  }

  // ── Extract Layer 0 evidence findings ──────────────────────────────
  const layer0Agent = agents.find(a => a.id === 'layer0' || a.layer === 0);
  const layer0Findings = (layer0Agent?.findings ?? []).filter(
    f => f.evidence && (f.evidence.code_value !== undefined || f.evidence.required_value !== undefined)
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ═══ LAYER 0 EVIDENCE BOX — What we found in code vs FDIC requirement ═══ */}
      {layer0Agent && layer0Agent.status !== 'skipped' && layer0Findings.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, #0a0f1e, #111827)',
          borderRadius: 14, border: '2px solid #2a3350',
          overflow: 'hidden',
        }}>
          {/* Header */}
          <div style={{
            padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 12,
            borderBottom: '1px solid #2a3350',
            background: 'linear-gradient(90deg, rgba(59,130,246,0.08), rgba(139,92,246,0.04))',
          }}>
            <FileCode2 size={18} color="#3b82f6" />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: '#e5e7eb' }}>
                What We Found In Your Code vs What FDIC Requires
              </div>
              <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
                We scanned {layer0Agent.description ?? 'your code'} and automatically extracted{' '}
                <strong style={{ color: '#60a5fa' }}>{layer0Findings.length} compliance parameters</strong>.{' '}
                Here is how they compare to FDIC requirements from the regulatory documents.
              </div>
            </div>
            {compared ? (
              <span style={{
                padding: '3px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.25)',
                color: '#3b82f6',
              }}>
                {layer0Findings.filter(f => f.evidence?.gap).length} gaps found
              </span>
            ) : (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => setCompared(true)}
                style={{
                  padding: '6px 14px', borderRadius: 8,
                  background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                  border: 'none', color: 'white', fontSize: 12, fontWeight: 700,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                  whiteSpace: 'nowrap',
                }}
              >
                <GitCompare size={13} /> Compare Against FDIC
              </motion.button>
            )}
          </div>

          {/* Table header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: compared ? '200px 1fr 1fr 110px' : '200px 1fr',
            gap: 0, padding: '8px 20px',
            background: '#0d1117',
            borderBottom: '1px solid #1a2030',
          }}>
            {(compared
              ? ["WHAT WE'RE CHECKING", 'FOUND IN YOUR CODE', 'FDIC REQUIRES', 'STATUS']
              : ["WHAT WE'RE CHECKING", 'FOUND IN YOUR CODE']
            ).map(h => (
              <span key={h} style={{ fontSize: 10, fontWeight: 700, color: '#4b5563', letterSpacing: 1 }}>{h}</span>
            ))}
          </div>

          {/* Rows */}
          <div style={{ maxHeight: 420, overflowY: 'auto' }}>
            {layer0Findings.map((f, idx) => {
              const ev = f.evidence ?? {};
              const hasGap = !!ev.gap;
              const sev = f.severity ?? 'INFO';
              const sevColor = SEVERITY_COLORS[sev] ?? '#6b7280';
              const paramLabel = (ev.parameter ?? f.title ?? 'Unknown')
                .replace(/_/g, ' ')
                .replace(/\b\w/g, (c: string) => c.toUpperCase());
              return (
                <div
                  key={idx}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: compared ? '200px 1fr 1fr 110px' : '200px 1fr',
                    gap: 0, padding: '10px 20px',
                    borderBottom: '1px solid #1a2030',
                    background: idx % 2 === 0 ? 'transparent' : '#0d111a',
                    alignItems: 'start',
                  }}
                >
                  {/* What we're checking */}
                  <div style={{ paddingRight: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#d1d5db' }}>{paramLabel}</div>
                    {ev.code_file && (
                      <div style={{ fontSize: 10, color: '#4b5563', marginTop: 2, fontFamily: 'monospace' }}>
                        {ev.code_file}{ev.code_line ? `:${ev.code_line}` : ''}
                      </div>
                    )}
                    {f.cfr_reference && (
                      <div style={{ fontSize: 10, color: '#8b5cf6', marginTop: 2 }}>{f.cfr_reference}</div>
                    )}
                  </div>

                  {/* Found in code */}
                  <div style={{ paddingRight: 8 }}>
                    <span style={{
                      display: 'inline-block',
                      padding: '3px 10px', borderRadius: 6, fontSize: 12, fontWeight: 700,
                      background: 'rgba(59,130,246,0.1)',
                      border: '1px solid rgba(59,130,246,0.25)',
                      color: '#60a5fa',
                      fontFamily: 'monospace',
                    }}>
                      {ev.code_value ?? 'Not found in code'}
                    </span>
                    {ev.code_context && (
                      <div style={{
                        marginTop: 4, fontSize: 10, color: '#4b5563',
                        fontFamily: 'monospace', whiteSpace: 'pre-wrap', maxWidth: 280,
                      }}>
                        {ev.code_context}
                      </div>
                    )}
                  </div>

                  {/* FDIC requires — only after compare */}
                  {compared && <div style={{ paddingRight: 8 }}>
                    <span style={{
                      display: 'inline-block',
                      padding: '3px 10px', borderRadius: 6, fontSize: 12, fontWeight: 700,
                      background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.25)',
                      color: '#10b981', fontFamily: 'monospace',
                    }}>
                      {ev.required_value ?? '—'}
                    </span>
                    {ev.gap && (
                      <div style={{ marginTop: 4, fontSize: 10, color: '#9ca3af', lineHeight: 1.4, maxWidth: 280 }}>
                        {ev.gap}
                      </div>
                    )}
                  </div>}

                  {/* Status pill — only after compare */}
                  {compared && <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                    <span style={{
                      padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 800,
                      background: `${sevColor}18`, border: `1px solid ${sevColor}40`,
                      color: sevColor,
                    }}>
                      {hasGap ? '❌ ' : '✅ '}{hasGap ? sev : 'OK'}
                    </span>
                    {f.remediation_recommendation && (
                      <div style={{ fontSize: 10, color: '#6b7280', lineHeight: 1.4 }}>
                        {f.remediation_recommendation.slice(0, 80)}{f.remediation_recommendation.length > 80 ? '…' : ''}
                      </div>
                    )}
                  </div>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Placeholder if layer0 ran but produced no evidence ─────────── */}
      {layer0Agent && layer0Agent.status === 'completed' && layer0Findings.length === 0 && (
        <div style={{
          padding: '14px 20px', borderRadius: 12,
          background: 'rgba(107,114,128,0.07)', border: '1px solid #2a3350',
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: '#6b7280',
        }}>
          <FileCode2 size={14} color="#6b7280" />
          Code scan completed — no hardcoded FDIC parameter values found in this system.
        </div>
      )}

      {/* ═══ DOWNLOAD REPORT ═══ */}
      {pipelineStatus === 'completed' && (
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={downloadReport}
          style={{
            alignSelf: 'flex-end',
            padding: '10px 20px', borderRadius: 8,
            background: 'linear-gradient(135deg, #0ea5e9, #0284c7)',
            border: 'none', color: 'white', fontSize: 13, fontWeight: 700,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 8,
          }}
        >
          <Download size={14} /> Download Report
        </motion.button>
      )}
    </div>
  );
}

// RAG comparison removed — keyword matcher was unreliable (produced 100% coverage / 0 gaps
// even when Layer 0 found real violations). Layer 0 evidence is the canonical compliance view.

