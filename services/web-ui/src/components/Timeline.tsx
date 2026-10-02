import React from 'react';
import { Clock, Calendar } from 'lucide-react';
import { Session } from '../api/client';

interface TimelineProps {
  sessions: Session[];
  selectedSessionId: string | null;
  onSelectSession: (id: string) => void;
}

export const Timeline: React.FC<TimelineProps> = ({ sessions, selectedSessionId, onSelectSession }) => {
  const formatDuration = (secs?: number) => {
    if (secs === undefined || secs === null || secs === 0) return 'Live / In progress';
    const m = Math.floor(secs / 60);
    const s = Math.round(secs % 60);
    return `${m}m ${s}s`;
  };

  const groupSessionsByDate = () => {
    const groups: { [key: string]: Session[] } = {};
    sessions.forEach(s => {
      const date = new Date(s.created_at);
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      
      let dateKey = date.toLocaleDateString();
      if (date.toDateString() === today.toDateString()) {
        dateKey = 'Today';
      } else if (date.toDateString() === yesterday.toDateString()) {
        dateKey = 'Yesterday';
      }
      
      if (!groups[dateKey]) groups[dateKey] = [];
      groups[dateKey].push(s);
    });
    // Sort groups by date descending? Assuming sessions are already sorted or we just use order of appearance
    return groups;
  };

  const groups = groupSessionsByDate();

  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400 p-8 text-center bg-slate-900">
        <Calendar className="w-16 h-16 mb-4 text-slate-500" />
        <p className="text-lg text-slate-100">No conversations recorded yet.</p>
        <p>Start recording to build your memory timeline.</p>
      </div>
    );
  }

  return (
    <div className="p-6 overflow-y-auto h-full bg-slate-900 text-slate-100">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-2xl font-bold mb-8 flex items-center">
          <Calendar className="mr-3" /> Memory Timeline
        </h2>
        
        <div className="space-y-8 relative">
          {/* Vertical connecting line */}
          <div className="absolute left-[27px] top-4 bottom-4 w-0.5 bg-slate-700"></div>
          
          {Object.entries(groups).map(([date, dateSessions]) => (
            <div key={date} className="relative z-10">
              <div className="sticky top-0 bg-slate-900/90 py-2 font-semibold text-slate-400 backdrop-blur-sm mb-4 pl-16">
                {date}
              </div>
              
              <div className="space-y-4">
                {dateSessions.map(session => {
                  const isSelected = session.id === selectedSessionId;
                  const timeStr = new Date(session.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                  
                  return (
                    <div 
                      key={session.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelectSession(session.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onSelectSession(session.id);
                        }
                      }}
                      className={`flex items-start cursor-pointer rounded-lg p-4 transition-colors focus:outline-none focus:ring-1 focus:ring-sky-500 ${isSelected ? 'bg-slate-800 border-sky-500/50 border' : 'hover:bg-slate-800/50 border border-transparent'}`}
                    >
                      <div className="mr-6 mt-1 flex flex-col items-center">
                        <div className={`w-4 h-4 rounded-full border-4 border-slate-900 shadow-sm z-10 ${session.status === 'COMPLETED' ? 'bg-emerald-500' : session.status === 'RECORDING' ? 'bg-amber-500' : 'bg-rose-500'}`}></div>
                        <div className="text-xs text-slate-400 mt-2 font-medium w-12 text-center">{timeStr}</div>
                      </div>
                      
                      <div className="flex-1 bg-slate-800/80 p-4 rounded-xl border border-slate-700 shadow-sm">
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-medium text-slate-200">Device: {session.device_id}</span>
                          <span className="text-xs flex items-center text-slate-400 bg-slate-900 px-2 py-1 rounded-md">
                            <Clock className="w-3 h-3 mr-1" />
                            {formatDuration(session.duration_seconds)}
                          </span>
                        </div>
                        <div className="text-sm text-slate-400 flex items-center">
                          Status: <span className="ml-1 capitalize">{session.status.toLowerCase()}</span>
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
    </div>
  );
};
