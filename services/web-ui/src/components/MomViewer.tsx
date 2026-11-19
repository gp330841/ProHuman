import React, { useState } from 'react';
import { 
  FileText, 
  CheckSquare, 
  Target, 
  Download, 
  Trash2, 
  Check, 
  Sparkles,
  RefreshCw,
  Flame,
  Zap,
  Leaf
} from 'lucide-react';
import { EvidencePlayer, evidenceTime } from './EvidencePlayer';
import { MOMData, exportMom, deleteSession, reviewActionItem, type TranscriptEvidence } from '../api/client';

interface Props {
  mom: MOMData | null;
  sessionId?: string | null;
  onGenerateMOM?: () => void;
  onSessionDeleted?: () => void;
  isGenerating?: boolean;
  version?: number;
  onReviewed?: (mom: MOMData, version: number) => void;
}

export const MomViewer: React.FC<Props> = ({ 
  mom, 
  sessionId, 
  onGenerateMOM, 
  onSessionDeleted, 
  isGenerating,
  version,
  onReviewed,
}) => {
  const [evidence, setEvidence] = useState<TranscriptEvidence | null>(null);
  const [edit, setEdit] = useState<{ index: number; version: number; description: string; assignee: string; deadline: string } | null>(null);
  const [reviewError, setReviewError] = useState('');
  const [savingReview, setSavingReview] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  const [completedItems, setCompletedItems] = useState<Record<number, boolean>>({});

  const toggleItem = (idx: number) => {
    setCompletedItems((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  async function saveReview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionId || !edit) return;
    setSavingReview(true);
    setReviewError('');
    try {
      const result = await reviewActionItem(sessionId, edit.index, {
        version: edit.version,
        description: edit.description.trim(),
        assignee: edit.assignee.trim() || null,
        deadline: edit.deadline || null,
      });
      onReviewed?.(result.mom, result.version);
      setEdit(null);
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : 'Could not save action item');
    } finally {
      setSavingReview(false);
    }
  }

  const handleExport = async (format: 'markdown' | 'json') => {
    if (!sessionId) return;
    try {
      setIsExporting(true);
      const content = await exportMom(sessionId, format);
      const mime = format === 'markdown' ? 'text/markdown' : 'application/json';
      const ext = format === 'markdown' ? 'md' : 'json';
      const blob = new Blob([content], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `meeting_mom_${sessionId.slice(0, 8)}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      setDownloadSuccess(true);
      setTimeout(() => setDownloadSuccess(false), 2500);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleDelete = async () => {
    if (!sessionId) return;
    if (!window.confirm('Are you sure you want to permanently delete this meeting session?')) {
      return;
    }
    try {
      setIsDeleting(true);
      await deleteSession(sessionId);
      onSessionDeleted?.();
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  const renderPriorityBadge = (priority?: string) => {
    const p = (priority || 'medium').toLowerCase();
    if (p === 'critical') {
      return (
        <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-rose-50 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30">
          <Flame className="w-3 h-3 text-rose-500 dark:text-rose-400" /> Critical
        </span>
      );
    }
    if (p === 'high') {
      return (
        <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30">
          <Zap className="w-3 h-3 text-amber-500 dark:text-amber-400" /> High
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-sky-50 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-500/30">
        <Leaf className="w-3 h-3 text-sky-500 dark:text-sky-400" /> Medium
      </span>
    );
  };

  if (!mom) {
    return (
      <div className="glass-card rounded-3xl p-10 md:p-16 text-center relative overflow-hidden animate-fade-in">
        <div className="absolute -top-16 left-1/2 -translate-x-1/2 w-64 h-64 rounded-full bg-sky-400/10 dark:bg-sky-500/10 blur-3xl pointer-events-none" />
        <div className="relative z-10">
          <div className="w-16 h-16 rounded-3xl bg-gradient-to-br from-sky-50 to-indigo-50 dark:from-sky-500/10 dark:to-indigo-500/10 border border-sky-200 dark:border-sky-500/25 flex items-center justify-center mx-auto mb-5 shadow-sm">
            <FileText className="w-8 h-8 text-sky-500 dark:text-sky-400" />
          </div>
          <h3 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">No Meeting Notes Yet</h3>
          <p className="text-xs md:text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto mt-2.5 mb-7 leading-relaxed">
            Select a session and generate smart AI notes — executive summary, key decisions, and action items in Hinglish.
          </p>
          <button
            onClick={onGenerateMOM}
            disabled={isGenerating || !sessionId}
            className="px-7 py-3 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 disabled:opacity-40 text-white font-semibold rounded-2xl text-sm transition shadow-lg shadow-sky-500/25 flex items-center gap-2 mx-auto cursor-pointer"
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Generating AI Notes...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Generate Minutes & Action Items</span>
              </>
            )}
          </button>
          {!sessionId && (
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-3">Select a session from the sidebar first</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Executive Summary Card */}
      <div className="glass-card rounded-3xl p-6 md:p-8 relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <span className="text-[10px] uppercase font-mono px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30 inline-flex items-center gap-1.5 mb-2">
              ✦ AI Intelligence
            </span>
            <h3 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {mom.title || 'Executive Meeting Summary'}
            </h3>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            {sessionId && (
              <>
                <button
                  onClick={() => handleExport('markdown')}
                  disabled={isExporting}
                  className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white glass-pill px-3 py-1.5 rounded-xl transition cursor-pointer"
                  title="Download Markdown summary"
                >
                  {downloadSuccess ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Download className="w-3.5 h-3.5 text-sky-500 dark:text-sky-400" />}
                  <span>{downloadSuccess ? 'Downloaded' : 'Export .MD'}</span>
                </button>

                <button
                  onClick={() => handleExport('json')}
                  disabled={isExporting}
                  className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white glass-pill px-3 py-1.5 rounded-xl transition cursor-pointer"
                  title="Download JSON structure"
                >
                  <Download className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
                  <span>JSON</span>
                </button>

                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400 hover:text-rose-700 dark:hover:text-rose-300 bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 dark:hover:bg-rose-500/20 border border-rose-200 dark:border-rose-500/30 px-3 py-1.5 rounded-xl transition cursor-pointer"
                  title="Delete session"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Delete</span>
                </button>
              </>
            )}

            {onGenerateMOM && (
              <button
                onClick={onGenerateMOM}
                disabled={isGenerating}
                className="flex items-center gap-1.5 text-xs bg-sky-50 dark:bg-sky-500/15 hover:bg-sky-100 dark:hover:bg-sky-500/25 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-500/30 px-3 py-1.5 rounded-xl transition cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
                <span>{isGenerating ? 'Analyzing...' : 'Regenerate'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Executive Summary Callout */}
        <div className="p-5 rounded-2xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] backdrop-blur-md mb-5">
          <p className="text-xs font-semibold text-sky-600 dark:text-sky-400 uppercase tracking-wider mb-2">Executive Summary:</p>
          <p className="text-xs md:text-sm text-slate-800 dark:text-slate-200 leading-relaxed">
            {mom.executive_summary}
          </p>
        </div>

        {/* Attendees */}
        {mom.attendees && mom.attendees.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
            <span className="font-semibold text-slate-700 dark:text-slate-300">Attendees:</span>
            <div className="flex flex-wrap gap-1.5">
              {mom.attendees.map((attendee, idx) => (
                <span key={idx} className="glass-pill text-slate-800 dark:text-slate-200 px-2.5 py-0.5 rounded-lg text-xs">
                  {attendee}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {evidence && <EvidencePlayer evidence={evidence} onClose={() => setEvidence(null)} />}
      {/* Action Items & Decisions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Action Items */}
        <div className="glass-card rounded-3xl p-6 md:p-7 relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm md:text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <CheckSquare className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
              Action Items
            </h4>
            <span className="text-xs font-mono bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 px-2.5 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-500/30">
              {mom.action_items?.length || 0} tasks
            </span>
          </div>

          {edit && (
            <form onSubmit={saveReview} className="mb-4 space-y-2 rounded-xl border border-slate-300 p-3 text-sm dark:border-slate-700">
              <label className="block">Action item
                <input className="block w-full rounded border border-slate-300 bg-transparent p-1 dark:border-slate-700" required
                  value={edit.description} onChange={(event) => setEdit({ ...edit, description: event.target.value })} />
              </label>
              <label className="block">Assignee
                <input className="block w-full rounded border border-slate-300 bg-transparent p-1 dark:border-slate-700"
                  value={edit.assignee} onChange={(event) => setEdit({ ...edit, assignee: event.target.value })} />
              </label>
              <label className="block">Due date
                <input type="date" className="block rounded border border-slate-300 bg-transparent p-1 dark:border-slate-700"
                  value={edit.deadline} onChange={(event) => setEdit({ ...edit, deadline: event.target.value })} />
              </label>
              {reviewError && <p role="alert" className="text-rose-600">{reviewError}</p>}
              <div className="flex gap-3">
                <button type="submit" disabled={savingReview} className="rounded bg-sky-700 px-3 py-1 text-white">Save changes</button>
                <button type="button" onClick={() => setEdit(null)} disabled={savingReview}>Cancel</button>
              </div>
            </form>
          )}
          {mom.action_items && mom.action_items.length > 0 ? (
            <div className="space-y-3">
              {mom.action_items.map((item, idx) => {
                const isDone = completedItems[idx];
                return (
                  <div 
                    key={idx} 
                    onClick={() => toggleItem(idx)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                      isDone 
                        ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-500/30 opacity-70' 
                        : 'bg-white dark:bg-white/[0.03] border-slate-200 dark:border-white/[0.08] hover:border-slate-300 dark:hover:border-white/[0.15]'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 w-4 h-4 rounded-md border flex items-center justify-center shrink-0 transition ${
                        isDone ? 'bg-emerald-500 border-emerald-400 text-white' : 'border-slate-400 dark:border-slate-500'
                      }`}>
                        {isDone && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-xs md:text-sm font-medium ${isDone ? 'line-through text-slate-400' : 'text-slate-800 dark:text-slate-100'}`}>
                          {item.description}
                        </p>
                        <div className="flex items-center justify-between gap-2 mt-2 text-xs text-slate-500">
                          <span className="text-slate-700 dark:text-slate-300 font-medium">
                            👤 {item.assignee || 'Unassigned'}
                          </span>
                          {renderPriorityBadge(item.priority)}
                          {version !== undefined && (
                            <button className="text-sky-700 dark:text-sky-300" onClick={(event) => {
                              event.stopPropagation();
                              setReviewError('');
                              setEdit({ index: idx, version, description: item.description,
                                assignee: item.assignee ?? '', deadline: item.deadline ?? '' });
                            }}>Edit</button>
                          )}
                          {item.evidence && (
                            <button className="text-sky-700 dark:text-sky-300" onClick={(event) => {
                              event.stopPropagation();
                              setEvidence(item.evidence ?? null);
                            }}>Play at {evidenceTime(item.evidence.start_time)}</button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic py-4">No action items detected in this conversation.</p>
          )}
        </div>

        {/* Decisions List */}
        <div className="glass-card rounded-3xl p-6 md:p-7 relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm md:text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-500 dark:text-purple-400" />
              Key Decisions & Agreements
            </h4>
            <span className="text-xs font-mono bg-purple-50 dark:bg-purple-500/15 text-purple-700 dark:text-purple-400 px-2.5 py-0.5 rounded-full border border-purple-200 dark:border-purple-500/30">
              {mom.decisions?.length || 0} decisions
            </span>
          </div>

          {mom.decisions && mom.decisions.length > 0 ? (
            <div className="space-y-3">
              {mom.decisions.map((dec, idx) => (
                <div key={idx} className="p-4 rounded-2xl bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] flex items-start gap-3">
                  <div className="w-6 h-6 rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30 flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
                    ✓
                  </div>
                  <div>
                    <p className="text-xs md:text-sm text-slate-800 dark:text-slate-200 leading-relaxed">{dec.description}</p>
                    {dec.evidence && (
                      <button className="mt-1 text-xs text-sky-700 dark:text-sky-300"
                        onClick={() => setEvidence(dec.evidence ?? null)}>
                        Play at {evidenceTime(dec.evidence.start_time)}
                      </button>
                    )}
                    {dec.made_by && (
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1.5">
                        Agreed by: <span className="text-purple-600 dark:text-purple-300 font-medium">{dec.made_by}</span>
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic py-4">No explicit decisions recorded yet.</p>
          )}
        </div>
      </div>
    </div>
  );
};
