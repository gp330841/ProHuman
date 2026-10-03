import React from 'react';
import { Clock, Calendar, CheckCircle2, AlertCircle, Radio, Layers } from 'lucide-react';
import { Session } from '../api/client';

interface TimelineProps {
  sessions: Session[];
  selectedSessionId: string | null;
  onSelectSession: (id: string) => void;
}

export const Timeline: React.FC<TimelineProps> = ({ sessions, selectedSessionId, onSelectSession }) => {
  const formatDuration = (secs?: number) => {
    if (!secs) return null;
    const m = Math.floor(secs / 60);
    const s = Math.round(secs % 60);
    return `${m}m ${s}s`;
  };

  const groupSessionsByDate = () => {
    const groups: Record<string, Session[]> = {};
    sessions.forEach((s) => {
      const date = new Date(s.created_at);
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);

      let key = date.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
      if (date.toDateString() === today.toDateString()) key = 'Today';
      else if (date.toDateString() === yesterday.toDateString()) key = 'Yesterday';

      if (!groups[key]) groups[key] = [];
      groups[key].push(s);
    });
    return groups;
  };

  const statusConfig = {
    COMPLETED: {
      dot: 'bg-emerald-500 shadow-emerald-500/40',
      badge: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/25',
      icon: CheckCircle2,
    },
    RECORDING: {
      dot: 'bg-amber-500 shadow-amber-500/40 animate-pulse',
      badge: 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/25',
      icon: Radio,
    },
    FAILED: {
      dot: 'bg-rose-500 shadow-rose-500/40',
      badge: 'bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-500/25',
      icon: AlertCircle,
    },
    DEFAULT: {
      dot: 'bg-slate-400 dark:bg-slate-600',
      badge: 'bg-slate-100 dark:bg-white/[0.05] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-white/[0.08]',
      icon: Clock,
    },
  };

  if (sessions.length === 0) {
    return (
      <div className="glass-card rounded-3xl p-16 flex flex-col items-center justify-center text-center">
        <div className="w-16 h-16 rounded-3xl bg-slate-100 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08] flex items-center justify-center mx-auto mb-4">
          <Calendar className="w-8 h-8 text-slate-400 dark:text-slate-500" />
        </div>
        <h3 className="text-base font-bold text-slate-900 dark:text-white">No conversations yet</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5 max-w-xs">
          Start recording to build your personal memory timeline.
        </p>
      </div>
    );
  }

  const groups = groupSessionsByDate();

  return (
    <div className="glass-card rounded-3xl p-6 md:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h3 className="text-lg md:text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2.5">
            <Layers className="w-5 h-5 text-amber-500" />
            Memory Timeline
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {sessions.length} conversations recorded
          </p>
        </div>
        <div className="text-xs text-slate-400 dark:text-slate-500 font-mono bg-slate-100 dark:bg-white/[0.05] px-3 py-1.5 rounded-xl border border-slate-200 dark:border-white/[0.07]">
          {sessions.length} sessions
        </div>
      </div>

      {/* Timeline Body */}
      <div className="space-y-8 max-h-[70vh] overflow-y-auto pr-1">
        {Object.entries(groups).map(([date, dateSessions]) => (
          <div key={date} className="relative">
            {/* Date Header */}
            <div className="flex items-center gap-3 mb-4 sticky top-0 bg-white/80 dark:bg-[#060a12]/80 backdrop-blur-md py-1 z-10">
              <div className="w-2 h-2 rounded-full bg-gradient-to-br from-sky-500 to-indigo-500 shadow-sm shadow-sky-500/30" />
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">{date}</span>
              <div className="flex-1 h-px bg-slate-200 dark:bg-white/[0.06]" />
            </div>

            {/* Sessions */}
            <div className="relative pl-6 space-y-3">
              {/* Vertical connector */}
              <div className="timeline-line" />

              {dateSessions.map((session) => {
                const isSelected = session.id === selectedSessionId;
                const cfg = statusConfig[session.status as keyof typeof statusConfig] ?? statusConfig.DEFAULT;
                const StatusIcon = cfg.icon;
                const timeStr = new Date(session.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const duration = formatDuration(session.duration_seconds);

                return (
                  <div
                    key={session.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => onSelectSession(session.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectSession(session.id); }
                    }}
                    className={`relative flex items-start gap-4 p-4 rounded-2xl border cursor-pointer transition-all focus:outline-none focus:ring-2 focus:ring-sky-500/50 glass-card-hover ${
                      isSelected
                        ? 'bg-gradient-to-r from-sky-500/8 to-indigo-500/8 dark:from-sky-500/12 dark:to-indigo-500/12 border-sky-400/50 dark:border-sky-500/40 shadow-sm'
                        : 'bg-white/60 dark:bg-white/[0.02] border-slate-200 dark:border-white/[0.06] hover:border-slate-300 dark:hover:border-white/[0.12]'
                    }`}
                  >
                    {/* Status dot (aligned to timeline) */}
                    <div className="absolute -left-[22px] top-5 flex flex-col items-center">
                      <div className={`w-3 h-3 rounded-full border-2 border-white dark:border-[#060a12] shadow-sm z-10 ${cfg.dot}`} />
                    </div>

                    {/* Icon */}
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border ${cfg.badge}`}>
                      <StatusIcon className="w-4 h-4" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                            {session.device_id}
                          </p>
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            <span className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                              <Clock className="w-3 h-3 text-slate-400" />
                              {timeStr}
                            </span>
                            {duration && (
                              <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">· {duration}</span>
                            )}
                          </div>
                        </div>
                        <span className={`text-[9px] uppercase font-mono px-2 py-0.5 rounded-full border shrink-0 ${cfg.badge}`}>
                          {session.status}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};


