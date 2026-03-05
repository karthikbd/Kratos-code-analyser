import { useCallback, useEffect, useRef, useState } from 'react';
import type { AgentDef, Finding, PipelineSummary, WSEvent } from '../types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws';
const API_BASE = WS_URL.replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

export interface PipelineState {
  connected: boolean;
  runId: string | null;
  status: 'idle' | 'running' | 'completed' | 'failed';
  institution: string;
  agents: AgentDef[];
  findings: Finding[];
  summary: PipelineSummary | null;
  ragStatus: string;
  ragChunks: number;
  events: WSEvent[];
  systemId: string;
  sourceFiles: string[];
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<PipelineState>({
    connected: false,
    runId: null,
    status: 'idle',
    institution: '',
    agents: [],
    findings: [],
    summary: null,
    ragStatus: 'unknown',
    ragChunks: 0,
    events: [],
    systemId: '',
    sourceFiles: [],
  });

  // Fetch RAG status on initial connect
  const checkRagStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rag/status`);
      const data = await res.json();
      setState(s => ({
        ...s,
        ragStatus: data.ready ? 'ready' : (data.error ? 'failed' : 'not_built'),
      }));
    } catch {
      setState(s => ({ ...s, ragStatus: 'unavailable' }));
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setState(s => ({ ...s, connected: true }));
      checkRagStatus();
    };

    ws.onclose = () => {
      setState(s => ({ ...s, connected: false }));
      // Auto-reconnect after 3s
      setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      const data: WSEvent = JSON.parse(event.data);

      setState(prev => {
        const next = { ...prev, events: [...prev.events.slice(-200), data] };

        switch (data.type) {
          case 'pipeline_started':
            return {
              ...next,
              runId: data.run_id,
              status: 'running',
              institution: data.institution,
              agents: data.agents.map(a => ({ ...a, findings: [], finding_counts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }, duration_ms: 0, status: 'idle' as const })),
              findings: [],
              summary: null,
              systemId: (data as any).system_id || '',
              sourceFiles: (data as any).source_files || [],
            };

          case 'rag_status':
            return {
              ...next,
              ragStatus: data.status,
              ragChunks: data.chunks ?? prev.ragChunks,
            };

          case 'agent_started':
            return {
              ...next,
              agents: prev.agents.map(a =>
                a.id === data.agent_id ? { ...a, status: 'running' as const } : a
              ),
            };

          case 'finding':
            return {
              ...next,
              findings: [...prev.findings, data.finding],
              agents: prev.agents.map(a =>
                a.id === data.agent_id
                  ? {
                      ...a,
                      findings: [...a.findings, data.finding],
                      finding_counts: {
                        ...a.finding_counts,
                        [data.finding.severity]: (a.finding_counts[data.finding.severity] || 0) + 1,
                      },
                    }
                  : a
              ),
            };

          case 'agent_completed':
            return {
              ...next,
              agents: prev.agents.map(a =>
                a.id === data.agent_id
                  ? { ...a, status: 'completed' as const, duration_ms: data.duration_ms, finding_counts: data.finding_counts }
                  : a
              ),
            };

          case 'agent_failed':
            return {
              ...next,
              agents: prev.agents.map(a =>
                a.id === data.agent_id
                  ? { ...a, status: 'failed' as const, error: data.error }
                  : a
              ),
            };

          case 'pipeline_completed':
            return {
              ...next,
              status: 'completed',
              summary: data.summary,
              agents: data.agents,
            };

          case 'run_created':
            return { ...next, runId: data.run_id };

          default:
            return next;
        }
      });
    };
  }, [checkRagStatus]);

  const startRun = useCallback((institutionName: string = 'Covered Institution', useRag: boolean = true, systemId: string = '') => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    setState(s => ({ ...s, status: 'idle', findings: [], summary: null, events: [], systemId: '', sourceFiles: [] }));
    wsRef.current.send(JSON.stringify({
      action: 'run',
      institution_name: institutionName,
      use_rag: useRag,
      system_id: systemId,
    }));
  }, []);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); };
  }, [connect]);

  return { state, startRun };
}
