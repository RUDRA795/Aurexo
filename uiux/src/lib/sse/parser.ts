import { OrcaBackendEvent } from '../../types/orca';

export type SSEEventCallback = (event: OrcaBackendEvent) => void;
export type SSEErrorCallback = (error: Error) => void;

/**
 * Robust stream parser for Server-Sent Events from the FastAPI /v1/agent/stream endpoint.
 */
export class SSEParser {
  private buffer: string = '';

  /**
   * Feed a new raw text chunk from the response reader.
   */
  public feed(chunk: string, onEvent: SSEEventCallback): void {
    this.buffer += chunk;
    const parts = this.buffer.split(/\r?\n\r?\n/);
    // The last part may be incomplete
    this.buffer = parts.pop() || '';

    for (const rawMessage of parts) {
      if (!rawMessage.trim()) continue;
      const parsed = this.parseRawMessage(rawMessage);
      if (parsed) {
        onEvent(parsed);
      }
    }
  }

  /**
   * Flush any remaining buffer.
   */
  public flush(onEvent: SSEEventCallback): void {
    if (this.buffer.trim()) {
      const parsed = this.parseRawMessage(this.buffer);
      if (parsed) {
        onEvent(parsed);
      }
      this.buffer = '';
    }
  }

  private parseRawMessage(raw: string): OrcaBackendEvent | null {
    const lines = raw.split(/\r?\n/);
    let eventType: string = 'message';
    let dataStr = '';

    for (const line of lines) {
      if (line.startsWith(':')) {
        // Comment or heartbeat
        continue;
      }
      if (line.startsWith('event:')) {
        eventType = line.replace('event:', '').trim();
      } else if (line.startsWith('data:')) {
        const value = line.replace('data:', '').trim();
        dataStr = dataStr ? `${dataStr}\n${value}` : value;
      }
    }

    if (!dataStr) return null;

    try {
      const parsed = JSON.parse(dataStr);
      // Ensure shape aligns with OrcaBackendEvent
      if (typeof parsed === 'object' && parsed !== null) {
        const normalizedEvent = (parsed.event_type || parsed.event || eventType || 'TOOL_CALL') as any;
        const payload = parsed.payload || {};
        const combinedData = {
          ...parsed,
          ...(parsed.data || {}),
          payload,
          tool: parsed.tool || parsed.data?.tool || payload.tool,
          agent: parsed.agent || parsed.data?.agent || payload.agent,
          node: parsed.node || parsed.data?.node || payload.node,
          status: parsed.status || parsed.data?.status || payload.status,
          answer_text: payload.answer_text || parsed.data?.response || parsed.data?.answer_text,
          response: payload.answer_text || parsed.data?.response,
          plan: payload.plan || parsed.data?.plan,
          overlay: payload.overlay || (normalizedEvent === 'MAP_OVERLAY_UPDATED' ? payload : undefined),
        };

        return {
          event: normalizedEvent,
          run_id: parsed.run_id || `run_${Date.now()}`,
          timestamp: parsed.timestamp || new Date().toISOString(),
          event_id: parsed.event_id,
          sequence: parsed.sequence,
          node: parsed.node,
          agent: parsed.agent,
          tool: parsed.tool,
          status: parsed.status,
          duration_ms: parsed.duration_ms,
          payload,
          data: combinedData,
        };
      }
    } catch {
      // In case server sends raw text
      return {
        event: (eventType as any) || 'TOOL_CALL',
        run_id: `run_${Date.now()}`,
        timestamp: new Date().toISOString(),
        data: {
          response: dataStr,
          answer_text: dataStr,
        },
      };
    }

    return null;
  }
}
