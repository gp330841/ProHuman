import { useState, useEffect, useRef } from 'react';
import {
  Radio,
  FileText,
  Search,
  Bot,
  Layers,
  Activity,
  RefreshCw,
  Cpu,
  Database,
  Sparkles,
  ShieldCheck,
  ArrowUpRight,
} from 'lucide-react';

import { AudioRecorder } from './components/AudioRecorder';
import { TranscriptViewer } from './components/TranscriptViewer';
import { MomViewer } from './components/MomViewer';
import { SearchExplorer } from './components/SearchExplorer';
import { AgentChat } from './components/AgentChat';
import { fetchSessions, fetchSessionDetails, generateMom, Session, TranscriptSegment, MOMData } from './api/client';

export default function App() {
  const [activeTab, setActiveTab] = useState<'stream' | 'mom' | 'search' | 'agent'>('stream');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [mom, setMom] = useState<MOMData | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isGeneratingMom, setIsGeneratingMom] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [gatewayConnected, setGatewayConnected] = useState(false);
  const momSnapshotRef = useRef<string | null>(null);
  const momTimeoutRef = useRef<number | undefined>(undefined);

  const tabConfig = [
    { id: 'stream', label: 'Audio & Streaming', icon: Radio },
    { id: 'mom', label: 'Transcript & MOM', icon: FileText },
    { id: 'search', label: 'Hybrid Search', icon: Search },
    { id: 'agent', label: 'ReAct Agent', icon: Bot },
  ] as const;

  const overviewCards = [
    { title: 'Gateway', value: ':8000', details: 'WebSocket ingest', accent: 'sky' },
    { title: 'Storage', value: 'MinIO + PG', details: 'Audio + vectors', accent: 'emerald' },
    { title: 'Workers', value: '3 Queues', details: 'STT + embeddings', accent: 'violet' },
  ] as const;

  const loadSessions = async () => {
    setIsLoadingSessions(true);
    try {
      const data = await fetchSessions();
      setSessions(data);
      setGatewayConnected(true);
      setApiError(null);
      if (data.length > 0 && !selectedSessionId) {
        setSelectedSessionId(data[0].id);
      }
    } catch (error: unknown) {
      setGatewayConnected(false);
      setApiError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsLoadingSessions(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (!selectedSessionId) {
      setSegments([]);
      setMom(null);
      return;
    }

    let disposed = false;
    let timer: number | undefined;
    const refreshDetails = async () => {
      setIsLoadingDetails(true);
      try {
        const details = await fetchSessionDetails(selectedSessionId);
        if (disposed) return;
        setSegments(details.segments);
        setMom(details.mom);
        if (
          isGeneratingMom &&
          details.mom &&
          JSON.stringify(details.mom) !== momSnapshotRef.current
        ) {
          if (momTimeoutRef.current !== undefined) {
            window.clearTimeout(momTimeoutRef.current);
            momTimeoutRef.current = undefined;
          }
          setIsGeneratingMom(false);
        }
        setSessions((current) =>
          current.map((item) => item.id === selectedSessionId ? details.session ?? item : item),
        );
        setGatewayConnected(true);
        setApiError(null);
        if (isGeneratingMom || !['COMPLETED', 'FAILED'].includes(details.session?.status ?? '')) {
          timer = window.setTimeout(refreshDetails, 3000);
        }
      } catch (error: unknown) {
        if (!disposed) {
          setApiError(error instanceof Error ? error.message : String(error));
          timer = window.setTimeout(refreshDetails, 5000);
        }
      } finally {
        if (!disposed) setIsLoadingDetails(false);
      }
    };

    void refreshDetails();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [selectedSessionId, isGeneratingMom]);

  const handleSessionCreated = (newSession: Session) => {
    setSessions((prev) => [newSession, ...prev]);
    setSelectedSessionId(newSession.id);
    setApiError(null);
  };

  const handleGenerateMom = async () => {
    if (!selectedSessionId) {
      setApiError('Select a session with a transcript before generating meeting notes.');
      return;
    }
    try {
      if (momTimeoutRef.current !== undefined) window.clearTimeout(momTimeoutRef.current);
      setIsGeneratingMom(true);
      momSnapshotRef.current = mom ? JSON.stringify(mom) : null;
      setApiError(null);
      await generateMom(selectedSessionId, Boolean(mom));
      setApiError('Meeting notes are queued and will appear here when processing finishes.');
      momTimeoutRef.current = window.setTimeout(() => {
        setIsGeneratingMom(false);
        momTimeoutRef.current = undefined;
      }, 60000);
    } catch (error: unknown) {
      if (momTimeoutRef.current !== undefined) {
        window.clearTimeout(momTimeoutRef.current);
        momTimeoutRef.current = undefined;
      }
      setApiError(error instanceof Error ? error.message : String(error));
      setIsGeneratingMom(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col app-shell">
      <header className="border-b border-slate-800/80 bg-slate-950/75 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 via-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20 ring-1 ring-sky-400/30">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="font-bold text-base tracking-tight flex items-center gap-2 flex-wrap">
                ProHuman AI
                <span className="text-[10px] bg-sky-500/10 text-sky-400 px-2 py-0.5 rounded-full border border-sky-500/30 uppercase font-mono font-semibold">
                  Gadget Studio
                </span>
              </h1>
              <p className="text-[11px] text-slate-400 truncate">Personal Conversation Intelligence Platform</p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800 shadow-lg shadow-slate-950/40 overflow-x-auto max-w-[45vw] md:max-w-none">
            {tabConfig.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  activeTab === id
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-2 text-xs text-slate-400 whitespace-nowrap">
            <span className={`w-2 h-2 rounded-full ${gatewayConnected ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            <span className="font-mono text-[11px]">{gatewayConnected ? 'Gateway online' : 'Gateway offline'}</span>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        {activeTab === 'stream' && (
          <div className="space-y-6">
            <section className="glass-panel overflow-hidden">
              <div className="px-5 py-4 md:px-6 md:py-5 border-b border-slate-800/80 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-sky-300">Control center</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white tracking-tight">Live conversation pipeline</h2>
                </div>
                <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-medium ${
                  gatewayConnected
                    ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                    : 'border-rose-500/20 bg-rose-500/10 text-rose-300'
                }`}>
                  <ShieldCheck className="w-3.5 h-3.5" />
                  {gatewayConnected ? 'Gateway connected' : 'Waiting for gateway'}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-5 md:p-6">
                {overviewCards.map(({ title, value, details, accent }) => (
                  <div key={title} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg shadow-slate-950/30 transition hover:border-slate-700">
                    <div className="flex items-center justify-between">
                      <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${
                        accent === 'sky'
                          ? 'border-sky-500/30 bg-sky-500/10 text-sky-300'
                          : accent === 'emerald'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            : 'border-violet-500/30 bg-violet-500/10 text-violet-300'
                      }`}>
                        {title}
                      </span>
                      <ArrowUpRight className="w-4 h-4 text-slate-400" />
                    </div>
                    <p className="mt-4 text-2xl font-semibold text-white">{value}</p>
                    <p className="mt-1 text-sm text-slate-400">{details}</p>
                  </div>
                ))}
              </div>
            </section>

            <AudioRecorder onSessionCreated={handleSessionCreated} />

            <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="glass-panel p-4">
                <div className="flex items-center gap-2 text-sky-400 mb-1">
                  <Activity className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">Gateway Port :8000</span>
                </div>
                <p className="text-xs text-slate-400">FastAPI binary websocket streaming with bounded queue backpressure.</p>
              </div>
              <div className="glass-panel p-4">
                <div className="flex items-center gap-2 text-emerald-400 mb-1">
                  <Database className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">MinIO + PostgreSQL</span>
                </div>
                <p className="text-xs text-slate-400">Chunk persistence, deduplication, and vector-store indexing in one flow.</p>
              </div>
              <div className="glass-panel p-4">
                <div className="flex items-center gap-2 text-violet-400 mb-1">
                  <Sparkles className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">Celery Worker Fleet</span>
                </div>
                <p className="text-xs text-slate-400">Diarization via Deepgram Nova-2 plus semantic embeddings via pgvector.</p>
              </div>
            </section>
          </div>
        )}

        {apiError && (
          <div role="status" className={`rounded-xl border px-4 py-3 text-sm ${
            apiError.includes('queued')
              ? 'border-sky-500/30 bg-sky-500/10 text-sky-200'
              : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
          }`}>
            {apiError}
          </div>
        )}

        {activeTab === 'mom' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 h-fit glass-panel">
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

            <div className="lg:col-span-2 space-y-6">
              <TranscriptViewer segments={segments} isLoading={isLoadingDetails} />
              <MomViewer
                mom={mom}
                onGenerateMOM={handleGenerateMom}
                isGenerating={isGeneratingMom}
              />
            </div>
          </div>
        )}

        {activeTab === 'search' && <SearchExplorer />}
        {activeTab === 'agent' && <AgentChat />}
      </main>
    </div>
  );
}
