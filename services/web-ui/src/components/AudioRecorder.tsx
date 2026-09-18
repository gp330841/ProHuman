import React, { useState, useRef } from 'react';
import { Mic, Square, Upload, Radio, CheckCircle } from 'lucide-react';
import { createSession, uploadAudioFile, Session } from '../api/client';

interface Props {
  onSessionCreated?: (session: Session) => void;
}

export const AudioRecorder: React.FC<Props> = ({ onSessionCreated }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [chunksSent, setChunksSent] = useState(0);
  const [bytesSent, setBytesSent] = useState(0);
  const [statusMessage, setStatusMessage] = useState<string>('Ready to capture audio');
  const [isUploading, setIsUploading] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const startLiveStreaming = async () => {
    try {
      setStatusMessage('Initializing new audio session...');
      const newSession = await createSession('browser-mic-gadget');
      setSession(newSession);
      if (onSessionCreated) onSessionCreated(newSession);

      // Open WebSocket connection
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/audio/stream/${newSession.id}`;
      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = async () => {
        setStatusMessage('WebSocket connected. Sending audio handshake...');
        // Send initial AudioSessionConfig handshake
        ws.send(JSON.stringify({
          format: 'WAV',
          sample_rate: 16000,
          channels: 1,
          chunk_size_bytes: 4096
        }));

        // Access microphone
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        mediaRecorderRef.current = mediaRecorder;

        let sentCount = 0;
        let totalBytes = 0;

        mediaRecorder.ondataavailable = async (e) => {
          if (e.data && e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            const arrayBuffer = await e.data.arrayBuffer();
            ws.send(arrayBuffer);
            sentCount++;
            totalBytes += arrayBuffer.byteLength;
            setChunksSent(sentCount);
            setBytesSent(totalBytes);
          }
        };

        mediaRecorder.start(250); // Emit chunk every 250ms
        setIsRecording(true);
        setStatusMessage('Streaming audio live to Ingestion Gateway...');
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setStatusMessage('WebSocket streaming error');
      };

      ws.onclose = () => {
        setStatusMessage('Audio stream closed');
      };

    } catch (err: any) {
      console.error(err);
      setStatusMessage(`Error starting recording: ${err.message}`);
    }
  };

  const stopLiveStreaming = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t: MediaStreamTrack) => t.stop());
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    setIsRecording(false);
    setStatusMessage('Recording ended. Processing dispatched to Celery pipeline!');
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsUploading(true);
      setStatusMessage('Creating upload session...');
      const newSession = await createSession('file-upload-gadget');
      setSession(newSession);
      if (onSessionCreated) onSessionCreated(newSession);

      setStatusMessage(`Uploading audio file (${(file.size / 1024).toFixed(1)} KB)...`);
      await uploadAudioFile(newSession.id, file);
      setStatusMessage('File uploaded successfully! Transcribing with Nova-2...');
    } catch (err: any) {
      setStatusMessage(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl backdrop-blur">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold flex items-center gap-2 text-white">
          <Radio className="w-5 h-5 text-sky-400 animate-pulse" />
          Hardware Gadget Ingestion Simulator
        </h2>
        {session && (
          <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full border border-slate-700 font-mono">
            Session: {session.id.slice(0, 8)}...
          </span>
        )}
      </div>

      <p className="text-sm text-slate-400 mb-6">
        Test audio streaming over WebSockets or upload audio files to trigger real-time VAD, MinIO S3 storage, Deepgram Nova-2 diarization, and pgvector embeddings.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Live Mic Recorder Card */}
        <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-lg flex flex-col justify-between">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-sky-400">Option 1</span>
            <h3 className="text-base font-semibold text-white mt-1">Live Microphone WebSocket Stream</h3>
            <p className="text-xs text-slate-400 mt-1">
              Captures browser microphone audio frames and streams raw binary chunks to <code>/api/v1/audio/stream</code>.
            </p>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center gap-3">
            {!isRecording ? (
              <button
                onClick={startLiveStreaming}
                className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white font-medium rounded-lg text-sm transition shadow-lg shadow-sky-900/20"
              >
                <Mic className="w-4 h-4" /> Start Recording
              </button>
            ) : (
              <button
                onClick={stopLiveStreaming}
                className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-medium rounded-lg text-sm transition animate-pulse"
              >
                <Square className="w-4 h-4" /> Stop & Finalize
              </button>
            )}

            {isRecording && (
              <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
                <span>Chunks: <b className="text-sky-400">{chunksSent}</b></span>
                <span>Bytes: <b className="text-sky-400">{(bytesSent / 1024).toFixed(1)} KB</b></span>
              </div>
            )}
          </div>
        </div>

        {/* File Upload Card */}
        <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-lg flex flex-col justify-between">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-emerald-400">Option 2</span>
            <h3 className="text-base font-semibold text-white mt-1">Direct Audio File Ingestion</h3>
            <p className="text-xs text-slate-400 mt-1">
              Upload pre-recorded Opus or WAV audio files through the chunked HTTP endpoint with idempotency verification.
            </p>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-800/80">
            <label className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-medium rounded-lg text-sm transition cursor-pointer w-fit border border-slate-700">
              <Upload className="w-4 h-4 text-emerald-400" />
              {isUploading ? 'Uploading...' : 'Choose WAV / Opus File'}
              <input
                type="file"
                accept="audio/*,.wav,.opus,.ogg"
                onChange={handleFileUpload}
                disabled={isUploading || isRecording}
                className="hidden"
              />
            </label>
          </div>
        </div>
      </div>

      {/* Realtime Status Bar */}
      <div className="flex items-center gap-2 bg-slate-950 px-4 py-2.5 rounded-lg border border-slate-800/80 text-xs">
        {isRecording ? (
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
        ) : (
          <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
        )}
        <span className="text-slate-400 font-mono">Status:</span>
        <span className="text-slate-200">{statusMessage}</span>
      </div>
    </div>
  );
};
