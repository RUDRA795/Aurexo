import { useCallback, useRef, useState } from 'react';
import type { FinalResponse, MapOverlay, EvidenceRecord } from './contracts';

export type StreamConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'streaming'
  | 'reconnecting'
  | 'completed'
  | 'cancelled'
  | 'error';

export interface AgentExecutionStep {
  id: string;
  name: string;
  agent?: string;
  tool?: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
  durationMs?: number;
}

export interface StreamEventPayload {
  event_id: string;
  sequence: number;
  event_type: string;
  run_id: string;
  thread_id: string;
  trace_id: string;
  timestamp: string;
  node?: string;
  agent?: string;
  tool?: string;
  status?: string;
  duration_ms?: number;
  checkpoint_id?: string;
  evidence_ids?: string[];
  error_code?: string;
  progress?: number;
  payload: Record<string, any>;
  redaction_status?: string;
}

export interface UseAgentStreamState {
  connectionStatus: StreamConnectionStatus;
  runId: string | null;
  threadId: string | null;
  currentAgent: string | null;
  currentTool: string | null;
  steps: AgentExecutionStep[];
  evidence: EvidenceRecord[];
  finalResponse: FinalResponse | null;
  mapOverlays: MapOverlay[];
  lastSequence: number;
  error: string | null;
}

const DEFAULT_STEPS: AgentExecutionStep[] = [
  { id: 'step_1', name: 'Understanding request', agent: 'SupervisorNode', status: 'pending' },
  { id: 'step_2', name: 'Creating execution plan', agent: 'SupervisorNode', status: 'pending' },
  { id: 'step_3', name: 'PFZ retrieval', agent: 'PFZAgentNode', tool: 'incois_webgis_pfz', status: 'pending' },
  { id: 'step_4', name: 'SST retrieval', agent: 'EnvironmentAgentNode', tool: 'incois_osf_sst', status: 'pending' },
  { id: 'step_5', name: 'Chlorophyll retrieval', agent: 'EnvironmentAgentNode', tool: 'incois_viirs_chl', status: 'pending' },
  { id: 'step_6', name: 'Marine weather retrieval', agent: 'EnvironmentAgentNode', tool: 'incois_marine_state', status: 'pending' },
  { id: 'step_7', name: 'Advisory & warnings search', agent: 'AdvisoryAgentNode', tool: 'imd_fishermen_warning', status: 'pending' },
  { id: 'step_8', name: 'Scientific verification', agent: 'SafetyValidationNode', status: 'pending' },
  { id: 'step_9', name: 'Evidence sufficiency', agent: 'SupervisorNode', status: 'pending' },
  { id: 'step_10', name: 'Synthesis & map overlay', agent: 'SynthesizerNode', status: 'pending' },
];

export function useAgentStream(apiBaseUrl: string = 'http://localhost:8000') {
  const [state, setState] = useState<UseAgentStreamState>({
    connectionStatus: 'idle',
    runId: null,
    threadId: null,
    currentAgent: null,
    currentTool: null,
    steps: DEFAULT_STEPS,
    evidence: [],
    finalResponse: null,
    mapOverlays: [],
    lastSequence: 0,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const activeParamsRef = useRef<{ query: string; coordinates?: { lat: number; lon: number }; sector?: string; threadId?: string; runId?: string } | null>(null);

  const applyEvent = useCallback((event: StreamEventPayload) => {
    setState((prev) => {
      // Deduplicate: ignore events already applied
      if (event.sequence > 0 && event.sequence <= prev.lastSequence) {
        return prev;
      }

      const nextSeq = Math.max(prev.lastSequence, event.sequence);
      const nextSteps = [...prev.steps];
      let nextAgent = prev.currentAgent;
      let nextTool = prev.currentTool;
      let nextResponse = prev.finalResponse;
      let nextOverlays = [...prev.mapOverlays];
      const nextEvidence = [...prev.evidence];
      let nextStatus = prev.connectionStatus;

      // Update agent/tool tracking
      if (event.agent) nextAgent = event.agent;
      if (event.tool) nextTool = event.tool;

      // Process event types
      switch (event.event_type) {
        case 'RUN_STARTED':
          nextStatus = 'streaming';
          break;

        case 'PLAN_CREATED': {
          const rawSteps = event.payload?.steps;
          if (Array.isArray(rawSteps) && rawSteps.length > 0) {
            // Match planned steps
            rawSteps.forEach((pStep: any, idx: number) => {
              if (nextSteps[idx]) {
                nextSteps[idx] = {
                  ...nextSteps[idx],
                  name: pStep.name || nextSteps[idx].name,
                  agent: pStep.agent || nextSteps[idx].agent,
                  tool: pStep.tool || nextSteps[idx].tool,
                };
              }
            });
          }
          break;
        }

        case 'AGENT_STARTED': {
          const stepIndex = nextSteps.findIndex((s) => s.agent === event.agent && s.status === 'pending');
          if (stepIndex !== -1) {
            nextSteps[stepIndex] = { ...nextSteps[stepIndex], status: 'active' };
          }
          break;
        }

        case 'TOOL_STARTED': {
          const stepIndex = nextSteps.findIndex((s) => s.tool === event.tool);
          if (stepIndex !== -1) {
            nextSteps[stepIndex] = { ...nextSteps[stepIndex], status: 'active' };
          }
          break;
        }

        case 'TOOL_COMPLETED': {
          const stepIndex = nextSteps.findIndex((s) => s.tool === event.tool);
          if (stepIndex !== -1) {
            const isError = event.status === 'ERROR';
            nextSteps[stepIndex] = {
              ...nextSteps[stepIndex],
              status: isError ? 'failed' : 'completed',
              durationMs: event.duration_ms,
            };
          }
          break;
        }

        case 'AGENT_COMPLETED': {
          const stepIndex = nextSteps.findIndex((s) => s.agent === event.agent && s.status === 'active');
          if (stepIndex !== -1) {
            nextSteps[stepIndex] = { ...nextSteps[stepIndex], status: 'completed' };
          }
          break;
        }

        case 'EVIDENCE_ADDED': {
          const p = event.payload;
          if (p && p.evidence_id) {
            const exists = nextEvidence.some((e) => e.retrieved_at === p.evidence_id || (e.value && e.value.pfz_id === p.pfz_id));
            if (!exists) {
              nextEvidence.push({
                variable: p.variable || 'marine_evidence',
                value: p.value || p.pfz_id || p,
                quality: p.quality || 'good',
                source: {
                  source_id: p.source_id || 'incois',
                  organization: 'INCOIS',
                  dataset: p.dataset || 'Marine Intelligence',
                },
                retrieved_at: event.timestamp,
              });
            }
          }
          break;
        }

        case 'EVIDENCE_CHECK': {
          const checkStep = nextSteps.find((s) => s.id === 'step_8');
          if (checkStep) {
            checkStep.status = event.status === 'PASSED' ? 'completed' : 'active';
          }
          break;
        }

        case 'MAP_OVERLAY_UPDATED': {
          const p = event.payload;
          if (p && p.coordinates) {
            const featureOverlay: MapOverlay = {
              layer_id: p.overlay_id || 'nearest-pfz',
              style_hint: 'pfz',
              data: {
                type: 'FeatureCollection',
                features: [
                  {
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: p.coordinates },
                    properties: {
                      pfz_id: p.selected_id || 'pfz_live_01',
                      distance_km: p.distance_km,
                      bearing_deg: p.bearing_deg,
                    },
                  },
                ],
              },
            };
            nextOverlays = [featureOverlay];
          }
          break;
        }

        case 'SYNTHESIS_COMPLETED': {
          const p = event.payload;
          if (p) {
            nextResponse = {
              session_id: event.run_id,
              response_type: p.response_type || 'factual',
              answer_text: p.answer_text || 'Synthesized marine advisory',
              confidence: p.confidence || 0.85,
              evidence_summary: nextEvidence,
              limitations: ['Grounded against official INCOIS/IMD verified evidence.'],
              map_overlays: nextOverlays,
            };
          }
          const synthStep = nextSteps.find((s) => s.id === 'step_10');
          if (synthStep) synthStep.status = 'completed';
          break;
        }

        case 'RUN_COMPLETED':
          nextStatus = 'completed';
          break;

        case 'RUN_CANCELLED':
          nextStatus = 'cancelled';
          break;

        case 'RUN_FAILED':
          nextStatus = 'error';
          break;

        default:
          break;
      }

      return {
        ...prev,
        connectionStatus: nextStatus,
        runId: event.run_id,
        threadId: event.thread_id,
        currentAgent: nextAgent,
        currentTool: nextTool,
        steps: nextSteps,
        evidence: nextEvidence,
        finalResponse: nextResponse,
        mapOverlays: nextOverlays,
        lastSequence: nextSeq,
      };
    });
  }, []);

  const connectSSE = useCallback(
    async (
      params: { query: string; coordinates?: { lat: number; lon: number }; sector?: string; threadId?: string; runId?: string },
      resumeFromSeq?: number
    ) => {
      activeParamsRef.current = params;
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setState((prev) => ({
        ...prev,
        connectionStatus: resumeFromSeq ? 'reconnecting' : 'connecting',
        error: null,
      }));

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (resumeFromSeq && resumeFromSeq > 0) {
        headers['Last-Event-ID'] = String(resumeFromSeq);
      }

      try {
        const response = await fetch(`${apiBaseUrl}/v1/agent/stream`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            query: params.query,
            coordinates: params.coordinates,
            sector: params.sector,
            thread_id: params.threadId,
            run_id: params.runId,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`SSE stream failed with status ${response.status}`);
        }
        if (!response.body) {
          throw new Error('Response body is null');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';

          for (const block of parts) {
            if (!block.trim() || block.startsWith(':')) {
              // Comment or keepalive
              continue;
            }

            const lines = block.split('\n');
            let eventType = 'message';
            let eventId = '';
            let dataStr = '';

            for (const line of lines) {
              if (line.startsWith('event:')) {
                eventType = line.replace('event:', '').trim();
              } else if (line.startsWith('id:')) {
                eventId = line.replace('id:', '').trim();
              } else if (line.startsWith('data:')) {
                dataStr = line.replace('data:', '').trim();
              }
            }

            if (dataStr) {
              try {
                const parsed = JSON.parse(dataStr);
                applyEvent({
                  ...parsed,
                  event_type: eventType || parsed.event_type,
                  sequence: eventId ? parseInt(eventId, 10) : parsed.sequence || 0,
                });
              } catch (parseErr) {
                console.warn('Failed to parse SSE event data:', dataStr, parseErr);
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setState((prev) => ({ ...prev, connectionStatus: 'cancelled' }));
        } else {
          console.error('Agent SSE connection error:', err);
          setState((prev) => ({
            ...prev,
            connectionStatus: 'error',
            error: err.message || 'Stream connection failed',
          }));
        }
      }
    },
    [apiBaseUrl, applyEvent]
  );

  const startStream = useCallback(
    (query: string, options?: { coordinates?: { lat: number; lon: number }; sector?: string; threadId?: string }) => {
      setState((prev) => ({
        ...prev,
        steps: DEFAULT_STEPS.map((s) => ({ ...s, status: 'pending', durationMs: undefined })),
        evidence: [],
        finalResponse: null,
        mapOverlays: [],
        lastSequence: 0,
        error: null,
      }));
      return connectSSE({
        query,
        coordinates: options?.coordinates,
        sector: options?.sector,
        threadId: options?.threadId,
      });
    },
    [connectSSE]
  );

  const cancelStream = useCallback(async () => {
    abortControllerRef.current?.abort();
    if (state.runId) {
      try {
        await fetch(`${apiBaseUrl}/v1/agent/runs/${state.runId}/cancel`, {
          method: 'POST',
        });
      } catch (err) {
        console.warn('Cancellation request failed:', err);
      }
    }
    setState((prev) => ({ ...prev, connectionStatus: 'cancelled' }));
  }, [apiBaseUrl, state.runId]);

  return {
    ...state,
    startStream,
    cancelStream,
  };
}
