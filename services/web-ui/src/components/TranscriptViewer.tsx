import React from 'react';
import { Clock, MessageCircle, Mic } from 'lucide-react';
import { TranscriptSegment } from '../api/client';

interface Props {
  segments: TranscriptSegment[];
  isLoading?: boolean;
}

const SPEAKER_CONFIGS = [
  { gradient: 'from-sky-500 to-indigo-600', bg: 'bg-sky-50 dark:bg-sky-500/10', border: 'border-sky-200 dark:border-sky-500/20' },
  { gradient: 'from-emerald-400 to-teal-600', bg: 'bg-emerald-50 dark:bg-emerald-500/10', border: 'border-emerald-200 dark:border-emerald-500/20' },
  { gradient: 'from-purple-500 to-pink-600', bg: 'bg-purple-50 dark:bg-purple-500/10', border: 'border-purple-200 dark:border-purple-500/20' },
  { gradient: 'from-amber-400 to-orange-600', bg: 'bg-amber-50 dark:bg-amber-500/10', border: 'border-amber-200 dark:border-amber-500/20' },
];

const SPEAKER_KEY_TO_IDX: Record<string, number> = {
  speaker_0: 0,
  speaker_1: 1,
  speaker_2: 2,
  speaker_3: 3,
};

export const TranscriptViewer: React.FC<Props> = ({ segments, isLoading }) => {
  if (isLoading) {
    return (
      <div className="glass-card rounded-3xl p-8">
        <div className="flex items-center gap-2 mb-6">
          <div className="shimmer h-5 w-5 rounded-lg" />
          <div className="shimmer h-5 w-48 rounded-lg" />
        </div>
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="p-4 rounded-2xl border border-slate-100 dark:border-white/[0.05] space-y-2">
              <div className="flex items-center gap-2">
                <div className="shimmer w-7 h-7 rounded-xl" />
                <div className="shimmer h-4 w-24 rounded" />
                <div className="shimmer h-3 w-16 rounded ml-auto" />
              </div>
              <div className="shimmer h-4 w-full rounded pl-9" />
              <div className={`shimmer h-4 rounded pl-9 ${i % 2 === 0 ? 'w-3/4' : 'w-5/6'}`} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (segments.length === 0) {
    return (
      <div className="glass-card rounded-3xl p-12 text-center">
        <div className="w-14 h-14 rounded-3xl bg-slate-100 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08] flex items-center justify-center mx-auto mb-4">
          <Mic className="w-7 h-7 text-slate-400 dark:text-slate-500" />
        </div>
        <h4 className="text-base font-bold text-slate-800 dark:text-slate-200">No Transcript Yet</h4>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 max-w-sm mx-auto">
          Record a conversation to generate speaker-attributed transcript turns with timestamps.
        </p>
      </div>
    );
  }

  // Track unique speakers for consistent color assignment
  const speakerColorMap: Record<string, number> = {};
  let speakerCount = 0;
  const getSpeakerIdx = (key: string) => {
    if (SPEAKER_KEY_TO_IDX[key] !== undefined) return SPEAKER_KEY_TO_IDX[key];
    if (speakerColorMap[key] === undefined) {
      speakerColorMap[key] = speakerCount % SPEAKER_CONFIGS.length;
      speakerCount++;
    }
    return speakerColorMap[key];
  };

  return (
    <div className="glass-card rounded-3xl p-6 md:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-base md:text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
            Conversation Transcript
          </h3>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
            Speaker-attributed turns with timestamps
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono bg-slate-100 dark:bg-white/[0.05] text-slate-600 dark:text-slate-300 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-white/[0.07]">
            {segments.length} turns
          </span>
        </div>
      </div>

      {/* Segments */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
        {segments.map((segment, idx) => {
          const speakerKey = segment.speaker_label || 'speaker_0';
          const colorIdx = getSpeakerIdx(speakerKey);
          const cfg = SPEAKER_CONFIGS[colorIdx % SPEAKER_CONFIGS.length];
          const speakerName = segment.speaker_name || speakerKey.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

          return (
            <div
              key={segment.id || segment.segment_id || idx}
              className="group p-4 rounded-2xl bg-white/70 dark:bg-white/[0.025] border border-slate-200 dark:border-white/[0.07] hover:border-slate-300 dark:hover:border-white/[0.13] transition-all shadow-sm animate-fade-in-up"
              style={{ animationDelay: `${idx * 0.03}s` }}
            >
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center gap-2.5">
                  <div className={`w-6 h-6 rounded-lg bg-gradient-to-tr ${cfg.gradient} flex items-center justify-center text-white text-[10px] font-bold shadow-sm shrink-0`}>
                    {speakerName.charAt(0)}
                  </div>
                  <span className="text-xs font-semibold text-slate-900 dark:text-white">{speakerName}</span>
                  {segment.confidence !== undefined && (
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full border font-mono ${cfg.bg} ${cfg.border} text-slate-600 dark:text-slate-400`}>
                      {(segment.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                  <Clock className="w-3 h-3" />
                  <span>{segment.start_time.toFixed(1)}s – {segment.end_time.toFixed(1)}s</span>
                </div>
              </div>
              <p className="text-xs md:text-sm text-slate-700 dark:text-slate-200 leading-relaxed pl-[34px]">
                {segment.text}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
