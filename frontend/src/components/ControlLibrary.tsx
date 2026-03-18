import { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, CheckCircle2, Search,
  ChevronDown, ChevronRight, Database, Loader2, BookOpen,
  Filter, FileCode2, Radar, Download,
} from 'lucide-react';
import type { RagControl, RagComparisonData, AgentDef } from '../types';

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
  const [validating, setValidating] = useState(false);
  const [validationDone, setValidationDone] = useState(false);
  const [ragComparison, setRagComparison] = useState<RagComparisonData | null>(null);
  const [expandedRagSection, setExpandedRagSection] = useState<string | null>(null);
  const [ragSearchTerm, setRagSearchTerm] = useState('');
  const [ragFilterSeverity, setRagFilterSeverity] = useState<string>('all');
  const [ragFilterRegulation, setRagFilterRegulation] = useState<string>('all');
  const [loadingRag, setLoadingRag] = useState(false);

  // RAG comparison is loaded on demand — never auto-fetched
  const loadRagComparison = useCallback(async () => {
    if (pipelineStatus !== 'completed') return;
    setLoadingRag(true);
    try {
      const res = await fetch(`${API_BASE}/api/controls/rag-comparison?system_id=${encodeURIComponent(selectedSystem)}`);
      const data = await res.json();
      setRagComparison(data);
    } catch (e) {
      console.error('Failed to fetch RAG comparison:', e);
    } finally {
      setLoadingRag(false);
    }
  }, [pipelineStatus, selectedSystem]);

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

  // Reset all data when the selected operational system changes
  useEffect(() => {
    setRagComparison(null);
    setValidationDone(false);
  }, [selectedSystem]);

  // Also reset data whenever a new pipeline run starts so the fetched controls
  // always reflect the most recent analysis (not stale data from a prior run)
  useEffect(() => {
    if (pipelineStatus === 'running') {
      setRagComparison(null);
      setValidationDone(false);
    }
  }, [pipelineStatus]);

  // Check FDIC regulatory sections against source code via rag-comparison endpoint
  const validateAgainstRag = useCallback(async () => {
    setValidating(true);
    setLoadingRag(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/controls/rag-comparison?system_id=${encodeURIComponent(selectedSystem)}`
      );
      const data = await res.json();
      setRagComparison(data);
      setValidationDone(true);
    } catch (e) {
      console.error('FDIC section check failed:', e);
    } finally {
      setValidating(false);
      setLoadingRag(false);
    }
  }, [selectedSystem]);

  const foundCount = ragComparison?.found_in_code ?? 0;
  const totalSections = ragComparison?.total_sections ?? 0;

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
                {validationDone
                  ? 'What We Found In Your Code vs What FDIC Requires'
                  : 'What We Found In Your Code'}
              </div>
              <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
                We scanned {layer0Agent.description ?? 'your code'} and automatically extracted{' '}
                <strong style={{ color: '#60a5fa' }}>{layer0Findings.length} compliance parameters</strong>.
                {validationDone
                  ? ' Here is how they compare to FDIC requirements from the regulatory documents.'
                  : <span style={{ color: '#f59e0b' }}> Click <strong>Check Against FDIC Rulebook</strong> below to compare against FDIC requirements.</span>
                }
              </div>
            </div>
            {validationDone && (
              <span style={{
                padding: '3px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.25)',
                color: '#3b82f6',
              }}>
                {layer0Findings.filter(f => f.evidence?.gap).length} gaps found
              </span>
            )}
          </div>

          {/* Table header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: validationDone ? '200px 1fr 1fr 110px' : '200px 1fr',
            gap: 0, padding: '8px 20px',
            background: '#0d1117',
            borderBottom: '1px solid #1a2030',
          }}>
            {(validationDone
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
                    gridTemplateColumns: validationDone ? '200px 1fr 1fr 110px' : '200px 1fr',
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

                  {/* FDIC requires — only after RAG validation */}
                  {validationDone && (
                    <div style={{ paddingRight: 8 }}>
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
                    </div>
                  )}

                  {/* Status pill — only after RAG validation */}
                  {validationDone && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
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
                    </div>
                  )}
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

      {/* ═══ ACTION BAR — Validate + Download ═══ */}
      <div style={{ display: 'flex', gap: 0, background: '#111827', borderRadius: 12, border: '1px solid #2a3350', padding: 4 }}>
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={validateAgainstRag}
          disabled={validating}
          style={{
            flex: 1, padding: '10px 16px', borderRadius: 8,
            background: validationDone
              ? 'linear-gradient(135deg, #10b981, #059669)'
              : 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            border: 'none', color: 'white', fontSize: 13, fontWeight: 700,
            cursor: validating ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            opacity: validating ? 0.7 : 1, transition: 'all 0.2s',
          }}
        >
          {validating ? (
            <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Checking…</>
          ) : validationDone ? (
            <><CheckCircle2 size={14} /> {foundCount}/{totalSections} FDIC Sections in Code</>
          ) : (
            <><Database size={14} /> Check Against FDIC Rulebook</>
          )}
        </motion.button>
        {pipelineStatus === 'completed' && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={downloadReport}
            style={{
              padding: '10px 20px', borderRadius: 8, marginLeft: 4,
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

      {/* ═══ RAG CONTROLS VIEW ═══ */}
      <RagControlsView
          ragComparison={ragComparison}
          expandedSection={expandedRagSection}
          onToggleSection={(s) => setExpandedRagSection(expandedRagSection === s ? null : s)}
          searchTerm={ragSearchTerm}
          onSearchChange={setRagSearchTerm}
          filterSeverity={ragFilterSeverity}
          onSeverityChange={setRagFilterSeverity}
          filterRegulation={ragFilterRegulation}
          onRegulationChange={setRagFilterRegulation}
          onLoad={loadRagComparison}
          loadingRag={loadingRag}
          pipelineCompleted={pipelineStatus === 'completed'}
        />
    </div>
  );
}

function FilterSelect({ value, onChange, options }: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <Filter size={12} style={{ position: 'absolute', left: 8, color: '#6b7280', pointerEvents: 'none' }} />
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          padding: '8px 28px 8px 26px', borderRadius: 8,
          background: '#1e2538', border: '1px solid #2a3350', color: '#e5e7eb',
          fontSize: 11, outline: 'none', appearance: 'none', cursor: 'pointer',
          minWidth: 130,
        }}
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <ChevronDown size={12} style={{ position: 'absolute', right: 8, color: '#6b7280', pointerEvents: 'none' }} />
    </div>
  );
}

/* ── RAG Controls View ───────────────────────────────────────────────────── */

function RagControlsView({
  ragComparison,
  expandedSection,
  onToggleSection,
  searchTerm,
  onSearchChange,
  filterSeverity,
  onSeverityChange,
  filterRegulation,
  onRegulationChange,
  onLoad,
  loadingRag,
  pipelineCompleted,
}: {
  ragComparison: RagComparisonData | null;
  expandedSection: string | null;
  onToggleSection: (s: string) => void;
  searchTerm: string;
  onSearchChange: (s: string) => void;
  filterSeverity: string;
  onSeverityChange: (s: string) => void;
  filterRegulation: string;
  onRegulationChange: (s: string) => void;
  onLoad: () => void;
  loadingRag: boolean;
  pipelineCompleted: boolean;
}) {
  if (!ragComparison) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
        height: 300, background: '#111827', borderRadius: 16, border: '1px solid #2a3350', gap: 16,
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          background: 'linear-gradient(135deg, #8b5cf620, #06b6d420)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: '2px solid #8b5cf640',
        }}>
          <Radar size={28} color="#8b5cf6" />
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#e5e7eb' }}>FDIC Regulatory Coverage</div>
        <div style={{ fontSize: 12, color: '#6b7280', textAlign: 'center', maxWidth: 480, lineHeight: 1.6 }}>
          {pipelineCompleted
            ? 'This view shows FDIC rulebook topics found by reading the actual regulation text — use it to discover if your system is missing coverage for certain chapters.'
            : 'Run the analysis pipeline first, then load this view to see regulatory coverage gaps.'}
        </div>
        {pipelineCompleted && (
          <button
            onClick={onLoad}
            disabled={loadingRag}
            style={{
              padding: '10px 24px', borderRadius: 8, border: '1px solid #8b5cf6',
              background: loadingRag ? '#8b5cf620' : 'linear-gradient(135deg, #8b5cf630, #06b6d420)',
              color: '#8b5cf6', fontSize: 13, fontWeight: 700, cursor: loadingRag ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s',
            }}
          >
            {loadingRag
              ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Loading…</>
              : <><Radar size={14} /> Load Regulatory Coverage</>}
          </button>
        )}
      </div>
    );
  }

  const gapSections: RagControl[] = ragComparison.gap_sections || [];
  const ragSeverities = [...new Set(gapSections.map((c: RagControl) => c.severity))];
  const ragRegulations = [...new Set(gapSections.map((c: RagControl) => c.regulation))];

  const filtered = gapSections.filter((item: RagControl) => {
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      if (
        !item.section.toLowerCase().includes(term) &&
        !item.regulation.toLowerCase().includes(term) &&
        !(item.title ?? '').toLowerCase().includes(term)
      ) return false;
    }
    if (filterSeverity !== 'all' && item.severity !== filterSeverity) return false;
    if (filterRegulation !== 'all' && item.regulation !== filterRegulation) return false;
    return true;
  });

  return (
    <>
      {/* Plain English explanation */}
      <div style={{
        padding: '12px 16px', borderRadius: 10,
        background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.18)',
        fontSize: 12, color: '#9ca3af', lineHeight: 1.7,
      }}>
        <span style={{ color: '#a78bfa', fontWeight: 700 }}>What is this view?</span>
        {'  '}We read every section of the FDIC rulebooks (12 CFR 330, 370, 360.8, the IT Guide) and checked
        whether each section is meaningfully addressed in your source code.
        Sections found in code appear in <span style={{ color: '#10b981', fontWeight: 600 }}>covered</span>{' '}
        — sections not found become{' '}
        <span style={{ color: '#ef4444', fontWeight: 600 }}>gaps</span>{' '}
        your team should review.
      </div>

      {/* Compact summary line */}
      <div style={{
        display: 'flex', gap: 12, flexWrap: 'wrap',
        padding: '10px 16px', borderRadius: 10,
        background: '#111827', border: '1px solid #2a3350',
        fontSize: 12, alignItems: 'center',
      }}>
        <Radar size={14} color="#8b5cf6" />
        <span style={{ color: '#9ca3af' }}>
          <span style={{ color: '#10b981', fontWeight: 700 }}>{ragComparison.found_in_code}</span>/<span style={{ color: '#e5e7eb', fontWeight: 700 }}>{ragComparison.total_sections}</span> FDIC sections in code
        </span>
        <div style={{ width: 1, height: 16, background: '#2a3350' }} />
        <span style={{ color: '#9ca3af' }}>
          <span style={{ color: '#ef4444', fontWeight: 700 }}>{ragComparison.gaps_count}</span> gaps
        </span>
        <div style={{ width: 1, height: 16, background: '#2a3350' }} />
        <span style={{ color: '#9ca3af' }}>
          <span style={{ color: '#a78bfa', fontWeight: 700 }}>{ragComparison.code_coverage_pct}%</span> code coverage
        </span>
        {(['CRITICAL','HIGH','MEDIUM','LOW'] as const)
          .filter(k => (ragComparison.gaps_by_severity?.[k] || 0) > 0)
          .map(k => {
            const c = k === 'CRITICAL' ? '#ef4444' : k === 'HIGH' ? '#f97316' : k === 'MEDIUM' ? '#f59e0b' : '#06b6d4';
            return (
              <span key={k} style={{
                padding: '2px 8px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                background: `${c}15`, border: `1px solid ${c}30`, color: c,
              }}>
                {ragComparison.gaps_by_severity?.[k]} {k}
              </span>
            );
          })}
      </div>

      {/* Section Header */}
      <div style={{
        fontSize: 11, fontWeight: 700, color: '#6b7280', letterSpacing: 1.5,
        textTransform: 'uppercase', paddingBottom: 4,
        borderBottom: '1px solid #2a335050',
      }}>
        FDIC sections not found in your code — {filtered.length} gaps
      </div>

      {/* RAG Coverage Bar */}
      <div style={{
        background: '#111827', borderRadius: 12, border: '1px solid #2a3350', padding: 16,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
          Gaps by risk level — {ragComparison.gaps_count} unaddressed FDIC sections
        </div>
        <div style={{ display: 'flex', gap: 0, borderRadius: 6, overflow: 'hidden', height: 10, marginBottom: 10 }}>
          {[
            { key: 'CRITICAL', color: '#ef4444' },
            { key: 'HIGH', color: '#f97316' },
            { key: 'MEDIUM', color: '#f59e0b' },
            { key: 'LOW', color: '#06b6d4' },
          ].map(({ key, color }) => {
            const count = ragComparison.gaps_by_severity?.[key] || 0;
            const pct = ragComparison.gaps_count > 0 ? (count / ragComparison.gaps_count * 100) : 0;
            return pct > 0 ? (
              <div key={key} style={{ width: `${pct}%`, background: color, minWidth: pct > 0 ? 2 : 0 }} title={`${key}: ${count}`} />
            ) : null;
          })}
        </div>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {[
            { key: 'CRITICAL', color: '#ef4444' },
            { key: 'HIGH', color: '#f97316' },
            { key: 'MEDIUM', color: '#f59e0b' },
            { key: 'LOW', color: '#06b6d4' },
          ].map(({ key, color }) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
              <span style={{ fontSize: 11, color: '#9ca3af' }}>{key}:</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: '#e5e7eb' }}>{ragComparison.gaps_by_severity?.[key] || 0}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Coverage indicator */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        fontSize: 11, color: '#10b981',
        background: '#10b98110', borderRadius: 8, padding: '10px 14px',
        border: '1px solid #10b98125',
      }}>
        <CheckCircle2 size={14} />
        <span>{ragComparison.found_in_code} of {ragComparison.total_sections} FDIC regulatory sections are addressed in your code ({ragComparison.code_coverage_pct}% coverage)</span>
      </div>

      {/* Search / Filter bar */}
      <div style={{
        display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
        padding: 12, background: '#111827', borderRadius: 12, border: '1px solid #2a3350',
      }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: '#6b7280' }} />
          <input
            value={searchTerm}
            onChange={e => onSearchChange(e.target.value)}
            placeholder="Search RAG sections by section ID, regulation..."
            style={{
              width: '100%', padding: '8px 12px 8px 32px', borderRadius: 8,
              background: '#1e2538', border: '1px solid #2a3350', color: '#e5e7eb',
              fontSize: 12, outline: 'none',
            }}
          />
        </div>
        <FilterSelect
          value={filterSeverity}
          onChange={onSeverityChange}
          options={[{ value: 'all', label: 'All Severities' }, ...ragSeverities.map((s: string) => ({ value: s, label: s }))]}
        />
        <FilterSelect
          value={filterRegulation}
          onChange={onRegulationChange}
          options={[{ value: 'all', label: 'All Regulations' }, ...ragRegulations.map((r: string) => ({ value: r, label: r }))]}
        />
      </div>

      {/* Results count */}
      <div style={{ fontSize: 12, color: '#6b7280' }}>
          Showing {filtered.length} of {gapSections.length} gap sections
      </div>

      {/* RAG Control List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <AnimatePresence>
          {filtered.map((item: RagControl, i: number) => (
            <RagControlRow
              key={item.section}
              control={item}
              index={i}
              expanded={expandedSection === item.section}
              onToggle={() => onToggleSection(item.section)}
            />
          ))}
        </AnimatePresence>
      </div>
    </>
  );
}

/* ── RAG Control Row ─────────────────────────────────────────────────────── */

function RagControlRow({ control, index, expanded, onToggle }: {
  control: RagControl;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const sevColor = SEVERITY_COLORS[control.severity] || '#6b7280';
  const refCount = control.code_references?.length || 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.01, duration: 0.2 }}
      style={{
        background: '#1e2538',
        border: `1px solid ${expanded ? '#8b5cf644' : '#2a3350'}`,
        borderRadius: 10,
        overflow: 'hidden',
        transition: 'border-color 0.2s',
      }}
    >
      {/* Header */}
      <div
        onClick={onToggle}
        style={{
          padding: '12px 16px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 12,
        }}
      >
        {/* Expand arrow */}
        <div style={{ color: '#6b7280', minWidth: 16 }}>
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>

        {/* Section ID */}
        <div style={{
          minWidth: 90, fontSize: 12, fontWeight: 700, color: '#8b5cf6',
          fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
        }}>
          §{control.section}
        </div>

        {/* Title + Regulation */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {control.title
            ? <div style={{ fontSize: 13, fontWeight: 600, color: '#e5e7eb', lineHeight: 1.3 }}>
                {control.title}
              </div>
            : null}
          <div style={{ fontSize: 11, color: '#6b7280', marginTop: control.title ? 2 : 0 }}>
            {control.regulation}
          </div>
        </div>

        {/* Gap badge */}
        <div style={{
          padding: '2px 8px', borderRadius: 6,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
          fontSize: 9, fontWeight: 700, color: '#ef4444', letterSpacing: 0.5,
        }}>
          FDIC GAP
        </div>

        {/* Severity badge */}
        <div style={{
          padding: '2px 8px', borderRadius: 6, minWidth: 64, textAlign: 'center',
          background: `${sevColor}12`, border: `1px solid ${sevColor}25`,
          fontSize: 10, fontWeight: 700, color: sevColor,
        }}>
          {control.severity}
        </div>

        {/* Code references count */}
        <div style={{
          padding: '2px 8px', borderRadius: 6,
          background: refCount > 0 ? 'rgba(59,130,246,0.1)' : 'rgba(107,114,128,0.1)',
          border: `1px solid ${refCount > 0 ? 'rgba(59,130,246,0.25)' : 'rgba(107,114,128,0.25)'}`,
          fontSize: 10, fontWeight: 600,
          color: refCount > 0 ? '#3b82f6' : '#6b7280',
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <FileCode2 size={11} />
          {refCount} refs
        </div>
      </div>

      {/* Expanded detail — code references */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              borderTop: '1px solid #2a3350', padding: '14px 16px 14px 44px',
              display: 'flex', flexDirection: 'column', gap: 10,
            }}>
              {/* Section info */}
              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 11 }}>
                <div>
                  <span style={{ color: '#6b7280' }}>Regulation: </span>
                  <span style={{ color: '#8b5cf6', fontWeight: 600 }}>{control.regulation}</span>
                </div>
                <div>
                  <span style={{ color: '#6b7280' }}>Section: </span>
                  <span style={{ color: '#3b82f6', fontWeight: 600 }}>{control.section}</span>
                </div>
                <div>
                  <span style={{ color: '#6b7280' }}>Source: </span>
                  <span style={{ color: '#10b981', fontWeight: 600 }}>FDIC Document Analysis</span>
                </div>
              </div>

              {/* What this section requires */}
              {control.description && (
                <div style={{
                  padding: '8px 12px', borderRadius: 8,
                  background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.15)',
                  fontSize: 11, color: '#c4b5fd', lineHeight: 1.6,
                }}>
                  <span style={{ fontWeight: 700, color: '#a78bfa', marginRight: 6 }}>What this requires:</span>
                  {control.description}
                </div>
              )}

              {/* Code References */}
              {refCount > 0 ? (
                <div>
                  <div style={{
                    fontSize: 10, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase',
                    letterSpacing: 1, marginBottom: 8,
                  }}>
                    Code References ({refCount} files)
                  </div>
                  <div style={{
                    display: 'flex', flexDirection: 'column', gap: 4,
                    maxHeight: 300, overflowY: 'auto',
                  }}>
                    {control.code_references.map((ref, j) => (
                      <div key={j} style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '6px 10px', borderRadius: 6,
                        background: '#0d1117', border: '1px solid #1e2538',
                        fontSize: 11,
                      }}>
                        <FileCode2 size={12} color="#3b82f6" />
                        <span style={{
                          color: '#3b82f6', fontWeight: 600,
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {ref.file}
                        </span>
                        <span style={{ color: '#6b7280', fontSize: 10 }}>L{ref.line}</span>
                        {ref.text && (
                          <span style={{
                            color: '#9ca3af', fontSize: 10, flex: 1,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {ref.text}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{
                  padding: '10px 14px', borderRadius: 8,
                  background: 'rgba(107,114,128,0.06)', border: '1px solid rgba(107,114,128,0.2)',
                  fontSize: 11, color: '#6b7280', fontStyle: 'italic',
                }}>
                  RAG context only — no direct code references found
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
