import React, { useRef, useState } from 'react';
import { CheckCircle, Mic, Radio, Square, Upload } from 'lucide-react';
import { createSession, Session, uploadAudioFile } from '../api/client';

interface Props {
  onSessionCreated?: (session: Session) => void;
}

export const AudioRecorder: React.FC<Props> = ({ onSessionCreated }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [chunksSent, setChunksSent] = useState(0);
  const [bytesSent, setBytesSent] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Ready to capture audio');
  const [isUploading, setIsUploading] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const stoppingRef = useRef(false);

  const startLiveStreaming = async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error('This browser does not support microphone recording.');
      }
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm'].find((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      if (!mimeType) throw new Error('This browser cannot record WebM audio.');

      setStatusMessage('Requesting microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      setStatusMessage('Creating audio session...');
      const newSession = await createSession('browser-mic-gadget');
      setSession(newSession);
      onSessionCreated?.(newSession);

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(
        `${protocol}//${window.location.host}/api/v1/audio/stream/${newSession.id}`,
      );
      wsRef.current = socket;
      stoppingRef.current = false;
      setChunksSent(0);
      setBytesSent(0);

      await new Promise<void>((resolve, reject) => {
        let didOpen = false;
        socket.onopen = () => {
          didOpen = true;
          socket.send(JSON.stringify({
            format: 'OPUS',
            sample_rate: 16000,
            channels: 1,
            chunk_size_bytes: 4096,
          }));

          const recorder = new MediaRecorder(stream, { mimeType });
          mediaRecorderRef.current = recorder;
          let chunkCount = 0;
          let byteCount = 0;
          let pendingChunk = Promise.resolve();

          recorder.ondataavailable = (event) => {
            if (event.data.size === 0 || socket.readyState !== WebSocket.OPEN) return;
            pendingChunk = pendingChunk.then(async () => {
              const chunk = await event.data.arrayBuffer();
              if (socket.readyState !== WebSocket.OPEN) return;
              socket.send(chunk);
              chunkCount += 1;
              byteCount += chunk.byteLength;
              setChunksSent(chunkCount);
              setBytesSent(byteCount);
            });
          };
          recorder.onerror = () => {
            setStatusMessage('Microphone recording failed.');
            stopLiveStreaming();
          };
          recorder.onstop = async () => {
            await pendingChunk;
            stream.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
            if (socket.readyState === WebSocket.OPEN) socket.close();
          };

          recorder.start(250);
          setIsRecording(true);
          setStatusMessage('Streaming microphone audio to the gateway...');
          resolve();
        };
        socket.onerror = () => {
          if (!didOpen) reject(new Error('Could not connect to the audio gateway.'));
          else setStatusMessage('Audio gateway connection failed.');
        };
        socket.onclose = (event) => {
          if (!didOpen) {
            reject(new Error(event.reason || 'Audio gateway rejected the connection.'));
          } else if (stoppingRef.current) {
            setStatusMessage('Recording uploaded. Transcription has been queued.');
          } else {
            setStatusMessage(event.reason || 'Audio connection closed unexpectedly.');
            setIsRecording(false);
            if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop();
            stream.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
          }
        };
      });
    } catch (error: unknown) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      wsRef.current?.close();
      setIsRecording(false);
      setStatusMessage(
        `Could not start recording: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  };

  const stopLiveStreaming = () => {
    stoppingRef.current = true;
    setStatusMessage('Finishing audio upload...');
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
      return;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.close();
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setIsUploading(true);
      setStatusMessage('Creating upload session...');
      const newSession = await createSession('file-upload-gadget');
      setSession(newSession);
      onSessionCreated?.(newSession);
      setStatusMessage(`Uploading audio file (${(file.size / 1024).toFixed(1)} KB)...`);
      await uploadAudioFile(newSession.id, file);
      setStatusMessage('File uploaded. Transcription has been queued.');
    } catch (error: unknown) {
      setStatusMessage(`Upload failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsUploading(false);
      event.target.value = '';
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl backdrop-blur">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold flex items-center gap-2 text-white">
          <Radio className="w-5 h-5 text-sky-400" />
          Audio ingestion
        </h2>
        {session && (
          <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full border border-slate-700 font-mono">
            Session: {session.id.slice(0, 8)}...
          </span>
        )}
      </div>

      <p className="text-sm text-slate-400 mb-6">
        Stream browser microphone audio or upload a recording. Audio is stored and queued for
        transcription, embedding, and meeting analysis.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-lg flex flex-col justify-between">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-sky-400">Live audio</span>
            <h3 className="text-base font-semibold text-white mt-1">Microphone stream</h3>
            <p className="text-xs text-slate-400 mt-1">
              Captures browser WebM/Opus audio and streams it to the gateway over WebSocket.
            </p>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center gap-3">
            {!isRecording ? (
              <button
                onClick={startLiveStreaming}
                disabled={isUploading}
                className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 text-white font-medium rounded-lg text-sm transition"
              >
                <Mic className="w-4 h-4" /> Start recording
              </button>
            ) : (
              <button
                onClick={stopLiveStreaming}
                className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-medium rounded-lg text-sm transition"
              >
                <Square className="w-4 h-4" /> Stop & finalize
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

        <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-lg flex flex-col justify-between">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-emerald-400">File upload</span>
            <h3 className="text-base font-semibold text-white mt-1">Upload a recording</h3>
            <p className="text-xs text-slate-400 mt-1">
              Upload an audio file up to 100 MB to start the same transcription pipeline.
            </p>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-800/80">
            <label className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-medium rounded-lg text-sm transition cursor-pointer w-fit border border-slate-700">
              <Upload className="w-4 h-4 text-emerald-400" />
              {isUploading ? 'Uploading...' : 'Choose audio file'}
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
