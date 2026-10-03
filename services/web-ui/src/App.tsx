import { useState, useEffect, useRef } from 'react';
import {
  Radio,
  FileText,
  Search,
  Bot,
  Layers,
  RefreshCw,
  Clock,
  ArrowRight,
  Trash2,
  Sun,
  Moon,
  Menu,
  X,
  Mic,
  ChevronRight,
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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const momSnapshotRef = useRef<string | null>(null);
  const momTimeoutRef = useRef<number | undefined>(undefined);
  const [refreshCount, setRefreshCount] = useState(0);

  const tabConfig = [
    {
      id: 'stream' as const, label: 'Live Studio', sublabel: 'Record & capture', icon: Radio,
      activeIcon: 'text-sky-500 dark:text-sky-400',
      mobileActive: 'text-sky-600 dark:text-sky-300 bg-sky-50 dark:bg-sky-500/10 border-sky-200 dark:border-sky-500/25',
    },
    {
      id: 'mom' as const, label: 'Transcript & MOM', sublabel: 'Notes & decisions', icon: FileText,
      activeIcon: 'text-indigo-500 dark:text-indigo-400',
      mobileActive: 'text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 border-indigo-200 dark:border-indigo-500/25',
    },
    {
      id: 'agent' as const, label: 'AI Agent', sublabel: 'ReAct intelligence', icon: Bot,
      activeIcon: 'text-violet-500 dark:text-violet-400',
      mobileActive: 'text-violet-600 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/10 border-violet-200 dark:border-violet-500/25',
    },
    {
      id: 'search' as const, label: 'AI Search', sublabel: 'Semantic explorer', icon: Search,
      activeIcon: 'text-emerald-500 dark:text-emerald-400',
      mobileActive: 'text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/25',
    },
    {
      id: 'timeline' as const, label: 'Memory Timeline', sublabel: 'History view', icon: Layers,
      activeIcon: 'text-amber-500 dark:text-amber-400',
      mobileActive: 'text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/25',
    },
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
      setApiError('Meeting notes are being generated in Hinglish...');
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

  const activeTabConfig = tabConfig.find(t => t.id === activeTab)!;

  return (
    <div className="min-h-screen text-slate-800 dark:text-slate-100 flex flex-col antialiased">

      {/* ===== HEADER ===== */}
      <header className="sticky top-0 z-50 border-b border-slate-200/70 dark:border-white/[0.07] bg-white/75 dark:bg-[#060a12]/80 backdrop-blur-2xl">
        <div className="max-w-screen-2xl mx-auto px-4 md:px-6 h-[60px] flex items-center gap-4">

          {/* Brand */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-sky-400 via-cyan-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/30 ring-1 ring-white/20">
              <Mic className="w-4 h-4 text-white" strokeWidth={2.5} />
            </div>
            <div className="hidden sm:block">
              <div className="flex items-baseline gap-2">
                <span className="font-bold text-sm tracking-tight text-slate-900 dark:text-white">ProHuman</span>
                <span className="text-[9px] uppercase font-mono tracking-widest text-slate-400 dark:text-slate-500">AI Platform</span>
              </div>
            </div>
          </div>

          {/* Desktop Tab Navigation */}
          <nav className="hidden md:flex flex-1 items-center gap-0.5 ml-4">
            {tabConfig.map(({ id, label, icon: Icon, activeIcon }) => {
              const isActive = activeTab === id;
              return (
                <button
                  key={id}
                  onClick={() => { setActiveTab(id); setMobileNavOpen(false); }}
                  className={`relative flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium transition-all duration-200 cursor-pointer ${
                    isActive
                      ? 'text-slate-900 dark:text-white bg-white dark:bg-white/[0.07] shadow-sm border border-slate-200/80 dark:border-white/[0.08]'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100/60 dark:hover:bg-white/[0.04]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? activeIcon : ''}`} />
                  <span>{label}</span>
                  {isActive && (
                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 rounded-full bg-gradient-to-r from-sky-500 to-indigo-500" />
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Controls */}
          <div className="flex items-center gap-2 ml-auto shrink-0">
            {/* Connection Status */}
            <div className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium border transition-all ${
              gatewayConnected
                ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/25 text-emerald-700 dark:text-emerald-400'
                : 'bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/25 text-rose-700 dark:text-rose-400'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${gatewayConnected ? 'bg-emerald-500 animate-status-live' : 'bg-rose-500'}`} />
              <span>{gatewayConnected ? 'Connected' : 'Offline'}</span>
            </div>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="w-8 h-8 rounded-lg flex items-center justify-center glass-pill text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition cursor-pointer"
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {theme === 'dark'
                ? <Sun className="w-3.5 h-3.5 text-amber-400" />
                : <Moon className="w-3.5 h-3.5" />
              }
            </button>

            {/* User avatar */}
            <button
              onClick={() => setIsUserModalOpen(true)}
              className="flex items-center gap-2 px-2.5 py-1.5 glass-pill rounded-xl hover:border-slate-300 dark:hover:border-white/20 transition cursor-pointer"
            >
              <div className={`w-5 h-5 rounded-lg bg-gradient-to-tr ${activeUser.gradient} flex items-center justify-center text-white font-bold text-[10px] shrink-0 shadow-sm`}>
                {activeUser.name.charAt(0)}
              </div>
              <span className="hidden sm:block text-xs font-semibold text-slate-900 dark:text-white">{activeUser.name.split(' ')[0]}</span>
            </button>

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobileNavOpen(p => !p)}
              className="md:hidden w-8 h-8 rounded-lg flex items-center justify-center glass-pill transition cursor-pointer"
            >
              {mobileNavOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav Dropdown */}
        {mobileNavOpen && (
          <div className="md:hidden border-t border-slate-200 dark:border-white/[0.06] bg-white/95 dark:bg-[#08101e]/95 backdrop-blur-xl px-4 py-3 space-y-1 animate-fade-in">
            {tabConfig.map(({ id, label, sublabel, icon: Icon, mobileActive }) => {
              const isActive = activeTab === id;
              return (
                <button
                  key={id}
                  onClick={() => { setActiveTab(id); setMobileNavOpen(false); }}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition cursor-pointer ${
                    isActive
                      ? `${mobileActive} border font-semibold`
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/[0.04]'
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <div className="text-left">
                    <div className="font-medium leading-none">{label}</div>
                    <div className="text-[10px] opacity-60 mt-0.5">{sublabel}</div>
                  </div>
                  {isActive && <ChevronRight className="w-4 h-4 ml-auto opacity-50" />}
                </button>
              );
            })}
          </div>
        )}
      </header>

      {/* ===== MAIN ===== */}
      <main className="flex-1 max-w-screen-2xl w-full mx-auto px-4 md:px-6 py-6 space-y-5">

        {/* Page Title Row (desktop) */}
        <div className="hidden md:flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2.5">
              <activeTabConfig.icon className={`w-5 h-5 ${activeTabConfig.activeIcon}`} />
              {activeTabConfig.label}
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{activeTabConfig.sublabel}</p>
          </div>
          {activeTab === 'stream' && (
            <button
              onClick={handleClearData}
              className="text-xs text-rose-600 dark:text-rose-400 hover:text-rose-700 bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 border border-rose-200 dark:border-rose-500/25 px-3 py-1.5 rounded-xl transition cursor-pointer flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear Test Data
            </button>
          )}
        </div>

        {/* Error / Info Banner */}
        {apiError && (
          <div role="status" className={`animate-fade-in-up rounded-2xl border px-4 py-3 text-xs flex items-center justify-between gap-3 shadow-sm ${
            apiError.includes('queued') || apiError.includes('generated') || apiError.includes('cleared') || apiError.includes('Hinglish')
              ? 'border-sky-400/30 bg-sky-50 dark:bg-sky-950/40 text-sky-800 dark:text-sky-200'
              : 'border-rose-400/30 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200'
          }`}>
            <span>{apiError}</span>
            <button onClick={() => setApiError(null)} className="opacity-60 hover:opacity-100 text-[11px] underline cursor-pointer shrink-0">Dismiss</button>
          </div>
        )}

        {/* ─── TAB: Live Studio ─── */}
        {activeTab === 'stream' && (
          <div className="space-y-5 animate-fade-in-up">
            <AudioRecorder
              onSessionCreated={handleSessionCreated}
              onViewTranscript={(sessionId) => {
                setSelectedSessionId(sessionId);
                setRefreshCount((c) => c + 1);
                setActiveTab('mom');
                loadSessions();
              }}
            />

            {/* Recent Sessions */}
            <div className="glass-card rounded-3xl p-6 md:p-8">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2 text-base">
                    <Clock className="w-4 h-4 text-sky-500" />
                    Recent Conversations
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">Click a session to view speaker transcript & meeting notes</p>
                </div>
                <button
                  onClick={loadSessions}
                  className="p-2 glass-pill rounded-xl text-slate-500 hover:text-slate-900 dark:hover:text-white transition cursor-pointer"
                  title="Refresh"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingSessions ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {sessions.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {sessions.slice(0, 6).map((s) => (
                    <div
                      key={s.id}
                      onClick={() => { setSelectedSessionId(s.id); setActiveTab('mom'); }}
                      className="group p-4 rounded-2xl bg-white/60 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] hover:border-sky-400/60 dark:hover:border-sky-500/40 hover:shadow-md hover:shadow-sky-500/5 transition-all cursor-pointer glass-card-hover flex flex-col justify-between min-h-[110px]"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span className="text-xs font-semibold text-slate-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition truncate">
                            {s.device_id}
                          </span>
                          <span className={`text-[9px] uppercase font-mono px-2 py-0.5 rounded-full border shrink-0 ${
                            s.status === 'COMPLETED'
                              ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/25'
                              : s.status === 'RECORDING'
                              ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/25'
                              : 'bg-slate-100 dark:bg-white/[0.05] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-white/[0.08]'
                          }`}>
                            {s.status}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                          {new Date(s.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-100 dark:border-white/[0.04] flex items-center justify-between text-[11px] text-sky-600 dark:text-sky-400">
                        <span>Open Transcript & MOM</span>
                        <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 space-y-2">
                  <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.07] flex items-center justify-center mx-auto">
                    <Mic className="w-6 h-6 text-slate-400" />
                  </div>
                  <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">No recordings yet</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">Tap the record button above to capture your first conversation</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── TAB: Transcript & MOM ─── */}
        {activeTab === 'mom' && (
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5 animate-fade-in-up">
            {/* Sidebar */}
            <div className="glass-card rounded-3xl p-5 h-fit space-y-4 lg:sticky lg:top-[80px]">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/[0.07]">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-500" /> Sessions
                </h3>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setFilterByUserOnly(!filterByUserOnly)}
                    className={`px-2.5 py-1 rounded-full text-[10px] font-semibold border transition cursor-pointer ${
                      filterByUserOnly
                        ? 'bg-indigo-50 dark:bg-indigo-500/15 border-indigo-300 dark:border-indigo-500/40 text-indigo-700 dark:text-indigo-300'
                        : 'glass-pill text-slate-500 dark:text-slate-400'
                    }`}
                  >
                    {filterByUserOnly ? 'Mine' : 'All'}
                  </button>
                  <button onClick={loadSessions} className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white transition cursor-pointer">
                    <RefreshCw className={`w-3.5 h-3.5 ${isLoadingSessions ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              {sessions.length > 0 ? (
                <div className="space-y-1.5 max-h-[520px] overflow-y-auto pr-0.5">
                  {sessions.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => { setSelectedSessionId(s.id); setRefreshCount((c) => c + 1); }}
                      className={`w-full text-left p-3 rounded-2xl border text-xs transition cursor-pointer ${
                        selectedSessionId === s.id
                          ? 'bg-gradient-to-r from-indigo-500/10 to-sky-500/10 dark:from-indigo-500/15 dark:to-sky-500/15 border-indigo-400/50 dark:border-indigo-500/40 text-slate-900 dark:text-white shadow-sm'
                          : 'bg-white/50 dark:bg-white/[0.02] border-slate-200 dark:border-white/[0.05] text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-white/[0.12]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-slate-900 dark:text-white truncate pr-2">{s.device_id}</span>
                        <span className="uppercase text-[9px] px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.05] text-slate-500 dark:text-slate-400 font-mono shrink-0">
                          {s.status}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                        {new Date(s.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-8">No sessions found.</p>
              )}
            </div>

            {/* Main Content */}
            <div className="space-y-5">
              <MomViewer
                mom={mom}
                sessionId={selectedSessionId}
                onGenerateMOM={handleGenerateMom}
                onSessionDeleted={() => { setSelectedSessionId(null); loadSessions(); }}
                isGenerating={isGeneratingMom}
              />
              <TranscriptViewer segments={segments} isLoading={isLoadingDetails} />
            </div>
          </div>
        )}

        {/* ─── TAB: AI Agent ─── */}
        {activeTab === 'agent' && (
          <div className="animate-fade-in-up">
            <AgentChat />
          </div>
        )}

        {/* ─── TAB: Search ─── */}
        {activeTab === 'search' && (
          <div className="animate-fade-in-up">
            <SearchExplorer
              onSelectSession={(sessionId) => {
                setSelectedSessionId(sessionId);
                setActiveTab('mom');
              }}
            />
          </div>
        )}

        {/* ─── TAB: Timeline ─── */}
        {activeTab === 'timeline' && (
          <div className="animate-fade-in-up">
            <Timeline
              sessions={sessions}
              selectedSessionId={selectedSessionId}
              onSelectSession={(id) => { setSelectedSessionId(id); setActiveTab('mom'); }}
            />
          </div>
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
