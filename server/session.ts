export interface SessionRecord {
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
}

class SessionStore {
  private sessions: Map<string, SessionRecord> = new Map();
  private processedMessages: Map<string, number> = new Map();

  constructor() {
    this.seedDefaultSessions();
  }

  private seedDefaultSessions() {
    const now = Date.now() / 1000;
    const session1: SessionRecord = {
      session_id: "+14155552671",
      state: "AWAITING_INPUT",
      user_profile: { name: "Alice Jenkins", phone: "+14155552671", tier: "platinum" },
      transcript: [
        { role: "user", content: "Hi, what are your business hours?", timestamp: new Date(Date.now() - 3600000).toISOString() },
        { role: "assistant", content: "Our support hours are 9 AM - 5 PM EST.", timestamp: new Date(Date.now() - 3595000).toISOString() }
      ],
      low_confidence_consecutive_count: 0,
      last_user_message: "Hi, what are your business hours?",
      ticket_id: null,
      phone_number_id: "109283746592819",
      last_interaction_timestamp: now - 3600
    };

    const session2: SessionRecord = {
      session_id: "+14155559823",
      state: "HUMAN_HANDOFF",
      user_profile: { name: "Carlos Rivera", phone: "+14155559823", tier: "standard" },
      transcript: [
        { role: "user", content: "I was charged twice on my credit card. I demand a refund of $650!", timestamp: new Date(Date.now() - 1800000).toISOString() },
        { role: "assistant", content: "I'm connecting you to a human specialist. Please hold.", timestamp: new Date(Date.now() - 1795000).toISOString() }
      ],
      low_confidence_consecutive_count: 0,
      last_user_message: "I was charged twice on my credit card. I demand a refund of $650!",
      ticket_id: "ZENDESK-104",
      phone_number_id: "109283746592819",
      last_interaction_timestamp: now - 1800
    };

    this.sessions.set(session1.session_id, session1);
    this.sessions.set(session2.session_id, session2);
  }

  public getSession(sessionId: string): SessionRecord {
    let session = this.sessions.get(sessionId);
    if (!session) {
      session = {
        session_id: sessionId,
        state: 'AWAITING_INPUT',
        user_profile: {
          name: 'WhatsApp Customer',
          phone: sessionId,
          tier: 'standard',
        },
        transcript: [],
        low_confidence_consecutive_count: 0,
        last_user_message: null,
        ticket_id: null,
        phone_number_id: null,
        last_interaction_timestamp: Date.now() / 1000,
      };
      this.sessions.set(sessionId, session);
    }
    return session;
  }

  public saveSession(session: SessionRecord): void {
    this.sessions.set(session.session_id, { ...session });
  }

  public getAllSessions(): SessionRecord[] {
    return Array.from(this.sessions.values()).map(s => ({
      ...s,
      is_within_24h_window: this.isWithin24hWindow(s.session_id)
    }));
  }

  public isWithin24hWindow(sessionId: string): boolean {
    const session = this.sessions.get(sessionId);
    if (!session || !session.last_interaction_timestamp) return true;
    const now = Date.now() / 1000;
    return (now - session.last_interaction_timestamp) < 86400;
  }

  public checkMessageIdempotency(messageId: string): boolean {
    const now = Date.now() / 1000;
    if (this.processedMessages.has(messageId)) {
      return true; // Duplicate
    }
    this.processedMessages.set(messageId, now);

    // Clean entries older than 1 hour
    const cutoff = now - 3600;
    for (const [id, ts] of this.processedMessages.entries()) {
      if (ts < cutoff) {
        this.processedMessages.delete(id);
      }
    }
    return false;
  }
}

export const sessionStore = new SessionStore();
