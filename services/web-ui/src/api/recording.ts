import { API_BASE, getAccessToken } from './client';

type CaptureReply =
  | { type: 'ready'; next_chunk: number; live_captions: boolean }
  | { type: 'ack'; index: number }
  | { type: 'caption_unavailable' }
  | { type: 'caption'; text: string; final: boolean }
  | { type: 'finished' };

export class RecordingCapture {
  private socket: WebSocket | undefined;
  private readonly pending = new Map<number, Blob>();
  private nextIndex = 0;
  private acknowledged = 0;
  private bytes = 0;
  private retries = 0;
  private reconnectTimer: number | undefined;
  private responseTimer: number | undefined;
  private ready = false;
  private waiting = false;
  private finishing = false;
  private closed = false;

  constructor(
    private readonly sessionId: string,
    private readonly mimeType: string,
    private readonly onStatus: (message: string) => void,
    private readonly onCaptionAvailability: (available: boolean) => void,
    private readonly onCaption: (text: string, isFinal: boolean) => void,
    private readonly onFinished: () => void,
    private readonly onError: (message: string) => void,
  ) {
    this.connect();
  }

  append(data: Blob) {
    if (this.closed || this.finishing) return;
    this.bytes += data.size;
    if (this.bytes > 100 * 1024 * 1024) {
      this.fail('Recording exceeds 100 MB.');
      return;
    }
    for (let offset = 0; offset < data.size; offset += 256 * 1024) {
      this.pending.set(this.nextIndex++, data.slice(offset, offset + 256 * 1024));
    }
    this.sendNext();
  }

  finish() {
    if (this.closed) return;
    if (!this.nextIndex) {
      this.fail('No audio was captured.');
      return;
    }
    this.finishing = true;
    this.sendNext();
  }

  close() {
    this.closed = true;
    clearTimeout(this.reconnectTimer);
    clearTimeout(this.responseTimer);
    this.socket?.close();
    this.pending.clear();
  }

  private fail(message: string) {
    this.close();
    this.onError(message);
  }

  private connect() {
    const url = new URL(API_BASE + '/audio/stream/' + this.sessionId, window.location.origin);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(url, ['prohuman.audio.v1', 'bearer.' + getAccessToken()]);
    this.socket = socket;
    this.ready = false;
    this.waiting = false;
    this.expectResponse();
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'start', mime_type: this.mimeType }));
    };
    socket.onmessage = ({ data }) => {
      if (this.closed || socket !== this.socket) return;
      const reply: CaptureReply = JSON.parse(data);
      if (reply.type === 'caption_unavailable') {
        this.onCaptionAvailability(false);
        return;
      }
      if (reply.type === 'caption') {
        this.onCaption(reply.text, reply.final);
        return;
      }
      clearTimeout(this.responseTimer);
      if (reply.type === 'finished') {
        this.close();
        this.onFinished();
        return;
      }
      if (reply.type === 'ready') this.onCaptionAvailability(reply.live_captions);
      const next = reply.type === 'ready' ? reply.next_chunk : reply.index + 1;
      if (next < this.acknowledged || next > this.nextIndex) {
        this.fail('Could not resume this recording.');
        return;
      }
      if (next > this.acknowledged) this.retries = 0;
      while (this.acknowledged < next) this.pending.delete(this.acknowledged++);
      this.ready = true;
      this.waiting = false;
      this.onStatus(this.finishing ? 'Saving recording…' : 'Recording audio…');
      this.sendNext();
    };
    socket.onclose = (event) => {
      if (this.closed || socket !== this.socket) return;
      clearTimeout(this.responseTimer);
      this.ready = false;
      this.onCaptionAvailability(false);
      if ([1002, 1003, 1008, 1009].includes(event.code) || this.retries >= 12) {
        this.fail(event.reason || 'Could not save the recording.');
        return;
      }
      this.onStatus('Connection interrupted. Retrying recording upload…');
      this.reconnectTimer = window.setTimeout(
        () => this.connect(), Math.min(1000 * 2 ** this.retries++, 5000),
      );
    };
  }

  private expectResponse(timeout = 15000) {
    clearTimeout(this.responseTimer);
    this.responseTimer = window.setTimeout(() => this.socket?.close(), timeout);
  }

  private sendNext() {
    const socket = this.socket;
    if (!this.ready || this.waiting || socket?.readyState !== WebSocket.OPEN) return;
    const chunk = this.pending.get(this.acknowledged);
    if (chunk) {
      const header = new DataView(new ArrayBuffer(4));
      header.setUint32(0, this.acknowledged);
      this.waiting = true;
      socket.send(new Blob([header.buffer, chunk]));
      this.expectResponse();
    } else if (this.finishing) {
      this.waiting = true;
      socket.send(JSON.stringify({ type: 'finish', chunk_count: this.nextIndex }));
      this.expectResponse(120000);
    }
  }
}
