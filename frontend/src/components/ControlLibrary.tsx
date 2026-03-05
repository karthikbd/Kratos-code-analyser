import { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, CheckCircle2, XCircle, AlertTriangle, Search,
  ChevronDown, ChevronRight, Database, Loader2, BookOpen,
  Filter, FileCode2, Radar, Lock, Download,
} from 'lucide-react';
import type { FDICControl, ControlSummary, ControlValidationResult, RagControl, RagComparisonData } from '../types';

const API_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws')
  .replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#06b6d4',
};

const CATEGORY_COLORS: Record<string, string> = {
  'Recordkeeping': '#3b82f6',
  'ORC Assignment': '#8b5cf6',
  'Data Quality': '#f59e0b',
  'Calculation Engine': '#10b981',
  'Output Files': '#06b6d4',
  'Pending Management': '#f97316',
  'Behavioral / Runtime': '#ec4899',
  'Certification': '#6366f1',
  'ARE Processing': '#14b8a6',
  'Insurance Coverage': '#a855f7',
  'Data Lineage': '#22d3ee',
};

interface ControlLibraryProps {
  pipelineStatus: string;
  selectedSystem: string;
}

export function ControlLibrary({ pipelineStatus, selectedSystem }: ControlLibraryProps) {
  const [controls, setControls] = useState<FDICControl[]>([]);
  const [summary, setSummary] = useState<ControlSummary | null>(null);
  const [validationResults, setValidationResults] = useState<ControlValidationResult[]>([]);
  const [validating, setValidating] = useState(false);
  const [validationDone, setValidationDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterRegulation, setFilterRegulation] = useState<string>('all');
  const [filterLayer, setFilterLayer] = useState<number>(0);
  const [expandedControl, setExpandedControl] = useState<string | null>(null);
  const [ragComparison, setRagComparison] = useState<RagComparisonData | null>(null);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [controlView, setControlView] = useState<'system' | 'rag'>('system');
  const [expandedRagSection, setExpandedRagSection] = useState<string | null>(null);
  const [ragSearchTerm, setRagSearchTerm] = useState('');
  const [ragFilterSeverity, setRagFilterSeverity] = useState<string>('all');
  const [ragFilterRegulation, setRagFilterRegulation] = useState<string>('all');
  const [loadingRag, setLoadingRag] = useState(false);

  // Fetch controls only after pipeline completes
  useEffect(() => {
    if (pipelineStatus !== 'completed' || dataLoaded) return;
    setLoading(true);
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/controls?system_id=${encodeURIComponent(selectedSystem)}`);
        const data = await res.json();
        setControls(data.controls || []);
        setSummary(data.summary || null);
      } catch (e) {
        console.error('Failed to fetch controls:', e);
      } finally {
        setLoading(false);
        setDataLoaded(true);
      }
    })();
  }, [pipelineStatus, dataLoaded]);

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
    setDataLoaded(false);
    setControls([]);
    setSummary(null);
    setRagComparison(null);
    setValidationResults([]);
    setValidationDone(false);
    setControlView('system');
  }, [selectedSystem]);

  // Also reset data whenever a new pipeline run starts so the fetched controls
  // always reflect the most recent analysis (not stale data from a prior run)
  useEffect(() => {
    if (pipelineStatus === 'running') {
      setDataLoaded(false);
      setControls([]);
      setSummary(null);
      setRagComparison(null);
      setValidationResults([]);
      setValidationDone(false);
    }
  }, [pipelineStatus]);

  // Validate against RAG — runs queries in parallel on backend, then auto-loads RAG comparison
  const validateAgainstRag = useCallback(async () => {
    setValidating(true);
    try {
      const res = await fetch(`${API_BASE}/api/controls/validate?system_id=${encodeURIComponent(selectedSystem)}`, { method: 'POST' });
      const data = await res.json();
      setValidationResults(data.results || []);
      setValidationDone(true);
      // Auto-load RAG comparison and switch to RAG tab
      setLoadingRag(true);
      try {
        const ragRes = await fetch(`${API_BASE}/api/controls/rag-comparison?system_id=${encodeURIComponent(selectedSystem)}`);
        const ragData = await ragRes.json();
        setRagComparison(ragData);
        setControlView('rag');
      } catch (ragErr) {
        console.error('Auto RAG comparison load failed:', ragErr);
      } finally {
        setLoadingRag(false);
      }
    } catch (e) {
      console.error('RAG validation failed:', e);
    } finally {
      setValidating(false);
    }
  }, [selectedSystem, pipelineStatus]);

  // Filter controls
  const filtered = controls.filter(c => {
    // Exclude controls marked not applicable after pipeline analysis
    if (c.applicable === false) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      if (!c.control_id.toLowerCase().includes(term) && !c.title.toLowerCase().includes(term) && !c.description.toLowerCase().includes(term) && !c.section.toLowerCase().includes(term))
        return false;
    }
    if (filterCategory !== 'all' && c.category !== filterCategory) return false;
    if (filterRegulation !== 'all' && c.regulation !== filterRegulation) return false;
    if (filterLayer > 0 && c.layer !== filterLayer) return false;
    return true;
  });

  const categories = [...new Set(controls.map(c => c.category))];
  const regulations = [...new Set(controls.map(c => c.regulation))];
  const validatedCount = validationResults.filter(r => r.rag_validated).length;

  // Show "waiting for analysis" when pipeline hasn't run yet
  if (pipelineStatus === 'idle' && !dataLoaded) {
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
        <div style={{ fontSize: 18, fontWeight: 700, color: '#e5e7eb' }}>FDIC Control Library</div>
        <div style={{ fontSize: 13, color: '#6b7280', textAlign: 'center', maxWidth: 420, lineHeight: 1.6 }}>
          Run the AI analysis pipeline to populate the control library with regulatory compliance results,
          severity breakdowns, and RAG coverage data.
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 12, color: '#3b82f6', background: '#3b82f610',
          padding: '8px 16px', borderRadius: 8, border: '1px solid #3b82f630',
        }}>
          <Shield size={14} />
          <span>Click <strong>Analyze Compliance</strong> above to start</span>
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

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
        <Loader2 size={32} color="#3b82f6" style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ marginLeft: 12, color: '#9ca3af' }}>Loading FDIC Control Library...</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Sub-Tab Switcher: System Controls / RAG Controls */}
      <div style={{ display: 'flex', gap: 0, background: '#111827', borderRadius: 12, border: '1px solid #2a3350', padding: 4 }}>
        <button
          onClick={() => setControlView('system')}
          style={{
            flex: 1, padding: '10px 16px', borderRadius: 8, border: 'none',
            background: controlView === 'system' ? 'linear-gradient(135deg, #3b82f620, #8b5cf620)' : 'transparent',
            color: controlView === 'system' ? '#e5e7eb' : '#6b7280',
            fontSize: 13, fontWeight: 700, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            transition: 'all 0.2s',
            borderBottom: controlView === 'system' ? '2px solid #3b82f6' : '2px solid transparent',
          }}
        >
          <Shield size={16} color={controlView === 'system' ? '#3b82f6' : '#6b7280'} />
          System Controls
          {summary && (
            <span style={{
              padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 700,
              background: controlView === 'system' ? '#3b82f620' : '#1e2538',
              color: controlView === 'system' ? '#3b82f6' : '#6b7280',
            }}>
              {summary.total_controls}
            </span>
          )}
        </button>
        {validationDone ? (
          <button
            onClick={() => setControlView('rag')}
            style={{
              flex: 1, padding: '10px 16px', borderRadius: 8, border: 'none',
              background: controlView === 'rag' ? 'linear-gradient(135deg, #8b5cf620, #06b6d420)' : 'transparent',
              color: controlView === 'rag' ? '#e5e7eb' : '#6b7280',
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              transition: 'all 0.2s',
              borderBottom: controlView === 'rag' ? '2px solid #8b5cf6' : '2px solid transparent',
            }}
          >
            <Radar size={16} color={controlView === 'rag' ? '#8b5cf6' : '#6b7280'} />
            RAG Controls
            {ragComparison && (
              <span style={{
                padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 700,
                background: controlView === 'rag' ? '#8b5cf620' : '#1e2538',
                color: controlView === 'rag' ? '#8b5cf6' : '#6b7280',
              }}>
                {ragComparison.rag_only_count}
              </span>
            )}
          </button>
        ) : (
          <div
            title="Run 'Validate Against RAG' in System Controls to unlock this tab"
            style={{
              flex: 1, padding: '10px 16px', borderRadius: 8,
              background: 'transparent', color: '#374151',
              fontSize: 13, fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              borderBottom: '2px solid transparent',
              cursor: 'not-allowed', userSelect: 'none',
            }}
          >
            <Lock size={14} color="#374151" />
            RAG Controls
            <span style={{
              padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
              background: '#1e2538', color: '#4b5563',
            }}>locked</span>
          </div>
        )}
      </div>

      {/* ═══ SYSTEM CONTROLS TAB ═══ */}
      {controlView === 'system' && (<>
      {/* Summary Cards */}
      {summary && (
        <>
          {/* Section Header */}
          <div style={{
            fontSize: 11, fontWeight: 700, color: '#6b7280', letterSpacing: 1.5,
            textTransform: 'uppercase', paddingBottom: 4,
            borderBottom: '1px solid #2a335050',
          }}>
            FDIC Control Library — Regulatory Requirements Inventory
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
            <SummaryCard icon={<Shield size={20} />} label="APPLICABLE" value={summary.total_controls} color="#3b82f6" />
            {controls.some(c => c.analysis_status === 'NOT_APPLICABLE') && (
              <SummaryCard icon={<Shield size={20} />} label="NOT APPLICABLE" value={controls.filter(c => c.analysis_status === 'NOT_APPLICABLE').length} color="#6b7280" />
            )}
            {summary.verdict && (
              <SummaryCard icon={<Shield size={20} />} label="VERDICT" value={summary.verdict} color={summary.verdict === 'PASS' ? '#10b981' : summary.verdict === 'REVIEW' ? '#f59e0b' : '#ef4444'} />
            )}
            <SummaryCard icon={<AlertTriangle size={20} />} label="CRITICAL CONTROLS" value={summary.by_severity?.CRITICAL || 0} color="#ef4444" />
            <SummaryCard icon={<AlertTriangle size={20} />} label="HIGH CONTROLS" value={summary.by_severity?.HIGH || 0} color="#f97316" />
            <SummaryCard icon={<AlertTriangle size={20} />} label="MEDIUM CONTROLS" value={summary.by_severity?.MEDIUM || 0} color="#f59e0b" />
            <SummaryCard icon={<AlertTriangle size={20} />} label="LOW CONTROLS" value={summary.by_severity?.LOW || 0} color="#06b6d4" />
            <SummaryCard icon={<BookOpen size={20} />} label="REGULATIONS" value={Object.keys(summary.by_regulation || {}).length} color="#8b5cf6" />
            <SummaryCard icon={<Database size={20} />} label="CATEGORIES" value={Object.keys(summary.by_category || {}).length} color="#10b981" />
            {validationDone && (
              <SummaryCard
                icon={<CheckCircle2 size={20} />}
                label="RAG VALIDATED"
                value={`${validatedCount}/${validationResults.length}`}
                color={validatedCount === validationResults.length ? '#10b981' : '#f59e0b'}
              />
            )}
          </div>

          {/* Detected System Capabilities */}
          {summary.capabilities && (summary.capabilities.orc_types?.length > 0 || summary.capabilities.features?.length > 0) && (
            <div style={{ background: '#111827', borderRadius: 12, border: '1px solid #2a3350', padding: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
                Detected System Capabilities
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {(summary.capabilities.orc_types || []).map((orc: string) => (
                  <span key={orc} style={{
                    padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.25)', color: '#60a5fa',
                  }}>ORC: {orc}</span>
                ))}
                {(summary.capabilities.features || []).map((feat: string) => (
                  <span key={feat} style={{
                    padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)', color: '#a78bfa',
                  }}>{feat.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
          )}

          {/* Severity Pass/Fail Breakdown Table */}
          <div style={{
            background: '#111827', borderRadius: 12, border: '1px solid #2a3350', padding: 16,
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
              Severity Breakdown — Compliance Status by Risk Level
            </div>
            {/* Header row */}
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 80px 90px 90px', gap: 0,
              borderBottom: '1px solid #2a3350', paddingBottom: 6, marginBottom: 6 }}>
              {['SEVERITY', 'CONTROLS', 'TOTAL', 'COMPLIANT', 'FINDINGS'].map(h => (
                <span key={h} style={{ fontSize: 10, fontWeight: 700, color: '#6b7280', letterSpacing: 1 }}>{h}</span>
              ))}
            </div>
            {[
              { key: 'CRITICAL', color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
              { key: 'HIGH',     color: '#f97316', bg: 'rgba(249,115,22,0.08)' },
              { key: 'MEDIUM',   color: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
              { key: 'LOW',      color: '#06b6d4', bg: 'rgba(6,182,212,0.08)'  },
            ].map(({ key, color, bg }) => {
              const total   = summary.by_severity?.[key] || 0;
              if (total === 0) return null;
              const passed  = controls.filter(c => c.severity?.toUpperCase() === key && c.analysis_status === 'PASS').length;
              const failed  = controls.filter(c => c.severity?.toUpperCase() === key && c.analysis_status === 'FAIL').length;
              const passRatio = total > 0 ? passed / total : 0;
              return (
                <div key={key} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 80px 90px 90px',
                  gap: 0, alignItems: 'center', padding: '8px 0',
                  borderBottom: '1px solid #1a2030' }}>
                  {/* Severity badge */}
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, fontWeight: 700, color }}>{key}</span>
                  </span>
                  {/* Progress bar */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingRight: 12 }}>
                    <div style={{ flex: 1, height: 6, borderRadius: 3, background: '#1f2937', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${passRatio * 100}%`,
                        background: passRatio >= 0.7 ? '#10b981' : passRatio >= 0.4 ? '#f59e0b' : '#ef4444',
                        borderRadius: 3, transition: 'width 0.4s ease' }} />
                    </div>
                    <span style={{ fontSize: 10, color: '#6b7280', whiteSpace: 'nowrap' }}>{Math.round(passRatio * 100)}%</span>
                  </div>
                  {/* Counts */}
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#e5e7eb', background: bg,
                    borderRadius: 4, padding: '2px 8px', textAlign: 'center' }}>{total}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#10b981',
                    background: 'rgba(16,185,129,0.08)', borderRadius: 4, padding: '2px 8px', textAlign: 'center' }}>{passed}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#ef4444',
                    background: 'rgba(239,68,68,0.08)', borderRadius: 4, padding: '2px 8px', textAlign: 'center' }}>{failed}</span>
                </div>
              );
            })}
            {/* Totals footer */}
            {(() => {
              const totalApplicable = summary.total_controls;
              const totalPassed = controls.filter(c => c.analysis_status === 'PASS').length;
              const totalFailed = controls.filter(c => c.analysis_status === 'FAIL').length;
              return (
                <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 80px 90px 90px',
                  gap: 0, alignItems: 'center', paddingTop: 8, borderTop: '1px solid #2a3350', marginTop: 4 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af' }}>TOTAL</span>
                  <div />
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#e5e7eb', textAlign: 'center' }}>{totalApplicable}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#10b981', textAlign: 'center' }}>{totalPassed}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#ef4444', textAlign: 'center' }}>{totalFailed}</span>
                </div>
              );
            })()}
          </div>
        </>
      )}

      {/* Regulation Breakdown Bar */}
      {summary && (
        <div style={{
          background: '#111827', borderRadius: 12, border: '1px solid #2a3350', padding: 16,
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
            Controls by Regulation
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {Object.entries(summary.by_regulation || {}).map(([reg, count]) => (
              <div key={reg} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 12, height: 12, borderRadius: 3, background: reg.includes('370') ? '#3b82f6' : reg.includes('330') ? '#8b5cf6' : reg.includes('IT') ? '#10b981' : '#6b7280' }} />
                <span style={{ fontSize: 12, color: '#e5e7eb' }}>{reg}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#e5e7eb' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search / Filter / Validate Controls */}
      <div style={{
        display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
        padding: 12, background: '#111827', borderRadius: 12, border: '1px solid #2a3350',
      }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: '#6b7280' }} />
          <input
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            placeholder="Search controls by ID, title, description..."
            style={{
              width: '100%', padding: '8px 12px 8px 32px', borderRadius: 8,
              background: '#1e2538', border: '1px solid #2a3350', color: '#e5e7eb',
              fontSize: 12, outline: 'none',
            }}
          />
        </div>

        <FilterSelect
          value={filterCategory}
          onChange={setFilterCategory}
          options={[{ value: 'all', label: 'All Categories' }, ...categories.map(c => ({ value: c, label: c }))]}
        />
        <FilterSelect
          value={filterRegulation}
          onChange={setFilterRegulation}
          options={[{ value: 'all', label: 'All Regulations' }, ...regulations.map(r => ({ value: r, label: r }))]}
        />
        <FilterSelect
          value={String(filterLayer)}
          onChange={v => setFilterLayer(Number(v))}
          options={[{ value: '0', label: 'All Layers' }, ...([1,2,3,4,5,6,7].map(l => ({ value: String(l), label: `Layer ${l}` })))]}
        />

        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={validateAgainstRag}
          disabled={validating}
          style={{
            padding: '8px 16px', borderRadius: 8,
            background: validationDone
              ? 'linear-gradient(135deg, #10b981, #059669)'
              : 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            border: 'none', color: 'white', fontSize: 12, fontWeight: 700,
            cursor: validating ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 6,
            opacity: validating ? 0.7 : 1,
          }}
        >
          {validating ? (
            <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Validating...</>
          ) : validationDone ? (
            <><CheckCircle2 size={14} /> {validatedCount}/{validationResults.length} Validated</>
          ) : (
            <><Database size={14} /> Validate Against RAG</>
          )}
        </motion.button>

        {/* Download Report button — active once pipeline has run */}
        {pipelineStatus === 'completed' && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={downloadReport}
            style={{
              padding: '8px 16px', borderRadius: 8,
              background: 'linear-gradient(135deg, #0ea5e9, #0284c7)',
              border: 'none', color: 'white', fontSize: 12, fontWeight: 700,
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Download size={14} /> Download Report
          </motion.button>
        )}
      </div>

      {/* Results count */}
      <div style={{ fontSize: 12, color: '#6b7280' }}>
        Showing {filtered.length} of {summary ? summary.total_controls : controls.length} controls
      </div>

      {/* Control List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <AnimatePresence>
          {filtered.map((ctrl, i) => {
            const ragResult = validationResults.find(r => r.control_id === ctrl.control_id);
            return (
              <ControlRow
                key={ctrl.control_id}
                control={ctrl}
                ragResult={ragResult}
                index={i}
                expanded={expandedControl === ctrl.control_id}
                onToggle={() => setExpandedControl(
                  expandedControl === ctrl.control_id ? null : ctrl.control_id
                )}
              />
            );
          })}
        </AnimatePresence>
      </div>
      </>)}

      {/* ═══ RAG CONTROLS TAB ═══ */}
      {controlView === 'rag' && (
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
      )}
    </div>
  );
}

/* ── Sub-Components ──────────────────────────────────────────────────────── */

function SummaryCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number | string; color: string }) {
  return (
    <div style={{
      background: '#111827', borderRadius: 10, border: '1px solid #2a3350', padding: '14px 16px',
      display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: `${color}15`, border: `1px solid ${color}30`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', color,
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#e5e7eb' }}>{value}</div>
        <div style={{ fontSize: 10, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.8 }}>{label}</div>
      </div>
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

function ControlRow({ control, ragResult, index, expanded, onToggle }: {
  control: FDICControl;
  ragResult?: ControlValidationResult;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const catColor = CATEGORY_COLORS[control.category] || '#6b7280';
  const sevColor = SEVERITY_COLORS[control.severity] || '#6b7280';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.015, duration: 0.25 }}
      style={{
        background: '#1e2538',
        border: `1px solid ${expanded ? '#3b82f644' : '#2a3350'}`,
        borderRadius: 10,
        overflow: 'hidden',
        transition: 'border-color 0.2s, opacity 0.2s',
        opacity: control.analysis_status === 'NOT_APPLICABLE' ? 0.45 : 1,
      }}
    >
      {/* Header row */}
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

        {/* Control ID */}
        <div style={{
          minWidth: 90, fontSize: 11, fontWeight: 700, color: '#3b82f6',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {control.control_id}
        </div>

        {/* Title */}
        <div style={{ flex: 1, fontSize: 13, color: '#e5e7eb', fontWeight: 500 }}>
          {control.title}
        </div>

        {/* Category badge */}
        <div style={{
          padding: '2px 8px', borderRadius: 6,
          background: `${catColor}12`, border: `1px solid ${catColor}25`,
          fontSize: 10, color: catColor, fontWeight: 600, whiteSpace: 'nowrap',
        }}>
          {control.category}
        </div>

        {/* Severity badge */}
        <div style={{
          padding: '2px 8px', borderRadius: 6, minWidth: 64, textAlign: 'center',
          background: `${sevColor}12`, border: `1px solid ${sevColor}25`,
          fontSize: 10, fontWeight: 700, color: sevColor,
        }}>
          {control.severity}
        </div>

        {/* Layer badge */}
        <div style={{
          padding: '2px 8px', borderRadius: 6,
          background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)',
          fontSize: 10, fontWeight: 600, color: '#818cf8', whiteSpace: 'nowrap',
        }}>
          L{control.layer}
        </div>

        {/* RAG validation indicator */}
        {ragResult !== undefined ? (
          ragResult.rag_validated ? (
            <CheckCircle2 size={18} color="#10b981" style={{ minWidth: 18 }} />
          ) : (
            <XCircle size={18} color="#ef4444" style={{ minWidth: 18 }} />
          )
        ) : (
          <div style={{ width: 18, height: 18, borderRadius: '50%', border: '2px solid #2a3350', minWidth: 18 }} />
        )}

        {/* Analysis pass/fail/n-a status */}
        {control.analysis_status && control.analysis_status !== 'NOT_RUN' && (
          <div style={{
            padding: '2px 8px', borderRadius: 6, minWidth: 40, textAlign: 'center',
            background: control.analysis_status === 'PASS' ? 'rgba(16,185,129,0.1)'
              : control.analysis_status === 'NOT_APPLICABLE' ? 'rgba(107,114,128,0.1)'
              : 'rgba(239,68,68,0.1)',
            border: `1px solid ${control.analysis_status === 'PASS' ? 'rgba(16,185,129,0.25)'
              : control.analysis_status === 'NOT_APPLICABLE' ? 'rgba(107,114,128,0.25)'
              : 'rgba(239,68,68,0.25)'}`,
            fontSize: 10, fontWeight: 700,
            color: control.analysis_status === 'PASS' ? '#10b981'
              : control.analysis_status === 'NOT_APPLICABLE' ? '#6b7280'
              : '#ef4444',
          }}>
            {control.analysis_status === 'PASS' ? 'COMPLIANT'
              : control.analysis_status === 'FAIL' ? 'FINDINGS'
              : control.analysis_status === 'NOT_APPLICABLE' ? 'N/A'
              : control.analysis_status}
          </div>
        )}
      </div>

      {/* Expanded detail */}
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
              {/* Description */}
              <div style={{ fontSize: 12, color: '#d1d5db', lineHeight: 1.6 }}>
                {control.description}
              </div>

              {/* Metadata */}
              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 11 }}>
                <div>
                  <span style={{ color: '#6b7280' }}>Regulation: </span>
                  <span style={{ color: '#3b82f6', fontWeight: 600 }}>{control.regulation}</span>
                </div>
                <div>
                  <span style={{ color: '#6b7280' }}>Section: </span>
                  <span style={{ color: '#8b5cf6', fontWeight: 600 }}>{control.section}</span>
                </div>
                <div>
                  <span style={{ color: '#6b7280' }}>Validated by: </span>
                  <span style={{ color: '#e5e7eb', fontWeight: 600 }}>{control.layer_name}</span>
                </div>
              </div>

              {/* RAG Citation */}
              {ragResult && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8,
                  background: ragResult.rag_validated
                    ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)',
                  border: `1px solid ${ragResult.rag_validated ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
                }}>
                  <div style={{
                    fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1,
                    color: ragResult.rag_validated ? '#10b981' : '#ef4444', marginBottom: 6,
                  }}>
                    {ragResult.rag_validated ? 'RAG Validated — Regulatory Citation Found' : 'RAG Validation Failed — No Citation Match'}
                  </div>
                  {ragResult.rag_citation && (
                    <div style={{ fontSize: 11, color: '#9ca3af', lineHeight: 1.5, fontStyle: 'italic' }}>
                      "{ragResult.rag_citation}"
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
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
        <div style={{ fontSize: 16, fontWeight: 700, color: '#e5e7eb' }}>RAG Regulatory Coverage</div>
        <div style={{ fontSize: 12, color: '#6b7280', textAlign: 'center', maxWidth: 420, lineHeight: 1.6 }}>
          {pipelineCompleted
            ? 'Compare your system\'s controls against additional regulatory sections discovered by the RAG knowledge base.'
            : 'Run the analysis pipeline first, then load RAG coverage data here.'}
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
              ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Loading...</>
              : <><Radar size={14} /> Load RAG Comparison</>}
          </button>
        )}
      </div>
    );
  }

  const classified = ragComparison.rag_only_classified || [];
  const ragSeverities = [...new Set(classified.map(c => c.severity))];
  const ragRegulations = [...new Set(classified.map(c => c.regulation))];

  const filtered = classified.filter(item => {
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      if (!item.section.toLowerCase().includes(term) && !item.regulation.toLowerCase().includes(term))
        return false;
    }
    if (filterSeverity !== 'all' && item.severity !== filterSeverity) return false;
    if (filterRegulation !== 'all' && item.regulation !== filterRegulation) return false;
    return true;
  });

  return (
    <>
      {/* Section Header */}
      <div style={{
        fontSize: 11, fontWeight: 700, color: '#6b7280', letterSpacing: 1.5,
        textTransform: 'uppercase', paddingBottom: 4,
        borderBottom: '1px solid #2a335050',
      }}>
        RAG Controls — Additional Regulatory Sections from RAG Analysis
      </div>

      {/* RAG Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
        <SummaryCard icon={<Radar size={20} />} label="RAG SECTIONS" value={ragComparison.rag_only_count} color="#8b5cf6" />
        <SummaryCard icon={<AlertTriangle size={20} />} label="CRITICAL" value={ragComparison.rag_only_by_severity?.CRITICAL || 0} color="#ef4444" />
        <SummaryCard icon={<AlertTriangle size={20} />} label="HIGH" value={ragComparison.rag_only_by_severity?.HIGH || 0} color="#f97316" />
        <SummaryCard icon={<AlertTriangle size={20} />} label="MEDIUM" value={ragComparison.rag_only_by_severity?.MEDIUM || 0} color="#f59e0b" />
        <SummaryCard icon={<AlertTriangle size={20} />} label="LOW" value={ragComparison.rag_only_by_severity?.LOW || 0} color="#06b6d4" />
        <SummaryCard icon={<CheckCircle2 size={20} />} label="RAG COVERAGE" value={`${ragComparison.semantic_coverage_pct}%`} color="#10b981" />
      </div>

      {/* RAG Coverage Bar */}
      <div style={{
        background: '#111827', borderRadius: 12, border: '1px solid #2a3350', padding: 16,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
          RAG Severity Breakdown — {ragComparison.rag_only_count} Additional Sections
        </div>
        <div style={{ display: 'flex', gap: 0, borderRadius: 6, overflow: 'hidden', height: 10, marginBottom: 10 }}>
          {[
            { key: 'CRITICAL', color: '#ef4444' },
            { key: 'HIGH', color: '#f97316' },
            { key: 'MEDIUM', color: '#f59e0b' },
            { key: 'LOW', color: '#06b6d4' },
          ].map(({ key, color }) => {
            const count = ragComparison.rag_only_by_severity?.[key] || 0;
            const pct = ragComparison.rag_only_count > 0 ? (count / ragComparison.rag_only_count * 100) : 0;
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
              <span style={{ fontSize: 12, fontWeight: 700, color: '#e5e7eb' }}>{ragComparison.rag_only_by_severity?.[key] || 0}</span>
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
        <span>RAG identifies {ragComparison.rag_only_count} additional regulatory sections beyond the system control library</span>
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
          options={[{ value: 'all', label: 'All Severities' }, ...ragSeverities.map(s => ({ value: s, label: s }))]}
        />
        <FilterSelect
          value={filterRegulation}
          onChange={onRegulationChange}
          options={[{ value: 'all', label: 'All Regulations' }, ...ragRegulations.map(r => ({ value: r, label: r }))]}
        />
      </div>

      {/* Results count */}
      <div style={{ fontSize: 12, color: '#6b7280' }}>
        Showing {filtered.length} of {classified.length} RAG controls
      </div>

      {/* RAG Control List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <AnimatePresence>
          {filtered.map((item, i) => (
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
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          §{control.section}
        </div>

        {/* Regulation */}
        <div style={{ flex: 1, fontSize: 13, color: '#e5e7eb', fontWeight: 500 }}>
          {control.regulation}
        </div>

        {/* RAG badge */}
        <div style={{
          padding: '2px 8px', borderRadius: 6,
          background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.25)',
          fontSize: 9, fontWeight: 700, color: '#8b5cf6', letterSpacing: 0.5,
        }}>
          RAG CONTROL
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
                  <span style={{ color: '#10b981', fontWeight: 600 }}>RAG Vector Analysis</span>
                </div>
              </div>

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
