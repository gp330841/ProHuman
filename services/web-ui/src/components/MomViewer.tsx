import { FileText, CheckSquare, Target, Calendar, UserCheck } from 'lucide-react';
import { MOMData } from '../api/client';

interface Props {
  mom: MOMData | null;
  onGenerateMOM?: () => void;
  isGenerating?: boolean;
}

const PRIORITY_BADGES: Record<string, string> = {
  critical: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
  high: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  medium: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
  low: 'bg-slate-700/50 text-slate-400 border-slate-600',
};

export const MomViewer: React.FC<Props> = ({ mom, onGenerateMOM, isGenerating }) => {
  if (!mom) {
    return (
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-8 text-center backdrop-blur shadow-xl">
        <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
        <h3 className="text-lg font-bold text-white">No Meeting Intelligence Generated</h3>
        <p className="text-sm text-slate-400 max-w-md mx-auto mt-1 mb-6">
          Trigger the pluggable Feature Provider pipeline (Summary, MOM, Action Items, Sentiment, Follow-ups) via LiteLLM & Instructor.
        </p>
        <button
          onClick={onGenerateMOM}
          disabled={isGenerating}
          className="px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 text-white font-medium rounded-lg text-sm transition shadow-lg shadow-sky-900/20"
        >
          {isGenerating ? 'Synthesizing with LLM...' : 'Generate Minutes & Action Items'}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Executive Summary Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl backdrop-blur">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-sky-400" />
            {mom.title || 'Executive Meeting Summary'}
          </h3>
          {onGenerateMOM && (
            <button
              onClick={onGenerateMOM}
              disabled={isGenerating}
              className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg border border-slate-700 transition"
            >
              {isGenerating ? 'Regenerating...' : 'Regenerate'}
            </button>
          )}
        </div>

        <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/60 p-4 rounded-lg border border-slate-800/80 mb-4">
          {mom.executive_summary}
        </p>

        {mom.attendees && mom.attendees.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <UserCheck className="w-4 h-4 text-emerald-400" />
            <span>Attendees:</span>
            <div className="flex flex-wrap gap-1.5">
              {mom.attendees.map((attendee, idx) => (
                <span key={idx} className="bg-slate-800 text-slate-200 px-2 py-0.5 rounded border border-slate-700">
                  {attendee}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Action Items List */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl backdrop-blur">
          <h4 className="text-base font-bold text-white flex items-center gap-2 mb-4">
            <CheckSquare className="w-5 h-5 text-emerald-400" />
            Extracted Action Items
            <span className="text-xs font-mono bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30">
              {mom.action_items?.length || 0}
            </span>
          </h4>

          {mom.action_items && mom.action_items.length > 0 ? (
            <div className="space-y-3">
              {mom.action_items.map((item, idx) => {
                const priorityBadge = PRIORITY_BADGES[item.priority || 'medium'] || PRIORITY_BADGES.medium;
                return (
                  <div key={idx} className="bg-slate-950/60 border border-slate-800/80 p-3.5 rounded-lg">
                    <p className="text-sm text-slate-200 font-medium mb-2">{item.description}</p>
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span className="flex items-center gap-1.5">
                        <UserCheck className="w-3.5 h-3.5 text-slate-500" />
                        <span className="text-slate-300">{item.assignee || 'Unassigned'}</span>
                      </span>
                      <div className="flex items-center gap-2">
                        {item.deadline && (
                          <span className="flex items-center gap-1 text-[11px] text-slate-400 font-mono">
                            <Calendar className="w-3 h-3 text-slate-500" />
                            {item.deadline}
                          </span>
                        )}
                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${priorityBadge}`}>
                          {item.priority || 'medium'}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No action items detected in this conversation.</p>
          )}
        </div>

        {/* Key Decisions List */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl backdrop-blur">
          <h4 className="text-base font-bold text-white flex items-center gap-2 mb-4">
            <Target className="w-5 h-5 text-purple-400" />
            Key Decisions & Approvals
            <span className="text-xs font-mono bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-full border border-purple-500/30">
              {mom.decisions?.length || 0}
            </span>
          </h4>

          {mom.decisions && mom.decisions.length > 0 ? (
            <div className="space-y-3">
              {mom.decisions.map((dec, idx) => (
                <div key={idx} className="bg-slate-950/60 border border-slate-800/80 p-3.5 rounded-lg flex items-start gap-3">
                  <span className="w-2 h-2 rounded-full bg-purple-400 mt-1.5 shrink-0" />
                  <div>
                    <p className="text-sm text-slate-200">{dec.description}</p>
                    {dec.made_by && (
                      <p className="text-[11px] text-slate-400 mt-1">
                        Decided by: <span className="text-purple-300 font-medium">{dec.made_by}</span>
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No formal decisions recorded.</p>
          )}
        </div>
      </div>
    </div>
  );
};
