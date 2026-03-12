import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Play, Shield, Database, Zap, BookOpen, GitBranch, Layers, Server, FolderSearch, Share2 } from 'lucide-react';
import { useWebSocket } from './hooks/useWebSocket';
import { PipelineFlow } from './components/PipelineFlow';
import { AgentCards } from './components/AgentCards';
import { SummaryBar } from './components/SummaryBar';
import { ControlLibrary } from './components/ControlLibrary';
import { DataLineageGraph } from './components/DataLineageGraph';
import type { OperationalSystem } from './types';

const API_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws')
  .replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

type Tab = 'controls' | 'pipeline' | 'lineage' | 'details' | 'events';

export default function App() {
  const { state, startRun } = useWebSocket();
  const [institution, setInstitution] = useState('Covered Institution');
  const [useRag, setUseRag] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('controls');
  const [systems, setSystems] = useState<OperationalSystem[]>([]);
  const [selectedSystem, setSelectedSystem] = useState<string>('');
  const [loadingSystems, setLoadingSystems] = useState(true);
  const [controlSections, setControlSections] = useState<Set<string>>(new Set());

  // Fetch available operational systems
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/systems`);
        const data = await res.json();
        setSystems(data.systems || []);
        if (data.systems?.length > 0) {
          setSelectedSystem(data.systems[0].id);
        }
      } catch (e) {
        console.error('Failed to fetch systems:', e);
      } finally {
        setLoadingSystems(false);
      }
    })();
  }, []);

  // Fetch control sections for finding classification
  useEffect(() => {
    (async () => {
      try {
        const qp = selectedSystem ? `?system_id=${encodeURIComponent(selectedSystem)}` : '';
        const res = await fetch(`${API_BASE}/api/controls${qp}`);
        const data = await res.json();
        const sections = new Set<string>(
          (data.controls || []).map((c: { section?: string }) => c.section).filter(Boolean)
        );
        setControlSections(sections);
      } catch (e) {
        console.error('Failed to fetch control sections:', e);
      }
    })();
  }, [state.status === 'completed', selectedSystem]);

  const handleRun = () => {
    startRun(institution, useRag, selectedSystem);
  };

  const selectedSystemInfo = systems.find(s => s.id === selectedSystem);

  // Use server-authoritative count after pipeline completes; fall back to streaming count during run
  const totalFindings = state.summary?.total ?? state.findings.length;

  const TAB_ITEMS: { id: Tab; label: string; icon: typeof Shield }[] = [
    { id: 'controls', label: 'Compliance Report', icon: BookOpen },
    { id: 'pipeline', label: 'Analysis Pipeline', icon: GitBranch },
    { id: 'lineage', label: 'Data Lineage', icon: Share2 },
    { id: 'details', label: 'Detailed Findings', icon: Layers },
    { id: 'events', label: 'Live Events', icon: Zap },
  ];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        padding: '16px 32px',
        background: '#111827',
        borderBottom: '1px solid #2a3350',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Shield size={22} color="white" />
          </div>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 800, letterSpacing: -0.5, color: '#e5e7eb' }}>
              KRATOS CODE ANALYZER
            </h1>
            <p style={{ fontSize: 11, color: '#6b7280', letterSpacing: 1, textTransform: 'uppercase' }}>
              FDIC Part 370 Deep Compliance Scanner
            </p>
          </div>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {/* Operational System Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }}>
            <FolderSearch size={14} color="#9ca3af" />
            <select
              value={selectedSystem}
              onChange={e => setSelectedSystem(e.target.value)}
              style={{
                padding: '8px 14px', borderRadius: 8,
                background: '#1e2538', border: '1px solid #2a3350',
                color: '#e5e7eb', fontSize: 12, width: 200,
                outline: 'none', cursor: 'pointer',
                appearance: 'none',
              }}
            >
              {loadingSystems ? (
                <option>Loading systems...</option>
              ) : systems.length === 0 ? (
                <option value="">No systems found</option>
              ) : (
                systems.map(sys => (
                  <option key={sys.id} value={sys.id}>
                    {sys.name} ({sys.file_count} files)
                  </option>
                ))
              )}
            </select>
          </div>

          <input
            value={institution}
            onChange={e => setInstitution(e.target.value)}
            placeholder="Institution name"
            style={{
              padding: '8px 14px', borderRadius: 8,
              background: '#1e2538', border: '1px solid #2a3350',
              color: '#e5e7eb', fontSize: 13, width: 220,
              outline: 'none',
            }}
          />

          <label style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 12px', borderRadius: 8,
            background: useRag ? 'rgba(59,130,246,0.12)' : '#1e2538',
            border: `1px solid ${useRag ? '#3b82f644' : '#2a3350'}`,
            cursor: 'pointer', fontSize: 12, color: useRag ? '#3b82f6' : '#9ca3af',
            fontWeight: 600, userSelect: 'none',
          }}>
            <input
              type="checkbox"
              checked={useRag}
              onChange={e => setUseRag(e.target.checked)}
              style={{ display: 'none' }}
            />
            <Database size={14} />
            RAG
          </label>

          <motion.button
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={handleRun}
            disabled={state.status === 'running' || !state.connected}
            style={{
              padding: '8px 20px', borderRadius: 8,
              background: state.status === 'running'
                ? 'linear-gradient(135deg, #1e40af, #3b82f6)'
                : 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              border: 'none', color: 'white', fontSize: 13,
              fontWeight: 700, cursor: state.status === 'running' ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 8,
              opacity: !state.connected ? 0.5 : 1,
            }}
          >
            {state.status === 'running' ? (
              <>
                <Zap size={15} style={{ animation: 'spin 1s linear infinite' }} />
                Running...
              </>
            ) : (
              <>
                <Play size={15} />
                Analyze
              </>
            )}
          </motion.button>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ flex: 1, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Summary Bar */}
        <SummaryBar
          summary={state.summary}
          status={state.status}
          ragStatus={state.ragStatus}
          ragChunks={state.ragChunks}
          totalFindings={totalFindings}
          connected={state.connected}
        />

        {/* System Info Bar */}
        {selectedSystemInfo && (
          <div style={{
            display: 'flex', gap: 16, alignItems: 'center',
            padding: '10px 20px', borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.08))',
            border: '1px solid rgba(59,130,246,0.2)',
            fontSize: 12,
          }}>
            <Server size={16} color="#3b82f6" />
            <div>
              <span style={{ fontWeight: 700, color: '#e5e7eb' }}>Target System: </span>
              <span style={{ color: '#3b82f6', fontWeight: 600 }}>{selectedSystemInfo.name}</span>
            </div>
            <span style={{ color: '#6b7280' }}>|</span>
            <span style={{ color: '#9ca3af' }}>{selectedSystemInfo.file_count} source files</span>
            <span style={{ color: '#6b7280' }}>|</span>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {selectedSystemInfo.files.slice(0, 5).map(f => (
                <span key={f} style={{
                  padding: '2px 8px', borderRadius: 4,
                  background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                  color: '#60a5fa', fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
                }}>{f}</span>
              ))}
            </div>
            {state.sourceFiles.length > 0 && state.status !== 'idle' && (
              <>
                <span style={{ color: '#6b7280' }}>|</span>
                <span style={{ color: '#10b981', fontWeight: 600 }}>
                  Scanning {state.sourceFiles.length} files live
                </span>
              </>
            )}
          </div>
        )}

        {/* Tab Navigation */}
        <div style={{
          display: 'flex', gap: 4, borderBottom: '2px solid #2a3350', paddingBottom: 0,
        }}>
          {TAB_ITEMS.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '10px 20px', borderRadius: '8px 8px 0 0',
                  background: isActive ? '#1e2538' : 'transparent',
                  borderBottom: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                  border: isActive ? '1px solid #2a3350' : '1px solid transparent',
                  borderBottomColor: isActive ? '#1e2538' : 'transparent',
                  marginBottom: -2,
                  color: isActive ? '#e5e7eb' : '#6b7280',
                  fontSize: 12, fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6,
                  transition: 'all 0.2s',
                  letterSpacing: 0.5,
                }}
              >
                <Icon size={14} />
                {tab.label}
                {tab.id === 'details' && totalFindings > 0 && (
                  <span style={{
                    padding: '1px 6px', borderRadius: 8,
                    background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
                    fontSize: 10, fontWeight: 700, color: '#ef4444',
                  }}>
                    {totalFindings}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        {activeTab === 'controls' && (
          <ControlLibrary pipelineStatus={state.status} selectedSystem={selectedSystem} agents={state.agents} />
        )}

        {activeTab === 'pipeline' && (
          <PipelineFlow agents={state.agents} />
        )}

        {activeTab === 'lineage' && (
          <DataLineageGraph pipelineStatus={state.status} selectedSystem={selectedSystem} />
        )}

        {activeTab === 'details' && (
          <AgentCards agents={state.agents.length > 0 ? state.agents : DEFAULT_AGENTS} controlSections={controlSections} />
        )}

        {activeTab === 'events' && (
          <div style={{
            background: '#111827', border: '1px solid #2a3350', borderRadius: 12,
            padding: '16px 20px', minHeight: 300, maxHeight: 600, overflowY: 'auto',
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontSize: 11, lineHeight: 1.8,
          }}>
            {state.events.length === 0 ? (
              <div style={{ color: '#6b7280', textAlign: 'center', padding: 40 }}>
                No events yet. Click "Analyze" to start the pipeline.
              </div>
            ) : (
              state.events.slice(-100).map((evt, i) => (
                <div key={i} style={{ color: eventColor(evt.type), borderBottom: '1px solid #1a2035', padding: '4px 0' }}>
                  <span style={{ color: '#6b7280', marginRight: 8 }}>[{String(i + 1).padStart(3, '0')}]</span>
                  <span style={{ fontWeight: 700 }}>{evt.type}</span>
                  {'agent_id' in evt && <span style={{ color: '#9ca3af', marginLeft: 8 }}>{evt.agent_id}</span>}
                  {'name' in evt && <span style={{ color: '#e5e7eb', marginLeft: 8 }}>{(evt as { name: string }).name}</span>}
                  {'finding' in evt && <span style={{ color: '#f59e0b', marginLeft: 8 }}>{((evt as { finding: { severity: string } }).finding).severity}</span>}
                </div>
              ))
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{
        padding: '12px 32px', background: '#111827',
        borderTop: '1px solid #2a3350',
        fontSize: 11, color: '#6b7280', textAlign: 'center',
      }}>
        Kratos Code Analyzer v1.0.0 — FDIC Part 370 / 12 CFR Part 330 / FDIC IT Guide v3.0 — {state.agents.length} Layers{state.summary ? ` | ${state.summary.total_controls} Controls` : ''}
      </footer>
    </div>
  );
}

const DEFAULT_AGENTS = [
  { id: 'layer1', name: 'ORC Static Analyzer', layer: 1, description: 'ORC Assignment Logic Static Analysis', regulation: '12 CFR Part 330 / IT Guide Section 4', status: 'idle' as const, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
  { id: 'layer2', name: 'Data Completeness Validator', layer: 2, description: 'Data Completeness and Validation', regulation: 'IT Guide Sections 2.3.2-2.3.3', status: 'idle' as const, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
  { id: 'layer3', name: 'Calculation Engine Verifier', layer: 3, description: 'Calculation Engine Verification', regulation: 'Compliance Manual Sections 6, 10', status: 'idle' as const, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
  { id: 'layer4', name: 'Output Pipeline Inspector', layer: 4, description: 'Output File Pipeline Integrity', regulation: 'IT Guide Section 5 / Appendix A', status: 'idle' as const, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
  { id: 'layer5', name: 'Behavioral Compliance Tester', layer: 5, description: 'Behavioral / Runtime Compliance', regulation: 'Compliance Manual Sections 4, 5', status: 'idle' as const, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
  { id: 'layer6', name: 'Certification Generator', layer: 6, description: 'Certification Artifact Generation', regulation: '12 CFR 370.10(a) / Appendix B', status: 'idle' as const, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
  { id: 'layer7', name: 'Data Lineage Tracer', layer: 7, description: 'Data Lineage & Back-Traceability', regulation: '12 CFR 370.3(b) / IT Guide §§2.1, 5.1-5.4', status: 'idle' as const, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0 },
];

function eventColor(type: string): string {
  if (type.includes('started')) return '#3b82f6';
  if (type.includes('completed')) return '#10b981';
  if (type.includes('failed')) return '#ef4444';
  if (type === 'finding') return '#f59e0b';
  if (type.includes('rag')) return '#8b5cf6';
  return '#6b7280';
}
