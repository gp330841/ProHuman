import React, { useState, useEffect } from 'react';
import {
  Database,
  RefreshCw,
  Server,
  Sparkles,
  Bot,
  Sliders,
  Zap,
  Trash2,
} from 'lucide-react';
import { fetchSystemStatus, flushTestData, queryAgent, SystemStatus } from '../api/client';
import { useUser } from '../context/UserContext';

interface Props {
  onDataFlushed?: () => void;
}

export const SystemController: React.FC<Props> = ({ onDataFlushed }) => {
  const { activeUser } = useUser();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [testAgentLoading, setTestAgentLoading] = useState(false);
  const [testAgentResult, setTestAgentResult] = useState<string | null>(null);
  const [hardwareMode, setHardwareMode] = useState<'neo1' | 'desk' | 'mobile'>('neo1');
  const [autoMomEnabled, setAutoMomEnabled] = useState(true);
  const [isFlushing, setIsFlushing] = useState(false);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const data = await fetchSystemStatus();
      setStatus(data);
    } catch {
      // Offline fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleTestAgent = async () => {
    setTestAgentLoading(true);
    setTestAgentResult(null);
    try {
      const start = Date.now();
      const res = await queryAgent('Quick system health check and capabilities summary', activeUser.id);
      const elapsed = Date.now() - start;
      setTestAgentResult(`Agent OK (${elapsed}ms): ${res.response.slice(0, 120)}...`);
    } catch (err: any) {
      setTestAgentResult(`Agent Test Failed: ${err.message}`);
    } finally {
      setTestAgentLoading(false);
    }
  };

  const handleFlushData = async () => {
    if (!window.confirm('Are you sure you want to clear all recorded demo sessions and transcripts from PostgreSQL? This action cannot be undone.')) {
      return;
    }
    setIsFlushing(true);
    try {
      await flushTestData();
      await loadStatus();
      onDataFlushed?.();
    } catch (err: any) {
      alert(`Flush failed: ${err.message}`);
    } finally {
      setIsFlushing(false);
    }
  };

  return (
    <section className="glass-panel overflow-hidden border border-slate-800 rounded-2xl shadow-xl">
      {/* Header with Live Status & Controls */}
      <div className="px-5 py-4 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-4 bg-slate-950/60">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 text-sky-400 flex items-center justify-center border border-sky-500/20">
            <Sliders className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-white tracking-tight">System Controller & Telemetry</h2>
              <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-mono flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live Control Hub
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Manage gadget hardware profiles, real-time pipeline, and microservice fleet</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadStatus}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700/80 rounded-lg text-xs font-medium transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleTestAgent}
            disabled={testAgentLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 border border-sky-500/30 rounded-lg text-xs font-medium transition"
          >
            <Bot className="w-3.5 h-3.5" />
            {testAgentLoading ? 'Testing Agent...' : 'Test ReAct Agent'}
          </button>
        </div>
      </div>

      {/* Live Service Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-5 bg-slate-950/40">
        {/* Gateway */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-sky-400 flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5" /> Gateway
            </span>
            <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/20 font-mono">
              Port :8000
            </span>
          </div>
          <div className="mt-2.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
              <span className={`w-2 h-2 rounded-full ${status?.gateway.status === 'ONLINE' ? 'bg-emerald-400' : loading ? 'bg-amber-400' : 'bg-rose-400'}`} />
              {status?.gateway.status || (loading ? 'CHECKING...' : 'OFFLINE')}
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">WebSocket + Audio Ingestion</p>
          </div>
        </div>

        {/* PostgreSQL Database */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5" /> Postgres
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              {status?.postgres.latency_ms !== undefined ? `${status.postgres.latency_ms}ms` : 'pgvector'}
            </span>
          </div>
          <div className="mt-2.5">
            <div className="flex items-center justify-between text-xs font-semibold text-white">
              <span className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${status?.postgres ? 'bg-emerald-400' : loading ? 'bg-amber-400' : 'bg-rose-400'}`} />
                {status?.postgres.sessions_count ?? 0} Sessions
              </span>
              <span className="text-[11px] text-sky-400 font-mono">
                {status?.postgres.transcripts_count ?? 0} Turns
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">Vector + Hybrid Storage</p>
          </div>
        </div>

        {/* Redis Queue */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5" /> Redis Broker
            </span>
            <span className="text-[10px] font-mono text-slate-400">Port :6379</span>
          </div>
          <div className="mt-2.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
              <span className={`w-2 h-2 rounded-full ${status?.redis.status === 'CONNECTED' ? 'bg-emerald-400' : loading ? 'bg-amber-400' : 'bg-rose-400'}`} />
              {status?.redis.status || (loading ? 'CHECKING...' : 'DISCONNECTED')}
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">Task Queue & PubSub</p>
          </div>
        </div>

        {/* ReAct Agent Service */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-violet-400 flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5" /> ReAct Agent
            </span>
            <span className="text-[10px] bg-violet-500/10 text-violet-300 px-1.5 py-0.5 rounded border border-violet-500/20 font-mono">
              Port :8001
            </span>
          </div>
          <div className="mt-2.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
              <span className={`w-2 h-2 rounded-full ${status?.agent.status === 'ACTIVE' ? 'bg-emerald-400' : loading ? 'bg-amber-400' : 'bg-rose-400'}`} />
              {status?.agent.status || (loading ? 'CHECKING...' : 'OFFLINE')}
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">Autonomous Reasoner</p>
          </div>
        </div>
      </div>

      {/* Agent test result toast */}
      {testAgentResult && (
        <div className="mx-5 mb-4 p-3 rounded-xl bg-violet-950/40 border border-violet-500/30 text-xs text-violet-200 flex items-start gap-2">
          <Sparkles className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold text-white">ReAct Agent Telemetry Response:</p>
            <p className="text-slate-300 mt-0.5 leading-relaxed">{testAgentResult}</p>
          </div>
        </div>
      )}

      {/* Interactive Controls & Settings Bar */}
      <div className="p-5 border-t border-slate-800/80 bg-slate-950/80 flex flex-wrap items-center justify-between gap-4">
        {/* Hardware Preset Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Gadget Mode:</span>
          <div className="inline-flex rounded-lg bg-slate-900 p-1 border border-slate-800">
            <button
              onClick={() => setHardwareMode('neo1')}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition ${
                hardwareMode === 'neo1'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Neo-1 Lapel Badge
            </button>
            <button
              onClick={() => setHardwareMode('desk')}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition ${
                hardwareMode === 'desk'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Studio Desk Mic
            </button>
            <button
              onClick={() => setHardwareMode('mobile')}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition ${
                hardwareMode === 'mobile'
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Mobile Companion
            </button>
          </div>
        </div>

        {/* Feature Toggles */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Language:</span>
            <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 rounded font-mono text-[11px]">
              Always Hinglish
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Auto-MOM:</span>
            <button
              onClick={() => setAutoMomEnabled(!autoMomEnabled)}
              className={`px-2 py-0.5 rounded text-[11px] font-semibold border transition ${
                autoMomEnabled
                  ? 'bg-sky-500/20 border-sky-500/40 text-sky-300'
                  : 'bg-slate-800 border-slate-700 text-slate-400'
              }`}
            >
              {autoMomEnabled ? 'ON' : 'OFF'}
            </button>
          </div>

          {/* Flush Demo Data Button */}
          <button
            onClick={handleFlushData}
            disabled={isFlushing}
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] text-rose-400 hover:bg-rose-500/10 border border-rose-500/30 rounded-lg transition"
            title="Clean demo sessions from database"
          >
            <Trash2 className="w-3 h-3" />
            {isFlushing ? 'Clearing...' : 'Clear Test Data'}
          </button>
        </div>
      </div>
    </section>
  );
};
