import React from 'react';
import { User, Clock, Sparkles } from 'lucide-react';
import { TranscriptSegment } from '../api/client';

interface Props {
  segments: TranscriptSegment[];
  isLoading?: boolean;
}

const SPEAKER_COLORS: Record<string, string> = {
  speaker_0: 'bg-sky-500/10 border-sky-500/30 text-sky-300',
  speaker_1: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
  speaker_2: 'bg-purple-500/10 border-purple-500/30 text-purple-300',
  speaker_3: 'bg-amber-500/10 border-amber-500/30 text-amber-300',
};

const SPEAKER_BADGES: Record<string, string> = {
  speaker_0: 'bg-sky-500/20 text-sky-400 border-sky-500/40',
  speaker_1: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  speaker_2: 'bg-purple-500/20 text-purple-400 border-purple-500/40',
  speaker_3: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
};

export const TranscriptViewer: React.FC<Props> = ({ segments, isLoading }) => {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-slate-900/60 border border-slate-800 rounded-xl">
        <Sparkles className="w-8 h-8 text-sky-400 animate-spin mb-3" />
        <p className="text-sm text-slate-400">Loading conversation transcript turns...</p>
      </div>
    );
  }

  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-slate-900/40 border border-slate-800 rounded-xl text-center">
        <User className="w-10 h-10 text-slate-600 mb-3" />
        <h4 className="text-base font-semibold text-slate-300">No Transcript Segments Yet</h4>
        <p className="text-xs text-slate-500 max-w-sm mt-1">
          Record or upload audio above to trigger Deepgram Nova-2 diarization and populate conversation turns.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl backdrop-blur">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <User className="w-5 h-5 text-emerald-400" />
            Diarized Conversation Stream
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Diarized turns with start/end millisecond offsets and speaker labeling.
          </p>
        </div>
        <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full font-mono border border-slate-700">
          {segments.length} turns
        </span>
      </div>

      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
        {segments.map((segment, idx) => {
          const color = SPEAKER_COLORS[segment.speaker_label] || 'bg-slate-800/40 border-slate-700 text-slate-300';
          const badge = SPEAKER_BADGES[segment.speaker_label] || 'bg-slate-800 text-slate-400 border-slate-700';

          return (
            <div
              key={segment.id || segment.segment_id || idx}
              className={`p-4 rounded-xl border transition hover:border-slate-700 ${color}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${badge}`}>
                    {segment.speaker_name || segment.speaker_label.replace('_', ' ').toUpperCase()}
                  </span>
                  {segment.confidence !== undefined && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      conf: {(segment.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 text-[11px] text-slate-400 font-mono">
                  <Clock className="w-3 h-3 text-slate-500" />
                  <span>{segment.start_time.toFixed(1)}s - {segment.end_time.toFixed(1)}s</span>
                </div>
              </div>
              <p className="text-sm leading-relaxed text-slate-200">{segment.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
