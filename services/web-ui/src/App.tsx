import { useState, useEffect, useRef } from 'react';
import {
  Radio,
  FileText,
  Search,
  Bot,
  Layers,
  Sparkles,
  RefreshCw,
  Clock,
  ArrowRight,
  Trash2,
  Sun,
  Moon,
} from 'lucide-react';

import { AudioRecorder } from './components/AudioRecorder';
import { TranscriptViewer } from './components/TranscriptViewer';
import { MomViewer } from './components/MomViewer';
import { SearchExplorer } from './components/SearchExplorer';
import { AgentChat } from './components/AgentChat';
import { Timeline } from './components/Timeline';
import { UserSessionModal } from './components/UserSessionModal';
import { useUser } from './context/UserContext';
import { useTheme } from './context/ThemeContext';
import { 
  fetchSessions, 
  fetchSessionDetails, 
  generateMom, 
  Session, 
  TranscriptSegment, 
  MOMData,
  flushTestData
} from './api/client';

export default function App() {
  const { activeUser, filterByUserOnly, setFilterByUserOnly } = useUser();
  const { theme, toggleTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<'stream' | 'mom' | 'search' | 'agent' | 'timeline'>('stream');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [mom, setMom] = useState<MOMData | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isGeneratingMom, setIsGeneratingMom] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [gatewayConnected, setGatewayConnected] = useState(true);
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const momSnapshotRef = useRef<string | null>(null);
  const momTimeoutRef = useRef<number | undefined>(undefined);

  const [refreshCount, setRefreshCount] = useState(0);

  const tabConfig = [
    { id: 'stream' as const, label: 'Audio & Live Studio', icon: Radio },
    { id: 'mom' as const, label: 'Transcript & MOM', icon: FileText },
    { id: 'agent' as const, label: 'ReAct Agent', icon: Bot },
    { id: 'search' as const, label: 'AI Search', icon: Search },
    { id: 'timeline' as const, label: 'Memory Timeline', icon: Layers },
  ];

  const loadSessions = async () => {
    setIsLoadingSessions(true);
    try {
      const data = await fetchSessions(filterByUserOnly ? activeUser.id : undefined);
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
  }, [activeTab, filterByUserOnly, activeUser.id]);

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
        const isTerminal = ['COMPLETED', 'FAILED'].includes(details.session?.status ?? '');
        if (isGeneratingMom || !isTerminal) {
          timer = window.setTimeout(refreshDetails, 2500);
        }
      } catch (error: unknown) {
        if (!disposed) {
          setApiError(error instanceof Error ? error.message : String(error));
          timer = window.setTimeout(refreshDetails, 4000);
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
  }, [selectedSessionId, isGeneratingMom, refreshCount, activeTab]);

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
      setApiError('Meeting notes are being generated with Gemini in Hinglish...');
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

  const handleClearData = async () => {
    if (!window.confirm('Delete all test/simulated data? Your recorded memories will be cleared.')) return;
    try {
      await flushTestData();
      setSelectedSessionId(null);
      setSegments([]);
      setMom(null);
      await loadSessions();
      setApiError('Test data cleared successfully.');
    } catch (e: any) {
      setApiError(`Failed to clear test data: ${e.message}`);
    }
  };

  return (
    <div className="min-h-screen text-slate-800 dark:text-slate-100 flex flex-col antialiased selection:bg-sky-500/30">
      {/* Sleek Floating Header */}
      <header className="border-b border-slate-200/80 dark:border-white/[0.08] bg-white/70 dark:bg-slate-950/70 backdrop-blur-2xl sticky top-0 z-50 transition-all">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between gap-4">
          {/* Logo / Brand */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-sky-400 via-cyan-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/25 ring-1 ring-black/10 dark:ring-white/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-base tracking-tight text-slate-900 dark:text-white">
                  ProHuman
                </h1>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-sky-50 dark:bg-white/[0.06] text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-white/[0.1] font-semibold">
                  AI Intelligence
                </span>
              </div>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 hidden sm:block">Personal Conversation Memory & Insights</p>
            </div>
          </div>

          {/* Navigation Pills */}
          <nav className="flex items-center gap-1 bg-slate-100/80 dark:bg-white/[0.03] p-1 rounded-full border border-slate-200 dark:border-white/[0.08] backdrop-blur-md overflow-x-auto max-w-[48vw] md:max-w-none">
            {tabConfig.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium transition cursor-pointer ${
                  activeTab === id
                    ? 'bg-gradient-to-r from-sky-500 to-indigo-600 text-white shadow-md shadow-sky-500/20'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </nav>

          {/* Right: Theme Toggle, User Profile & Status */}
          <div className="flex items-center gap-2">
            {/* Light / Dark Mode Toggle Button */}
            <button
              onClick={toggleTheme}
              className="w-8 h-8 rounded-full flex items-center justify-center glass-pill text-slate-700 dark:text-slate-300 hover:text-sky-500 dark:hover:text-sky-400 transition cursor-pointer"
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-slate-700" />
              )}
            </button>

            {/* User Session Profile Button */}
            <button
              onClick={() => setIsUserModalOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 glass-pill rounded-full hover:border-slate-300 dark:hover:border-white/20 transition cursor-pointer text-left"
              title="Manage user session & switch profile"
            >
              <div
                className={`w-6 h-6 rounded-full bg-gradient-to-tr ${activeUser.gradient} flex items-center justify-center text-white font-bold text-xs shrink-0 shadow-sm`}
              >
                {activeUser.name.charAt(0)}
              </div>
              <div className="hidden sm:block min-w-0 pr-1">
                <p className="text-xs font-semibold text-slate-900 dark:text-white leading-tight truncate">{activeUser.name}</p>
              </div>
            </button>

            {/* Subtle Status Dot */}
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.06] text-[11px] font-mono text-slate-600 dark:text-slate-400">
              <span className={`w-2 h-2 rounded-full ${gatewayConnected ? 'bg-emerald-500 dark:bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
              <span className="hidden md:inline">{gatewayConnected ? 'Live' : 'Offline'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        {/* Error / Notice Notification Banner */}
        {apiError && (
          <div role="status" className={`rounded-2xl border px-4 py-3 text-xs md:text-sm flex items-center justify-between gap-3 shadow-sm ${
            apiError.includes('queued') || apiError.includes('generated') || apiError.includes('cleared')
              ? 'border-sky-500/30 bg-sky-50 dark:bg-sky-950/40 text-sky-800 dark:text-sky-200'
              : 'border-rose-500/30 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200'
          }`}>
            <span>{apiError}</span>
            <button 
              onClick={() => setApiError(null)} 
              className="text-xs opacity-70 hover:opacity-100 underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Tab 1: Live Voice Studio & Recent Sessions */}
        {activeTab === 'stream' && (
          <div className="space-y-6">
            <AudioRecorder
              onSessionCreated={handleSessionCreated}
              onViewTranscript={(sessionId) => {
                setSelectedSessionId(sessionId);
                setRefreshCount((c) => c + 1);
                setActiveTab('mom');
                loadSessions();
              }}
            />

            {/* Recent Recorded Conversations Carousel / List */}
            <div className="glass-card rounded-3xl p-6 md:p-8 relative overflow-hidden">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base md:text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <Clock className="w-4 h-4 text-sky-500 dark:text-sky-400" />
                    Recent Conversations & Meetings
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Click any session to view speaker-attributed transcripts, smart executive titles, and MOM
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={loadSessions}
                    className="p-1.5 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white glass-pill rounded-xl transition cursor-pointer"
                    title="Refresh sessions"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isLoadingSessions ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={handleClearData}
                    className="text-xs text-rose-600 dark:text-rose-400 hover:text-rose-700 dark:hover:text-rose-300 bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 dark:hover:bg-rose-500/20 border border-rose-200 dark:border-rose-500/30 px-3 py-1.5 rounded-xl transition cursor-pointer flex items-center gap-1.5"
                    title="Clear test data"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Clear Test Data</span>
                  </button>
                </div>
              </div>

              {sessions.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {sessions.slice(0, 6).map((s) => (
                    <div
                      key={s.id}
                      onClick={() => {
                        setSelectedSessionId(s.id);
                        setActiveTab('mom');
                      }}
                      className="p-4 rounded-2xl bg-white/60 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] hover:border-sky-400 dark:hover:border-sky-500/40 hover:bg-slate-50 dark:hover:bg-white/[0.05] transition-all cursor-pointer group flex flex-col justify-between shadow-sm"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span className="text-xs font-semibold text-slate-800 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition truncate">
                            {s.device_id}
                          </span>
                          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30">
                            {s.status}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                          {new Date(s.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>

                      <div className="mt-4 pt-3 border-t border-slate-100 dark:border-white/[0.05] flex items-center justify-between text-xs text-sky-600 dark:text-sky-400 group-hover:text-sky-500 dark:group-hover:text-sky-300">
                        <span>Open Transcript & MOM</span>
                        <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-slate-400 dark:text-slate-500 text-xs">
                  No recorded meetings yet. Tap 'Record' above to capture your first conversation turn.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Transcript & MOM */}
        {activeTab === 'mom' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Sidebar: Session Selector */}
            <div className="glass-card rounded-3xl p-5 h-fit space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/[0.08]">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-sky-500 dark:text-sky-400" /> Meeting History
                </h3>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setFilterByUserOnly(!filterByUserOnly)}
                    className={`px-2.5 py-1 rounded-full text-[10px] font-semibold border transition cursor-pointer ${
                      filterByUserOnly
                        ? 'bg-sky-50 dark:bg-sky-500/20 border-sky-300 dark:border-sky-500/40 text-sky-700 dark:text-sky-300'
                        : 'glass-pill text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    {filterByUserOnly ? 'My Sessions' : 'All Sessions'}
                  </button>
                  <button
                    onClick={loadSessions}
                    className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white transition cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isLoadingSessions ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              {sessions.length > 0 ? (
                <div className="space-y-2 max-h-[550px] overflow-y-auto pr-1">
                  {sessions.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => {
                        setSelectedSessionId(s.id);
                        setRefreshCount((c) => c + 1);
                      }}
                      className={`w-full text-left p-3.5 rounded-2xl border text-xs transition cursor-pointer ${
                        selectedSessionId === s.id
                          ? 'bg-gradient-to-r from-sky-500/10 to-indigo-500/10 dark:from-sky-500/20 dark:to-indigo-500/20 border-sky-500/50 text-slate-900 dark:text-white shadow-sm'
                          : 'bg-white/40 dark:bg-white/[0.02] border-slate-200 dark:border-white/[0.06] text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-white/[0.15]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-slate-900 dark:text-white">{s.device_id}</span>
                        <span className="uppercase text-[9px] px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.05] text-slate-500 dark:text-slate-400 font-mono">
                          {s.status}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                        {new Date(s.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-6">No sessions recorded yet.</p>
              )}
            </div>

            {/* Main Content Area */}
            <div className="lg:col-span-2 space-y-6">
              <MomViewer
                mom={mom}
                sessionId={selectedSessionId}
                onGenerateMOM={handleGenerateMom}
                onSessionDeleted={() => {
                  setSelectedSessionId(null);
                  loadSessions();
                }}
                isGenerating={isGeneratingMom}
              />
              <TranscriptViewer segments={segments} isLoading={isLoadingDetails} />
            </div>
          </div>
        )}

        {/* Tab 3: ReAct Agent */}
        {activeTab === 'agent' && <AgentChat />}

        {/* Tab 4: AI Semantic & Hybrid Search */}
        {activeTab === 'search' && (
          <SearchExplorer
            onSelectSession={(sessionId) => {
              setSelectedSessionId(sessionId);
              setActiveTab('mom');
            }}
          />
        )}

        {/* Tab 5: Memory Timeline */}
        {activeTab === 'timeline' && (
          <Timeline
            sessions={sessions}
            selectedSessionId={selectedSessionId}
            onSelectSession={(id) => {
              setSelectedSessionId(id);
              setActiveTab('mom');
            }}
          />
        )}
      </main>

      {/* User Session Modal */}
      <UserSessionModal
        isOpen={isUserModalOpen}
        onClose={() => setIsUserModalOpen(false)}
      />
    </div>
  );
}
