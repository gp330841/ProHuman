import { useEffect, useRef, useState } from 'react';
import { fetchRecording, fetchSessionDetails, type TranscriptEvidence } from '../api/client';

export function evidenceTime(seconds: number): string {
  return Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
}

export function EvidencePlayer({ evidence, onClose }: { evidence: TranscriptEvidence; onClose: () => void }) {
  const [source, setSource] = useState('');
  const [excerpt, setExcerpt] = useState('');
  const [error, setError] = useState('');
  const playerRef = useRef<HTMLElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    let url = '';
    setSource('');
    setError('');
    playerRef.current?.scrollIntoView({ block: 'nearest' });
    fetchRecording(evidence.session_id, controller.signal).then((blob) => {
      if (controller.signal.aborted) return;
      url = URL.createObjectURL(blob);
      setSource(url);
    }).catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [evidence.session_id]);

  useEffect(() => {
    let current = true;
    setExcerpt('');
    fetchSessionDetails(evidence.session_id).then(({ segments }) => {
      if (current) setExcerpt(segments.find((segment) => segment.id === evidence.segment_id)?.text ?? '');
    }).catch(() => {});
    return () => { current = false; };
  }, [evidence.session_id, evidence.segment_id]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || audio.readyState === 0) return;
    audio.currentTime = evidence.start_time;
    void audio.play().catch(() => {});
  }, [evidence.start_time]);

  return (
    <section ref={playerRef} className="space-y-2 rounded-xl border border-slate-300 p-4 dark:border-slate-700" aria-label="Recording excerpt">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium">Recording at {evidenceTime(evidence.start_time)}</span>
        <button onClick={onClose} className="text-sky-700 dark:text-sky-300">Close player</button>
      </div>
      {source ? (
        <audio key={source} ref={audioRef} controls src={source} className="w-full"
          onLoadedMetadata={(event) => {
            event.currentTarget.currentTime = evidence.start_time;
            void event.currentTarget.play().catch(() => {});
          }} />
      ) : <p role="status" className="text-sm">{error || 'Loading recording…'}</p>}
      {excerpt && <blockquote className="text-sm text-slate-600 dark:text-slate-300">{excerpt}</blockquote>}
    </section>
  );
}
