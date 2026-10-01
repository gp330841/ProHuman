export interface Session {
  id: string;
  device_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  audio_format?: string;
  duration_seconds?: number;
}

export interface TranscriptSegment {
  segment_id?: string;
  id?: string;
  speaker_label: string;
  speaker_name?: string;
  text: string;
  start_time: number;
  end_time: number;
  confidence?: number;
  rrf_score?: number;
  vector_rank?: number;
  text_rank?: number;
}

export interface ActionItem {
  description: string;
  assignee?: string;
  deadline?: string;
  priority?: 'critical' | 'high' | 'medium' | 'low';
  confidence?: number;
  status?: string;
}

export interface Decision {
  description: string;
  made_by?: string;
  confidence?: number;
  timestamp?: number;
}

export interface AgendaItem {
  topic: string;
  summary: string;
  speakers_involved?: string[];
}

export interface MOMData {
  title: string;
  date?: string;
  attendees: string[];
  agenda_items: AgendaItem[];
  decisions: Decision[];
  action_items: ActionItem[];
  follow_ups: Array<{ description: string; responsible_party?: string }>;
  executive_summary: string;
}

export interface SearchResult {
  segment_id: string;
  session_id: string;
  speaker_label: string;
  text: string;
  start_time: number;
  end_time: number;
  rrf_score: number;
  vector_rank?: number;
  text_rank?: number;
}

export const API_BASE = '/api/v1';

async function ensureOk(response: Response): Promise<void> {
  if (response.ok) return;
  let message = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    message = body.detail || body.message || message;
  } catch {
    // Preserve the HTTP status when an error response has no JSON body.
  }
  throw new Error(message);
}

export async function fetchSessions(): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/sessions`, { signal: AbortSignal.timeout(10000) });
  await ensureOk(response);
  const data: { sessions: Session[] } = await response.json();
  return data.sessions;
}

export async function fetchSessionDetails(sessionId: string): Promise<{
  session: Session | null;
  segments: TranscriptSegment[];
  mom: MOMData | null;
}> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, { signal: AbortSignal.timeout(10000) });
  await ensureOk(response);
  const data = await response.json();
  return {
    session: data as Session,
    segments: (data.transcript_segments || []) as TranscriptSegment[],
    mom: (data.feature_results?.mom || null) as MOMData | null,
  };
}

export async function createSession(deviceId: string = 'web-gadget-01'): Promise<Session> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: deviceId,
      audio_format: 'OPUS',
      sample_rate: 16000,
    }),
    signal: AbortSignal.timeout(10000),
  });
  await ensureOk(response);
  return response.json();
}

export async function uploadAudioFile(
  sessionId: string,
  file: File,
): Promise<{ session_id: string; status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE}/audio/${sessionId}/upload`, {
    method: 'POST',
    body: formData,
    signal: AbortSignal.timeout(120000),
  });
  await ensureOk(response);
  return response.json();
}

export async function runHybridSearch(
  query: string,
  mode: 'HYBRID' | 'SEMANTIC' | 'LEXICAL' = 'HYBRID',
): Promise<SearchResult[]> {
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      search_mode: mode,
      limit: 15,
    }),
    signal: AbortSignal.timeout(30000),
  });
  await ensureOk(response);
  const data: { results: SearchResult[] } = await response.json();
  return data.results;
}

export async function generateMom(sessionId: string, force = false): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/features`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feature_names: ['mom'], force }),
    signal: AbortSignal.timeout(10000),
  });
  await ensureOk(response);
}

export interface AgentResponse {
  response: string;
  query_id: string;
  tool_calls_count: number;
  tokens_used: number;
  latency_ms: number;
}

export async function queryAgent(query: string, userId: string = 'user-01'): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/agent/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      user_id: userId,
    }),
    signal: AbortSignal.timeout(120000),
  });
  await ensureOk(response);
  return response.json();
}
