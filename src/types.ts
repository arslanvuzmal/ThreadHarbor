export interface InteractionMetric {
  id: number;
  session_id: string;
  timestamp: string;
  intent: string | null;
  llm_model: string | null;
  tokens_used: number;
  latency_ms: number;
  used_fallback: boolean;
  escalated: boolean;
}

export interface KpiSummary {
  total_messages: number;
  total_tokens: number;
  avg_latency: number;
  escalations: number;
  escalation_rate: number;
  fallbacks: number;
  fallback_rate: number;
}

export interface SessionData {
  session_id: string;
  state: 'IDLE' | 'AWAITING_INPUT' | 'PROCESSING' | 'ESCALATED' | 'HUMAN_HANDOFF';
  user_profile: {
    name: string;
    phone: string;
    tier: string;
  };
  transcript: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp?: string;
  }>;
  low_confidence_consecutive_count: number;
  last_user_message: string | null;
  ticket_id: string | null;
  phone_number_id: string | null;
  last_interaction_timestamp: number;
  is_within_24h_window: boolean;
}

export interface ZendeskTicket {
  ticket_id: string;
  session_id: string;
  status: 'open' | 'closed' | 'pending';
  escalation_reason: string;
  conversation_summary: string;
  created_at: string;
  updated_at: string;
  messages: string[];
  user_profile: {
    name: string;
    phone: string;
    tier: string;
  };
}

export interface SystemStatus {
  status: 'ok' | 'degraded' | 'error';
  redis: 'ok' | 'down';
  qdrant: 'ok' | 'down';
  database: 'ok' | 'down';
  timestamp: string;
  uptime_seconds: number;
}

export interface SimulationResult {
  reply_text: string;
  masked_input: string;
  state: string;
  escalated: boolean;
  used_fallback: boolean;
  intent: string;
  latency_ms: number;
  llm_model: string | null;
  tokens_used: number;
  ticket_id: string | null;
  session: SessionData;
}
