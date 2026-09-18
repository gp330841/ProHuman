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

import { 
  SAMPLE_SESSIONS, 
  SAMPLE_TRANSCRIPTS, 
  SAMPLE_MOM, 
  SAMPLE_SEARCH_RESULTS, 
  SAMPLE_AGENT_RESPONSES 
} from './sampleData';

export const API_BASE = '/api/v1';

export async function fetchSessions(): Promise<Session[]> {
  try {
    const res = await fetch(`${API_BASE}/sessions`, { signal: AbortSignal.timeout(1500) });
    if (!res.ok) throw new Error('Failed to fetch sessions');
    const data = await res.json();
    if (data.sessions && data.sessions.length > 0) return data.sessions;
  } catch (err) {
    console.info('Backend unavailable or empty. Loading sample test sessions.');
  }
  return SAMPLE_SESSIONS;
}

export async function fetchSessionDetails(sessionId: string): Promise<{
  session: Session | null;
  segments: TranscriptSegment[];
  mom: MOMData | null;
}> {
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      const data = await res.json();
      return {
        session: data,
        segments: data.transcript_segments || [],
        mom: data.feature_results?.mom || null
      };
    }
  } catch (err) {
    console.info('Using sample transcript & MOM data for session:', sessionId);
  }

  const sampleSession = SAMPLE_SESSIONS.find((s) => s.id === sessionId) || SAMPLE_SESSIONS[0];
  const sampleSegments = SAMPLE_TRANSCRIPTS[sessionId] || SAMPLE_TRANSCRIPTS['a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d'] || [];
  const sampleMom = SAMPLE_MOM[sessionId] || SAMPLE_MOM['a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d'] || null;

  return {
    session: sampleSession,
    segments: sampleSegments,
    mom: sampleMom
  };
}

export async function createSession(deviceId: string = 'web-gadget-01'): Promise<Session> {
  try {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: deviceId,
        audio_format: 'WAV',
        sample_rate: 16000,
      }),
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.info('Using local simulated session ID for testing.');
  }

  // Fallback demo session
  return {
    id: `sim-${Date.now().toString(36)}`,
    device_id: deviceId,
    status: 'RECORDING',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    audio_format: 'WAV',
    duration_seconds: 0,
  };
}

export async function uploadAudioFile(sessionId: string, file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  try {
    const res = await fetch(`${API_BASE}/audio/${sessionId}/upload`, {
      method: 'POST',
      body: formData,
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.info('Backend upload endpoint offline; simulated mock upload completed.');
  }

  return {
    session_id: sessionId,
    status: 'processing',
    file_name: file.name,
    bytes: file.size,
  };
}

export async function runHybridSearch(query: string, mode: string = 'HYBRID'): Promise<SearchResult[]> {
  try {
    const res = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        search_mode: mode,
        limit: 15,
      }),
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) {
      const data = await res.json();
      return data.results || [];
    }
  } catch (err) {
    console.info('Search API offline; serving sample search results.');
  }

  return SAMPLE_SEARCH_RESULTS.filter(
    (item) => item.text.toLowerCase().includes(query.toLowerCase()) || query.length < 4
  ).concat(SAMPLE_SEARCH_RESULTS);
}

export async function queryAgent(query: string, userId: string = 'user-01'): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/agent/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        user_id: userId,
      }),
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.info('Agent API offline; serving contextual simulated agent answer.');
  }

  await new Promise((resolve) => setTimeout(resolve, 600));
  return SAMPLE_AGENT_RESPONSES.default;
}

