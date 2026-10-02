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

export interface SystemServiceHealth {
  status: string;
  port?: number;
  latency_ms?: number;
  sessions_count?: number;
  transcripts_count?: number;
  moms_count?: number;
  endpoint?: string;
  bucket?: string;
  error?: string;
}

export interface SystemStatus {
  status: string;
  timestamp: string;
  gateway: SystemServiceHealth;
  postgres: SystemServiceHealth;
  redis: SystemServiceHealth;
  agent: SystemServiceHealth;
  storage: SystemServiceHealth;
}

/**
 * Fetches the current health and status of all system components.
 * @returns A promise resolving to the system status object.
 */
export async function fetchSystemStatus(): Promise<SystemStatus> {
  const response = await fetch(`${API_BASE}/system/status`, { signal: AbortSignal.timeout(5000) });
  await ensureOk(response);
  return response.json();
}

/**
 * Flushes all test data from the system databases.
 * @returns A promise resolving to a success message.
 */
export async function flushTestData(): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/system/flush-test-data`, {
    method: 'POST',
    signal: AbortSignal.timeout(10000),
  });
  await ensureOk(response);
  return response.json();
}

/**
 * Fetches a list of sessions, optionally filtered by user ID.
 * @param userId - Optional user identifier to filter sessions.
 * @returns A promise resolving to an array of sessions.
 */
export async function fetchSessions(userId?: string): Promise<Session[]> {
  const url = userId ? `${API_BASE}/sessions?user_id=${encodeURIComponent(userId)}` : `${API_BASE}/sessions`;
  const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
  await ensureOk(response);
  const data: { sessions: Session[] } = await response.json();
  return data.sessions;
}

/**
 * Fetches detailed information for a specific session.
 * @param sessionId - The unique identifier of the session.
 * @returns A promise resolving to the session details including segments and MoM.
 */
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

/**
 * Creates a new recording or upload session.
 * @param deviceId - The device identifier creating the session.
 * @param language - The expected primary language.
 * @param metadata - Additional metadata for the session.
 * @returns A promise resolving to the created session.
 */
export async function createSession(
  deviceId: string = 'web-gadget-01',
  language: string = 'auto',
  metadata: Record<string, any> = {}
): Promise<Session> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: deviceId,
      audio_format: 'OPUS',
      sample_rate: 16000,
      language,
      metadata,
    }),
    signal: AbortSignal.timeout(10000),
  });
  await ensureOk(response);
  return response.json();
}

/**
 * Uploads an audio file for a session.
 * @param sessionId - The session identifier.
 * @param file - The audio file to upload.
 * @returns A promise resolving to upload status.
 */
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

/**
 * Executes a hybrid, semantic, or lexical search over transcripts.
 * @param query - The search query string.
 * @param mode - The search algorithm to use.
 * @returns A promise resolving to an array of search results.
 */
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

/**
 * Triggers the generation of Minutes of Meeting (MoM) for a session.
 * @param sessionId - The session identifier.
 * @param force - Whether to force regeneration if already exists.
 * @returns A promise resolving when the request succeeds.
 */
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

/**
 * Submits a query to the AI agent.
 * @param query - The user's query text.
 * @param userId - The user's identifier.
 * @returns A promise resolving to the agent's response.
 */
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


// --- Export APIs ---

/**
 * Exports the transcript in the requested format.
 * @param sessionId - The session identifier.
 * @param format - The export format.
 * @returns A promise resolving to the exported transcript string.
 */
export async function exportTranscript(
  sessionId: string,
  format: 'markdown' | 'json' = 'markdown',
): Promise<string> {
  const response = await fetch(`${API_BASE}/export/${sessionId}/transcript?format=${format}`, {
    signal: AbortSignal.timeout(30000),
  });
  await ensureOk(response);
  return response.text();
}

/**
 * Exports the Minutes of Meeting in the requested format.
 * @param sessionId - The session identifier.
 * @param format - The export format.
 * @returns A promise resolving to the exported MoM string.
 */
export async function exportMom(
  sessionId: string,
  format: 'markdown' | 'json' = 'markdown',
): Promise<string> {
  const response = await fetch(`${API_BASE}/export/${sessionId}/mom?format=${format}`, {
    signal: AbortSignal.timeout(30000),
  });
  await ensureOk(response);
  return response.text();
}

/**
 * Exports the full session including transcript and MoM.
 * @param sessionId - The session identifier.
 * @param format - The export format.
 * @returns A promise resolving to the exported full session string.
 */
export async function exportFullSession(
  sessionId: string,
  format: 'markdown' | 'json' = 'markdown',
): Promise<string> {
  const response = await fetch(`${API_BASE}/export/${sessionId}/full?format=${format}`, {
    signal: AbortSignal.timeout(30000),
  });
  await ensureOk(response);
  return response.text();
}

/**
 * Deletes a session and its associated data.
 * @param sessionId - The session identifier.
 * @returns A promise resolving when the deletion succeeds.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    signal: AbortSignal.timeout(10000),
  });
  if (response.status !== 204) {
    await ensureOk(response);
  }
}

export interface Language {
  code: string;
  name: string;
}

/**
 * Fetches the supported languages for transcription.
 * @returns A promise resolving to languages and default.
 */
export async function fetchLanguages(): Promise<{ languages: Language[]; default: string }> {
  const response = await fetch(`${API_BASE}/languages`, {
    signal: AbortSignal.timeout(5000),
  });
  await ensureOk(response);
  return response.json();
}

/**
 * Submits transcript segments for a session.
 * @param sessionId - The session identifier.
 * @param segments - Array of transcript segments to submit.
 * @returns A promise resolving on success.
 */
export async function submitSessionTranscript(
  sessionId: string,
  segments: Array<{
    text: string;
    speaker_name?: string;
    start_time?: number;
    end_time?: number;
    confidence?: number;
  }>,
): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/transcript`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ segments }),
    signal: AbortSignal.timeout(10000),
  });
  await ensureOk(response);
}
