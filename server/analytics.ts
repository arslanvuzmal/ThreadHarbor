export interface MetricRecord {
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

class AnalyticsStore {
  private metrics: MetricRecord[] = [];
  private idCounter = 1;

  constructor() {
    this.seedHistoricalMetrics();
  }

  private seedHistoricalMetrics() {
    const intents = [
      'product_inquiry',
      'order_status',
      'refund_request',
      'Explicit Request',
      'Sentiment: Negative',
      'business_hours',
      'account_access',
      'Policy Limit',
      'shipping_delay',
      'success_bot_chat'
    ];

    const models = ['gpt-4o-mini', 'gpt-4o', null];
    const now = Date.now();

    // Generate ~60 realistic telemetry events over the past 7 days
    for (let i = 60; i >= 1; i--) {
      const minutesAgo = i * 150 + Math.floor(Math.random() * 30);
      const timestamp = new Date(now - minutesAgo * 60000).toISOString();
      const isEscalated = Math.random() < 0.18;
      const isFallback = Math.random() < 0.08;
      const intent = isEscalated
        ? (Math.random() < 0.5 ? 'Explicit Request' : (Math.random() < 0.5 ? 'Policy Limit' : 'Sentiment: Negative'))
        : intents[Math.floor(Math.random() * intents.length)];

      const latency = isFallback
        ? Math.floor(Math.random() * 80) + 40
        : Math.floor(Math.random() * 450) + 180;

      const tokens = isFallback ? 0 : Math.floor(Math.random() * 120) + 35;
      const model = isFallback ? null : (tokens > 100 ? 'gpt-4o' : 'gpt-4o-mini');

      this.metrics.push({
        id: this.idCounter++,
        session_id: `+1415555${String(1000 + (i % 25)).padStart(4, '0')}`,
        timestamp,
        intent,
        llm_model: model,
        tokens_used: tokens,
        latency_ms: latency,
        used_fallback: isFallback,
        escalated: isEscalated
      });
    }
  }

  public recordMetric(metric: Omit<MetricRecord, 'id' | 'timestamp'> & { timestamp?: string }): MetricRecord {
    const record: MetricRecord = {
      id: this.idCounter++,
      session_id: metric.session_id,
      timestamp: metric.timestamp || new Date().toISOString(),
      intent: metric.intent || null,
      llm_model: metric.llm_model || null,
      tokens_used: metric.tokens_used,
      latency_ms: metric.latency_ms,
      used_fallback: metric.used_fallback,
      escalated: metric.escalated,
    };
    this.metrics.push(record);
    return record;
  }

  public getMetrics(days: number = 7): MetricRecord[] {
    const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
    return this.metrics
      .filter(m => new Date(m.timestamp).getTime() >= cutoff)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }

  public getSummary(days: number = 7) {
    const data = this.getMetrics(days);
    const total_messages = data.length;
    if (total_messages === 0) {
      return {
        total_messages: 0,
        total_tokens: 0,
        avg_latency: 0,
        escalations: 0,
        escalation_rate: 0,
        fallbacks: 0,
        fallback_rate: 0,
      };
    }

    const total_tokens = data.reduce((acc, curr) => acc + curr.tokens_used, 0);
    const avg_latency = Math.round(data.reduce((acc, curr) => acc + curr.latency_ms, 0) / total_messages);
    const escalations = data.filter(d => d.escalated).length;
    const escalation_rate = Number(((escalations / total_messages) * 100).toFixed(1));
    const fallbacks = data.filter(d => d.used_fallback).length;
    const fallback_rate = Number(((fallbacks / total_messages) * 100).toFixed(1));

    return {
      total_messages,
      total_tokens,
      avg_latency,
      escalations,
      escalation_rate,
      fallbacks,
      fallback_rate,
    };
  }

  public resetMetrics() {
    this.metrics = [];
    this.idCounter = 1;
    this.seedHistoricalMetrics();
  }
}

export const analyticsStore = new AnalyticsStore();
