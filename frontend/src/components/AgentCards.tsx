import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, CheckCircle, XCircle, Loader2,
  Clock, FileWarning, ChevronDown, ChevronUp,
} from 'lucide-react';
import { useState } from 'react';
import type { AgentDef, Finding } from '../types';

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#06b6d4',
  INFO: '#6b7280',
};

const STATUS_CONFIG: Record<string, { color: string; icon: typeof Shield; label: string }> = {
  idle: { color: '#6b7280', icon: Shield, label: 'Waiting' },
  running: { color: '#3b82f6', icon: Loader2, label: 'Analyzing...' },
  completed: { color: '#10b981', icon: CheckCircle, label: 'Complete' },
  failed: { color: '#ef4444', icon: XCircle, label: 'Failed' },
};

interface Props {
  agents: AgentDef[];
  controlSections?: Set<string>;
}

export function AgentCards({ agents, controlSections }: Props) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 16 }}>
      <AnimatePresence>
        {agents.map((agent, i) => (
          <AgentCard key={agent.id} agent={agent} index={i} controlSections={controlSections} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function AgentCard({ agent, index, controlSections }: { agent: AgentDef; index: number; controlSections?: Set<string> }) {
  const [expanded, setExpanded] = useState(false);
  const config = STATUS_CONFIG[agent.status] || STATUS_CONFIG.idle;
  const StatusIcon = config.icon;
  const totalFindings = Object.values(agent.finding_counts || {}).reduce((a, b) => a + b, 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      style={{
        background: '#1e2538',
        border: `1px solid ${agent.status === 'running' ? '#3b82f6' : '#2a3350'}`,
        borderRadius: 12,
        overflow: 'hidden',
        transition: 'border-color 0.3s',
      }}
    >
      {/* Progress bar for running */}
      {agent.status === 'running' && (
        <motion.div
          style={{ height: 3, background: 'linear-gradient(90deg, #3b82f6, #06b6d4, #3b82f6)', backgroundSize: '200% 100%' }}
          animate={{ backgroundPosition: ['0% 0%', '200% 0%'] }}
          transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
        />
      )}

      <div style={{ padding: '16px 20px' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: `linear-gradient(135deg, ${config.color}15, ${config.color}30)`,
              border: `1px solid ${config.color}40`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <StatusIcon
                size={20}
                color={config.color}
                style={agent.status === 'running' ? { animation: 'spin 1s linear infinite' } : {}}
              />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase' }}>
                Layer {agent.layer}
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#e5e7eb' }}>
                {agent.name}
              </div>
            </div>
          </div>

          <div style={{
            padding: '4px 10px', borderRadius: 20,
            background: `${config.color}15`,
            border: `1px solid ${config.color}30`,
            fontSize: 11, fontWeight: 600, color: config.color,
          }}>
            {config.label}
          </div>
        </div>

        {/* Regulation */}
        <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileWarning size={13} />
          {agent.regulation}
        </div>

        {/* Finding counts */}
        {totalFindings > 0 && (
          <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            {Object.entries(agent.finding_counts || {}).map(([sev, count]) => (
              count > 0 && (
                <div key={sev} style={{
                  padding: '3px 8px', borderRadius: 6,
                  background: `${SEVERITY_COLORS[sev]}15`,
                  border: `1px solid ${SEVERITY_COLORS[sev]}30`,
                  fontSize: 11, fontWeight: 700, color: SEVERITY_COLORS[sev],
                }}>
                  {count} {sev}
                </div>
              )
            ))}
          </div>
        )}

        {/* Duration + expand */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {agent.duration_ms > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#6b7280' }}>
              <Clock size={12} />
              {agent.duration_ms}ms
            </div>
          )}
          {totalFindings > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: '#3b82f6', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4,
              }}
            >
              {expanded ? 'Hide' : 'Show'} {totalFindings} findings
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
        </div>
      </div>

      {/* Expanded findings */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ borderTop: '1px solid #2a3350', padding: '12px 20px', maxHeight: 300, overflowY: 'auto' }}>
              {(agent.findings || []).map((f, i) => (
                <FindingRow key={i} finding={f} index={i} controlSections={controlSections} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function FindingRow({ finding, index, controlSections }: { finding: Finding; index: number; controlSections?: Set<string> }) {
  const sevColor = SEVERITY_COLORS[finding.severity] || '#6b7280';

  // Determine if this finding maps to a System Control or RAG Control
  const findingRef = finding.cfr_reference || finding.it_guide_reference || '';
  const isSystemControl = controlSections
    ? [...controlSections].some(s => findingRef.includes(s) || s.includes(findingRef.replace('Section ', '')))
    : !!finding.cfr_reference; // fallback: CFR refs are always system controls

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      style={{
        padding: '10px 0',
        borderBottom: '1px solid #1a2035',
      }}
    >
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
          <div style={{
            minWidth: 56, padding: '2px 6px', borderRadius: 4,
            background: `${sevColor}15`, border: `1px solid ${sevColor}30`,
            fontSize: 10, fontWeight: 700, color: sevColor, textAlign: 'center',
          }}>
            {finding.severity}
          </div>
          {/* Control Source Badge */}
          <div style={{
            minWidth: 56, padding: '2px 4px', borderRadius: 4, textAlign: 'center',
            background: isSystemControl ? 'rgba(59,130,246,0.08)' : 'rgba(139,92,246,0.08)',
            border: `1px solid ${isSystemControl ? 'rgba(59,130,246,0.2)' : 'rgba(139,92,246,0.2)'}`,
            fontSize: 8, fontWeight: 700, letterSpacing: 0.3,
            color: isSystemControl ? '#3b82f6' : '#8b5cf6',
          }}>
            {isSystemControl ? 'SYSTEM' : 'RAG'}
          </div>
        </div>
        <div style={{ flex: 1 }}>
          {finding.title && (
            <div style={{ fontSize: 12, color: '#e5e7eb', fontWeight: 600, marginBottom: 2 }}>
              {finding.title}
            </div>
          )}
          {/* Source File / Line Reference */}
          {finding.source_file && (
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '3px 8px', borderRadius: 5,
              background: '#3b82f610', border: '1px solid #3b82f625',
              marginBottom: 4, fontSize: 11,
            }}>
              <span style={{ color: '#3b82f6', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                {finding.source_file}
              </span>
              {(finding.line_number ?? 0) > 0 && (
                <span style={{ color: '#6b7280' }}>
                  L{finding.line_number}
                </span>
              )}
            </div>
          )}
          <div style={{ fontSize: 12, color: '#d1d5db', lineHeight: 1.5 }}>
            {finding.description}
          </div>
          {/* Code Snippet */}
          {finding.code_snippet && (
            <pre style={{
              fontSize: 10, lineHeight: 1.5, color: '#a5b4fc',
              background: '#0d1117', border: '1px solid #1e2538',
              borderRadius: 6, padding: '6px 10px', marginTop: 4,
              overflow: 'auto', maxHeight: 80, whiteSpace: 'pre-wrap',
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            }}>
              {finding.code_snippet}
            </pre>
          )}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 4 }}>
            {finding.cfr_reference && (
              <div style={{ fontSize: 10, color: '#3b82f6', fontWeight: 500 }}>
                CFR: {finding.cfr_reference}
              </div>
            )}
            {finding.it_guide_reference && (
              <div style={{ fontSize: 10, color: '#8b5cf6', fontWeight: 500 }}>
                IT Guide: {finding.it_guide_reference}
              </div>
            )}
            {finding.orc_type && (
              <div style={{ fontSize: 10, color: '#f59e0b', fontWeight: 500 }}>
                ORC: {finding.orc_type}
              </div>
            )}
          </div>
          {finding.remediation_recommendation && (
            <div style={{ fontSize: 11, color: '#10b981', marginTop: 4, lineHeight: 1.4 }}>
              Fix: {finding.remediation_recommendation}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
