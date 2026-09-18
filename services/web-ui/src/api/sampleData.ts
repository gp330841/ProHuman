import { Session, TranscriptSegment, MOMData, SearchResult } from './client';

export const SAMPLE_SESSIONS: Session[] = [
  {
    id: 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d',
    device_id: 'prohuman-esp32-badge-01',
    status: 'COMPLETED',
    created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 1.5).toISOString(),
    audio_format: 'OPUS',
    duration_seconds: 1420.5,
  },
  {
    id: 'f9e8d7c6-b5a4-4321-9876-fedcba098765',
    device_id: 'tabletop-mic-hub-alpha',
    status: 'COMPLETED',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000 + 1800000).toISOString(),
    audio_format: 'WAV',
    duration_seconds: 1845.0,
  },
  {
    id: '3c4d5e6f-7a8b-49c0-9d1e-2f3a4b5c6d7e',
    device_id: 'browser-mic-gadget',
    status: 'RECORDING',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    audio_format: 'WAV',
    duration_seconds: 145.2,
  },
];

export const SAMPLE_TRANSCRIPTS: Record<string, TranscriptSegment[]> = {
  'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d': [
    {
      segment_id: 'seg-001',
      speaker_label: 'speaker_0',
      speaker_name: 'Dr. Sarah Chen (CTO)',
      text: "Good morning everyone. Let's review the hardware audio gadget architecture. We need to finalize the ESP32 I2S microphone streaming pipeline before the beta rollout.",
      start_time: 1.2,
      end_time: 8.5,
      confidence: 0.98,
    },
    {
      segment_id: 'seg-002',
      speaker_label: 'speaker_1',
      speaker_name: 'Alex Rivera (Firmware Lead)',
      text: "On the firmware side, we switched to Opus 16kHz mono. That drops our WiFi throughput from 256kbps to 32kbps while preserving crystal clear speech intelligibility for Deepgram Nova-2.",
      start_time: 9.1,
      end_time: 17.8,
      confidence: 0.96,
    },
    {
      segment_id: 'seg-003',
      speaker_label: 'speaker_0',
      speaker_name: 'Dr. Sarah Chen (CTO)',
      text: "That's a massive win for battery life. What about backpressure when network connectivity fluctuates?",
      start_time: 18.2,
      end_time: 23.4,
      confidence: 0.99,
    },
    {
      segment_id: 'seg-004',
      speaker_label: 'speaker_1',
      speaker_name: 'Alex Rivera (Firmware Lead)',
      text: "We implemented a 30-second circular PSRAM ring buffer on the ESP32-S3. If the WebSocket connection drops, it buffers packets and flushes them upon reconnect with monotonic chunk indexes.",
      start_time: 24.0,
      end_time: 34.6,
      confidence: 0.95,
    },
    {
      segment_id: 'seg-005',
      speaker_label: 'speaker_2',
      speaker_name: 'Elena Rostova (Backend Staff)',
      text: "On the backend gateway, we're using asyncio.Queue with maxsize 100. If consumer workers lag, TCP backpressure automatically throttles the socket without dropping packets.",
      start_time: 35.2,
      end_time: 44.8,
      confidence: 0.97,
    },
    {
      segment_id: 'seg-006',
      speaker_label: 'speaker_0',
      speaker_name: 'Dr. Sarah Chen (CTO)',
      text: "Excellent. Let's also ensure our pgvector hybrid search uses Reciprocal Rank Fusion with k=60 so users can search both exact names and fuzzy conversational topics.",
      start_time: 45.5,
      end_time: 55.1,
      confidence: 0.98,
    }
  ],
  'f9e8d7c6-b5a4-4321-9876-fedcba098765': [
    {
      segment_id: 'seg-101',
      speaker_label: 'speaker_0',
      speaker_name: 'Michael Vance (Product)',
      text: "Let's review the Q3 budget allocation for our cloud STT models. Deepgram Nova-2 is currently costing $0.0043 per minute.",
      start_time: 2.0,
      end_time: 9.8,
      confidence: 0.97,
    },
    {
      segment_id: 'seg-102',
      speaker_label: 'speaker_1',
      speaker_name: 'Priya Patel (Finance)',
      text: "Based on 50,000 active gadgets recording 2 hours daily, our projected monthly speech infrastructure cost is around $25,800. We approved this budget yesterday.",
      start_time: 10.4,
      end_time: 21.0,
      confidence: 0.99,
    }
  ]
};

export const SAMPLE_MOM: Record<string, MOMData> = {
  'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d': {
    title: 'ESP32 Audio Gadget & Streaming Architecture Review',
    date: new Date(Date.now() - 3600000 * 2).toISOString(),
    attendees: ['Dr. Sarah Chen (CTO)', 'Alex Rivera (Firmware Lead)', 'Elena Rostova (Backend Staff)'],
    executive_summary:
      'The engineering leadership finalized the audio ingestion pipeline. The ESP32-S3 firmware now streams Opus 16kHz audio over binary WebSockets with a 30-second PSRAM ring buffer for dropout resilience. The backend gateway enforces asyncio queue backpressure and persists chunks directly into MinIO S3 before dispatching to Deepgram Nova-2 and pgvector hybrid search.',
    agenda_items: [
      {
        topic: 'Firmware Codec & Bandwidth Optimization',
        summary: 'Evaluated raw PCM vs Opus. Selected Opus 16kHz mono, reducing network throughput from 256kbps to 32kbps.',
        speakers_involved: ['Alex Rivera', 'Dr. Sarah Chen']
      },
      {
        topic: 'Network Dropout & Backpressure Handling',
        summary: 'Agreed on 30s hardware ring buffer and FastAPI gateway asyncio.Queue bounded throttling.',
        speakers_involved: ['Alex Rivera', 'Elena Rostova']
      },
      {
        topic: 'Hybrid Search (RRF) Implementation',
        summary: 'Configured PostgreSQL 16 pgvector HNSW cosine distance with tsvector lexical search via RRF k=60.',
        speakers_involved: ['Dr. Sarah Chen', 'Elena Rostova']
      }
    ],
    decisions: [
      {
        description: 'Adopt Opus 16kHz mono as default hardware capture format to maximize battery life and minimize cellular/WiFi bandwidth.',
        made_by: 'Alex Rivera',
        confidence: 0.99,
        timestamp: 15.2
      },
      {
        description: 'Standardize on Reciprocal Rank Fusion (RRF k=60) for all cross-session conversation queries.',
        made_by: 'Dr. Sarah Chen',
        confidence: 0.98,
        timestamp: 52.0
      }
    ],
    action_items: [
      {
        description: 'Merge ESP32 circular PSRAM ring buffer reconnection PR to master',
        assignee: 'Alex Rivera',
        deadline: '2026-09-22',
        priority: 'critical',
        confidence: 0.97,
        status: 'in_progress'
      },
      {
        description: 'Implement Celery task dead-letter queue (DLQ) replay policy for transient Deepgram rate limits',
        assignee: 'Elena Rostova',
        deadline: '2026-09-24',
        priority: 'high',
        confidence: 0.95,
        status: 'pending'
      },
      {
        description: 'Prepare load testing script simulating 500 concurrent WebSocket streams',
        assignee: 'QA Lead',
        deadline: '2026-09-26',
        priority: 'medium',
        confidence: 0.91,
        status: 'pending'
      }
    ],
    follow_ups: [
      {
        description: 'Check battery drain curve when streaming continuously over BLE vs WiFi',
        responsible_party: 'Hardware QA'
      },
      {
        description: 'Verify HNSW indexing build times once database crosses 1,000,000 segments',
        responsible_party: 'Database Architect'
      }
    ]
  }
};

export const SAMPLE_SEARCH_RESULTS: SearchResult[] = [
  {
    segment_id: 'seg-004',
    session_id: 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d',
    speaker_label: 'Alex Rivera (Firmware Lead)',
    text: "We implemented a 30-second circular PSRAM ring buffer on the ESP32-S3. If the WebSocket connection drops, it buffers packets and flushes them upon reconnect with monotonic chunk indexes.",
    start_time: 24.0,
    end_time: 34.6,
    rrf_score: 0.0328,
    vector_rank: 1,
    text_rank: 2,
  },
  {
    segment_id: 'seg-005',
    session_id: 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d',
    speaker_label: 'Elena Rostova (Backend Staff)',
    text: "On the backend gateway, we're using asyncio.Queue with maxsize 100. If consumer workers lag, TCP backpressure automatically throttles the socket without dropping packets.",
    start_time: 35.2,
    end_time: 44.8,
    rrf_score: 0.0315,
    vector_rank: 2,
    text_rank: 1,
  },
  {
    segment_id: 'seg-002',
    session_id: 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d',
    speaker_label: 'Alex Rivera (Firmware Lead)',
    text: "On the firmware side, we switched to Opus 16kHz mono. That drops our WiFi throughput from 256kbps to 32kbps while preserving crystal clear speech intelligibility for Deepgram Nova-2.",
    start_time: 9.1,
    end_time: 17.8,
    rrf_score: 0.0274,
    vector_rank: 3,
    text_rank: 4,
  }
];

export const SAMPLE_AGENT_RESPONSES: Record<string, any> = {
  default: {
    response:
      "Based on the meeting records from the ESP32 Audio Gadget Architecture Review:\n\n" +
      "1. **Audio Codec**: The team finalized on **Opus 16kHz mono**, cutting bandwidth from 256kbps to 32kbps to preserve battery.\n" +
      "2. **Resilience**: A 30-second PSRAM circular ring buffer handles connection dropouts, while the backend gateway uses `asyncio.Queue` (maxsize=100) to apply TCP backpressure.\n" +
      "3. **Pending Commitments**:\n" +
      "   - **Alex Rivera**: Merge circular PSRAM ring buffer PR by **Sep 22** (CRITICAL)\n" +
      "   - **Elena Rostova**: Implement Celery task DLQ replay policy by **Sep 24** (HIGH)\n" +
      "   - **QA Lead**: Benchmark 500 concurrent WebSocket connections by **Sep 26** (MEDIUM)",
    latency_ms: 245,
    tool_calls: [
      {
        name: 'search_conversations',
        args: { query: 'ESP32 audio architecture commitments', search_mode: 'HYBRID' }
      },
      {
        name: 'query_action_items',
        args: { status_filter: ['pending', 'in_progress'], sort_by: 'priority' }
      }
    ]
  }
};
