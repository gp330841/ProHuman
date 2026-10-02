import React from 'react';
import { Clock, Sparkles, MessageCircle } from 'lucide-react';
import { TranscriptSegment } from '../api/client';

interface Props {
  segments: TranscriptSegment[];
  isLoading?: boolean;
}

const SPEAKER_GRADIENTS: Record<string, string> = {
  speaker_0: 'from-sky-500 to-indigo-600',
  speaker_1: 'from-emerald-400 to-teal-600',
  speaker_2: 'from-purple-500 to-pink-600',
  speaker_3: 'from-amber-400 to-orange-600',
};

export const TranscriptViewer: React.FC<Props> = ({ segments, isLoading }) => {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 glass-card rounded-3xl">
        <Sparkles className="w-8 h-8 text-sky-500 dark:text-sky-400 animate-spin mb-3" />
        <p className="text-sm text-slate-600 dark:text-slate-300">Loading conversation transcript turns...</p>
      </div>
    );
  }

  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 glass-card rounded-3xl text-center">
        <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08] flex items-center justify-center text-slate-400 mb-3">
          <MessageCircle className="w-7 h-7 text-slate-400" />
        </div>
        <h4 className="text-base font-semibold text-slate-800 dark:text-slate-200">No Transcript Segments Yet</h4>
        <p className="text-xs text-slate-500 max-w-sm mt-1">
          Record speech in the Audio tab to generate real-time speaker turns and conversation history.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-3xl p-6 md:p-8 relative overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg md:text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
            Diarized Conversation Stream
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Real-time speaker turns attributed with timestamps and confidence
          </p>
        </div>
        <span className="text-xs font-mono bg-slate-100 dark:bg-white/[0.05] text-slate-600 dark:text-slate-300 px-3 py-1 rounded-full border border-slate-200 dark:border-white/[0.08]">
          {segments.length} turns
        </span>
      </div>

      <div className="space-y-3.5 max-h-[550px] overflow-y-auto pr-1">
        {segments.map((segment, idx) => {
          const speakerKey = segment.speaker_label || 'speaker_0';
          const gradient = SPEAKER_GRADIENTS[speakerKey] || 'from-sky-500 to-indigo-600';
          const speakerDisplayName = segment.speaker_name || segment.speaker_label.replace('_', ' ').toUpperCase();

          return (
            <div
              key={segment.id || segment.segment_id || idx}
              className="p-4 rounded-2xl bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] hover:border-slate-300 dark:hover:border-white/[0.15] transition shadow-sm"
            >
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center gap-2.5">
                  <div className={`w-6 h-6 rounded-lg bg-gradient-to-tr ${gradient} flex items-center justify-center text-white text-[10px] font-bold shadow-sm`}>
                    {speakerDisplayName.charAt(0)}
                  </div>
                  <span className="text-xs font-semibold text-slate-900 dark:text-white">
                    {speakerDisplayName}
                  </span>
                  {segment.confidence !== undefined && (
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                      {(segment.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                  <Clock className="w-3 h-3 text-slate-400" />
                  <span>{segment.start_time.toFixed(1)}s - {segment.end_time.toFixed(1)}s</span>
                </div>
              </div>
              <p className="text-xs md:text-sm leading-relaxed text-slate-700 dark:text-slate-200 pl-8">{segment.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
