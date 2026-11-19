import React, { useEffect, useRef, useState } from 'react';
import { 
  Mic, 
  Square, 
  Upload, 
  Sparkles, 
  Radio, 
  CheckCircle2, 
  Volume2, 
  ArrowRight,
  Headphones
} from 'lucide-react';
import { createSession, Session, uploadAudioFile } from '../api/client';
import { devanagariToHinglish } from '../utils/hinglish';
import { RecordingCapture } from '../api/recording';

interface Props {
  onSessionCreated?: (session: Session) => void;
  onViewTranscript?: (sessionId: string) => void;
}

const HARDWARE_MODES = [
  { id: 'neo1-badge-01', label: 'Neo-1 Lapel Badge' },
  { id: 'studio-desk-mic', label: 'Studio Desk' },
  { id: 'mobile-companion', label: 'Mobile Device' },
];

export const AudioRecorder: React.FC<Props> = ({ onSessionCreated, onViewTranscript }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [session, setSession] = useState<Session | null>(null);
  const [completedSessionId, setCompletedSessionId] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<'multi' | 'hi' | 'en'>('multi');
  const [selectedHardware, setSelectedHardware] = useState('neo1-badge-01');
  const [statusMessage, setStatusMessage] = useState('Ready to capture voice memory');
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // Real-time speech transcription state
  const [captionsAvailable, setCaptionsAvailable] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState<string>('');
  const [interimText, setInterimText] = useState<string>('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const captureRef = useRef<RecordingCapture | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<any>(null);

  // Timer effect
  useEffect(() => {
    if (isRecording) {
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRecording]);

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Cleanup hardware mic, WebSocket, and speech recognition on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop(); } catch {}
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      captureRef.current?.close();
    };
  }, []);

  const startLiveStreaming = async () => {
    setIsStarting(true);
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error('Microphone access is not supported on this browser.');
      }
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'].find((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      if (!mimeType) throw new Error('This browser cannot record a supported audio format.');

      setStatusMessage('Requesting microphone permissions...');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const newSession = await createSession(selectedHardware, selectedLanguage);
      setSession(newSession);
      setCompletedSessionId(null);
      setCaptionsAvailable(false);
      setLiveTranscript('');
      setInterimText('');
      onSessionCreated?.(newSession);


      setStatusMessage('Connecting recorder…');
      const mediaRecorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 64000 });
      mediaRecorderRef.current = mediaRecorder;
      const capture = new RecordingCapture(
        newSession.id,
        mediaRecorder.mimeType,
        setStatusMessage,
        setCaptionsAvailable,
        (text, isFinal) => {
          const caption = selectedLanguage === 'en' ? text : devanagariToHinglish(text);
          if (isFinal) {
            setLiveTranscript((previous) => [previous, caption].filter(Boolean).join(' '));
            setInterimText('');
          } else {
            setInterimText(caption);
          }
        },
        () => {
          setCompletedSessionId(newSession.id);
          setIsUploading(false);
          setStatusMessage('Recording saved. Transcription is queued.');
        },
        (message) => {
          if (mediaRecorder.state !== 'inactive') mediaRecorder.stop();
          stream.getTracks().forEach((track) => track.stop());
          setIsRecording(false);
          setIsUploading(false);
          setStatusMessage(message);
        },
      );
      captureRef.current = capture;
      mediaRecorder.ondataavailable = (event) => capture.append(event.data);
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        capture.finish();
      };

      mediaRecorder.start(250);
      setIsRecording(true);

    } catch (error: any) {
      console.error('Audio recording failed:', error);
      setStatusMessage(`Error: ${error.message}`);
      setIsRecording(false);
      captureRef.current?.close();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    } finally {
      setIsStarting(false);
    }
  };

  const stopLiveStreaming = () => {
    setIsRecording(false);
    setIsUploading(true);
    setStatusMessage('Saving recording…');
    setInterimText('');
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
  };

  const handleFileUpload = async (file: File) => {
    if (!file || isRecording || isUploading || isStarting) return;

    try {
      setIsUploading(true);
      setStatusMessage(`Analyzing & uploading ${file.name}...`);
      const newSession = await createSession(selectedHardware, selectedLanguage);
      setSession(newSession);
      onSessionCreated?.(newSession);
      setStatusMessage(`Transcribing audio (${(file.size / (1024 * 1024)).toFixed(1)} MB)...`);
      await uploadAudioFile(newSession.id, file);
      setStatusMessage('Audio uploaded. Transcription is queued.');
      setCompletedSessionId(newSession.id);
    } catch (error: unknown) {
      setStatusMessage(`Upload failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFileUpload(file);
  };

  return (
    <div className="space-y-6">
      {/* Hero Recording Studio Card */}
      <div className="glass-card rounded-3xl p-6 md:p-8 relative overflow-hidden">
        {/* Subtle Ambient Glow Orbs */}
        <div 
          className={`absolute -top-24 -left-24 w-72 h-72 rounded-full blur-3xl transition-opacity duration-700 pointer-events-none ${
            isRecording ? 'bg-rose-500/20 opacity-100' : 'bg-sky-500/10 opacity-70'
          }`} 
        />
        <div 
          className={`absolute -bottom-24 -right-24 w-72 h-72 rounded-full blur-3xl transition-opacity duration-700 pointer-events-none ${
            isRecording ? 'bg-amber-500/15 opacity-100' : 'bg-indigo-500/10 opacity-70'
          }`} 
        />

        {/* Top Control Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8 relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-sky-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/25">
              <Radio className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg md:text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                Live Conversation Studio
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                  ✦ LLM Ready
                </span>
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Capture spoken conversations into structured minutes and action items</p>
            </div>
          </div>

          {/* Clean Controls: 2-Option Language Pill & Hardware Mode */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Direct Hindi / English Toggle Pill */}
            <div className="flex items-center p-1 rounded-2xl glass-pill">
              <button
                type="button"
                onClick={() => setSelectedLanguage('multi')}
                disabled={isRecording || isUploading || isStarting}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                  selectedLanguage === 'multi'
                    ? 'bg-gradient-to-r from-sky-500 to-indigo-600 text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                🇮🇳 Hindi + English
              </button>
              <button
                type="button"
                onClick={() => setSelectedLanguage('en')}
                disabled={isRecording || isUploading || isStarting}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                  selectedLanguage === 'en'
                    ? 'bg-gradient-to-r from-sky-500 to-indigo-600 text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                🌐 English
              </button>
            </div>

            {/* Hardware badge selector */}
            <div className="flex items-center gap-1.5 glass-pill px-3 py-1.5 rounded-2xl text-xs text-slate-700 dark:text-slate-300">
              <Headphones className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
              <select
                value={selectedHardware}
                onChange={(e) => setSelectedHardware(e.target.value)}
                disabled={isRecording || isUploading || isStarting}
                className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
              >
                {HARDWARE_MODES.map((h) => (
                  <option key={h.id} value={h.id} className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200">
                    {h.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Central Recording Pod */}
        <div className="flex flex-col items-center justify-center py-6 md:py-10 text-center relative z-10">
          {/* Big Action Orb Button */}
          <div className="relative mb-6">
            {!isRecording ? (
              <button
                onClick={startLiveStreaming}
                disabled={isUploading || isStarting}
                className="w-24 h-24 md:w-28 md:h-28 rounded-full bg-gradient-to-tr from-sky-500 via-cyan-400 to-indigo-600 hover:scale-105 active:scale-95 transition-all duration-300 flex flex-col items-center justify-center text-white shadow-[0_0_40px_rgba(14,165,233,0.35)] hover:shadow-[0_0_55px_rgba(14,165,233,0.55)] group cursor-pointer disabled:opacity-50"
              >
                <Mic className="w-9 h-9 md:w-11 md:h-11 transition-transform group-hover:scale-110" />
                <span className="text-[11px] font-semibold tracking-wide uppercase mt-1 opacity-90">Record</span>
              </button>
            ) : (
              <div className="relative">
                <div className="absolute inset-0 rounded-full animate-pulse-ring" />
                <button
                  onClick={stopLiveStreaming}
                  className="w-24 h-24 md:w-28 md:h-28 rounded-full bg-gradient-to-tr from-rose-500 via-red-500 to-pink-600 hover:scale-105 active:scale-95 transition-all duration-300 flex flex-col items-center justify-center text-white shadow-[0_0_50px_rgba(244,63,94,0.6)] cursor-pointer relative z-10"
                >
                  <Square className="w-8 h-8 fill-current" />
                  <span className="text-[11px] font-bold tracking-wide uppercase mt-1">Stop & AI</span>
                </button>
              </div>
            )}
          </div>

          {/* Recording Timer & Status */}
          <div className="space-y-2">
            {isRecording ? (
              <div className="flex items-center gap-3">
                <span className="w-3 h-3 rounded-full bg-rose-500 animate-ping" />
                <span className="font-mono text-2xl font-bold tracking-wider text-slate-900 dark:text-white">
                  {formatTimer(recordingSeconds)}
                </span>
                {/* Audio Waveform Bars — 8 bars */}
                <div className="flex items-end gap-[3px] h-9 px-2">
                  <div className="w-[3px] bg-gradient-to-t from-sky-500 to-cyan-300 rounded-full animate-wave-1" />
                  <div className="w-[3px] bg-gradient-to-t from-indigo-500 to-violet-300 rounded-full animate-wave-2" />
                  <div className="w-[3px] bg-gradient-to-t from-sky-500 to-cyan-300 rounded-full animate-wave-3" />
                  <div className="w-[3px] bg-gradient-to-t from-rose-500 to-pink-300 rounded-full animate-wave-4" />
                  <div className="w-[3px] bg-gradient-to-t from-sky-500 to-cyan-300 rounded-full animate-wave-5" />
                  <div className="w-[3px] bg-gradient-to-t from-indigo-500 to-violet-300 rounded-full animate-wave-6" />
                  <div className="w-[3px] bg-gradient-to-t from-emerald-500 to-teal-300 rounded-full animate-wave-7" />
                  <div className="w-[3px] bg-gradient-to-t from-sky-500 to-cyan-300 rounded-full animate-wave-8" />
                </div>
              </div>
            ) : (
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Tap button to start recording or speak naturally
              </p>
            )}
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
              {selectedLanguage === 'multi'
                ? 'Speak in Hindi or English — automatically saved in structured MOM.'
                : 'Speak in English — automatically converted into structured meeting notes.'}
            </p>
          </div>
        </div>

        {/* Live Speech Stream Pill */}
        {(isRecording || liveTranscript || interimText) && (
          <div className="mt-4 p-5 rounded-2xl border border-sky-500/25 bg-white/70 dark:bg-slate-950/60 backdrop-blur-md relative z-10 transition-all">
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="flex items-center gap-2 text-xs font-semibold text-sky-600 dark:text-sky-400">
                <Volume2 className="w-3.5 h-3.5" />
                Live Speech Stream
              </span>
              {isRecording && captionsAvailable && (
                <span className="flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400 font-mono">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Listening in real-time...
                </span>
              )}
            </div>
            <p className="text-sm text-slate-800 dark:text-slate-200 leading-relaxed min-h-[48px]">
              {liveTranscript ? (
                <>
                  {liveTranscript}{' '}
                  {interimText && <span className="text-sky-500 dark:text-sky-300 italic">{interimText}</span>}
                </>
              ) : interimText ? (
                <span className="text-sky-500 dark:text-sky-300 italic">{interimText}</span>
              ) : (
                <span className="text-slate-400 dark:text-slate-500 italic">{captionsAvailable ? 'Waiting for speech…' : 'Live captions unavailable. A transcript is generated after recording.'}</span>
              )}
            </p>
          </div>
        )}

        {/* Status Bar */}
        <div className="mt-6 pt-4 border-t border-slate-200 dark:border-white/[0.06] flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 relative z-10">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isRecording ? 'bg-rose-500 animate-pulse' : 'bg-emerald-500 dark:bg-emerald-400'}`} />
            <span className="truncate">{statusMessage}</span>
          </div>
          {session && (
            <span className="font-mono text-[10px] text-slate-500 bg-slate-100 dark:bg-white/[0.04] px-2.5 py-1 rounded-md border border-slate-200 dark:border-white/[0.08]">
              Session: {session.id.slice(0, 8)}...
            </span>
          )}
        </div>
      </div>

      {/* Audio File Dropzone & Celebration Banner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Upload Dropzone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`glass-card rounded-2xl p-6 border-2 border-dashed transition-all flex flex-col items-center justify-center text-center cursor-pointer ${
            isDragging 
              ? 'border-sky-500 bg-sky-50 dark:bg-sky-500/10 scale-[1.01]' 
              : 'border-slate-300 dark:border-white/10 hover:border-slate-400 dark:hover:border-white/20 bg-white/40 dark:bg-slate-900/30'
          }`}
        >
          <input
            type="file"
            id="audio-file-input"
            accept="audio/*,.wav,.opus,.ogg,.mp3,.m4a,.webm"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFileUpload(file);
            }}
            disabled={isUploading || isRecording || isStarting}
            className="hidden"
          />
          <label htmlFor="audio-file-input" className="cursor-pointer flex flex-col items-center">
            <div className="w-12 h-12 rounded-2xl bg-sky-50 dark:bg-white/[0.05] border border-sky-100 dark:border-white/[0.08] flex items-center justify-center text-sky-500 dark:text-sky-400 mb-3 group-hover:scale-110 transition">
              <Upload className="w-5 h-5" />
            </div>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
              {isUploading ? 'Processing Audio File...' : 'Upload Existing Audio Recording'}
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
              Drag & drop MP3, WAV, M4A, or OPUS files up to 100MB
            </p>
          </label>
        </div>

        {/* Success / Next Step Card */}
        {completedSessionId ? (
          <div className="glass-card rounded-2xl p-6 border border-emerald-500/30 bg-emerald-50/70 dark:bg-emerald-950/20 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 mb-2">
                <CheckCircle2 className="w-5 h-5" />
                <span className="text-xs uppercase font-bold tracking-wider">Intelligence Ready</span>
              </div>
              <h4 className="text-base font-bold text-slate-900 dark:text-white">Your Meeting is Processed</h4>
              <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                AI has generated your executive title, Roman Hinglish summary, key decisions, and action items.
              </p>
            </div>
            <button
              onClick={() => onViewTranscript?.(completedSessionId)}
              className="mt-4 flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-xs shadow-lg shadow-emerald-500/20 transition cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              View Diarized Transcript & MOM
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="glass-card rounded-2xl p-6 border border-slate-200 dark:border-white/[0.06] bg-white/40 dark:bg-slate-900/20 flex flex-col justify-between">
            <div>
              <span className="text-xs uppercase font-semibold tracking-wider text-indigo-500 dark:text-indigo-400">Language System</span>
              <h4 className="text-base font-semibold text-slate-900 dark:text-white mt-1">Hindi & English Focused</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                Choose Hindi/Hinglish or English with a single tap. All output notes are cleanly structured with decisions and assigned action items.
              </p>
            </div>
            <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-200 dark:border-white/[0.05] text-[11px] text-slate-500">
              <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.05] text-slate-700 dark:text-slate-300">Decisions</span>
              <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.05] text-slate-700 dark:text-slate-300">Action Items</span>
              <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.05] text-slate-700 dark:text-slate-300">Speaker Diarization</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
