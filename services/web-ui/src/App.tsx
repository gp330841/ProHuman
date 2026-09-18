import { useState, useEffect } from 'react';
import { 
  Radio, 
  FileText, 
  Search, 
  Bot, 
  Layers, 
  Activity, 
  RefreshCw,
  Cpu,
  Database
} from 'lucide-react';

import { AudioRecorder } from './components/AudioRecorder';
import { TranscriptViewer } from './components/TranscriptViewer';
import { MomViewer } from './components/MomViewer';
import { SearchExplorer } from './components/SearchExplorer';
import { AgentChat } from './components/AgentChat';
import { fetchSessions, fetchSessionDetails, Session, TranscriptSegment, MOMData } from './api/client';

export default function App() {
  const [activeTab, setActiveTab] = useState<'stream' | 'mom' | 'search' | 'agent'>('stream');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [mom, setMom] = useState<MOMData | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);

  const loadSessions = async () => {
    setIsLoadingSessions(true);
    try {
      const data = await fetchSessions();
      setSessions(data);
      if (data.length > 0 && !selectedSessionId) {
        setSelectedSessionId(data[0].id);
      }
    } finally {
      setIsLoadingSessions(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (selectedSessionId) {
      fetchSessionDetails(selectedSessionId).then((details) => {
        setSegments(details.segments);
        setMom(details.mom);
      });
    }
  }, [selectedSessionId]);

  const handleSessionCreated = (newSession: Session) => {
    setSessions((prev) => [newSession, ...prev]);
    setSelectedSessionId(newSession.id);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-base tracking-tight flex items-center gap-2">
                ProHuman AI
                <span className="text-[10px] bg-sky-500/10 text-sky-400 px-2 py-0.5 rounded-full border border-sky-500/30 uppercase font-mono font-semibold">
                  Gadget Studio
                </span>
              </h1>
              <p className="text-[11px] text-slate-400">Personal Conversation Intelligence Platform</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('stream')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'stream'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Radio className="w-3.5 h-3.5" /> Audio & Streaming
            </button>
            <button
              onClick={() => setActiveTab('mom')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'mom'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" /> Transcript & MOM
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'search'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Search className="w-3.5 h-3.5" /> Hybrid Search
            </button>
            <button
              onClick={() => setActiveTab('agent')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'agent'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Bot className="w-3.5 h-3.5" /> ReAct Agent
            </button>
          </nav>

          {/* System Status Pill */}
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-mono text-[11px]">Services Ready</span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* TAB 1: Live Audio Streaming */}
        {activeTab === 'stream' && (
          <div className="space-y-6">
            <AudioRecorder onSessionCreated={handleSessionCreated} />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                <div className="flex items-center gap-2 text-sky-400 mb-1">
                  <Activity className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">Gateway Port :8000</span>
                </div>
                <p className="text-xs text-slate-400">FastAPI binary WebSocket streaming with bounded queue backpressure.</p>
              </div>
              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                <div className="flex items-center gap-2 text-emerald-400 mb-1">
                  <Database className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">MinIO S3 & PostgreSQL</span>
                </div>
                <p className="text-xs text-slate-400">Opus chunk persistence, SHA-256 idempotency deduplication.</p>
              </div>
              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                <div className="flex items-center gap-2 text-purple-400 mb-1">
                  <Cpu className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">Celery Worker Fleet</span>
                </div>
                <p className="text-xs text-slate-400">Diarization via Deepgram Nova-2 + 1536-dim embeddings via pgvector.</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: Transcript & MOM */}
        {activeTab === 'mom' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Col: Sessions List */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 h-fit">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-sky-400" /> Past Sessions
                </h3>
                <button
                  onClick={loadSessions}
                  className="p-1 text-slate-400 hover:text-slate-200 transition"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingSessions ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {sessions.length > 0 ? (
                <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                  {sessions.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setSelectedSessionId(s.id)}
                      className={`w-full text-left p-3 rounded-lg border text-xs transition ${
                        selectedSessionId === s.id
                          ? 'bg-sky-500/10 border-sky-500/40 text-white'
                          : 'bg-slate-950/60 border-slate-800/80 text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono font-semibold">{s.device_id}</span>
                        <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                          {s.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 font-mono truncate">{s.id}</p>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 text-center py-6">No sessions recorded yet.</p>
              )}
            </div>

            {/* Right Col: Transcript + MOM */}
            <div className="lg:col-span-2 space-y-6">
              <TranscriptViewer segments={segments} />
              <MomViewer
                mom={mom}
                onGenerateMOM={() => {
                  // Simulate sample MOM extraction
                  setMom({
                    title: 'Q3 Product Strategy & Roadmap',
                    attendees: ['speaker_0', 'speaker_1'],
                    agenda_items: [
                      { topic: 'Hardware Firmware v2', summary: 'Discussion on ESP32 Opus audio streaming codec and I2S buffer latency' },
                      { topic: 'Backend Deployment', summary: 'Agreed to spin up Celery workers with 4-concurrency for embeddings' }
                    ],
                    decisions: [
                      { description: 'Ship Deepgram Nova-2 as primary speech recognition engine', made_by: 'speaker_0' },
                      { description: 'Enable pgvector HNSW indexing with cosine distance metric', made_by: 'speaker_1' }
                    ],
                    action_items: [
                      { description: 'Configure Redis Streams dead-letter queue replay policy', assignee: 'DevOps Lead', priority: 'high', deadline: '2026-09-25' },
                      { description: 'Benchmark Web Audio API chunking overhead in browser', assignee: 'Frontend Engineer', priority: 'medium' }
                    ],
                    follow_ups: [
                      { description: 'Sync on battery consumption with hardware engineering team' }
                    ],
                    executive_summary: 'The team aligned on shipping the hardware prototype with Nova-2 diarization and pgvector hybrid search across conversation sessions.'
                  });
                }}
              />
            </div>
          </div>
        )}

        {/* TAB 3: Hybrid Search */}
        {activeTab === 'search' && <SearchExplorer />}

        {/* TAB 4: ReAct Agent */}
        {activeTab === 'agent' && <AgentChat />}
      </main>
    </div>
  );
}
