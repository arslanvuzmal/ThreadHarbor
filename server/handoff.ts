import { logger } from './logger';
import { SessionRecord } from './session';

export interface ZendeskTicketRecord {
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

class MockZendeskHandoffClient {
  private tickets: Map<string, ZendeskTicketRecord> = new Map();
  private ticketCounter = 101;

  constructor() {
    this.seedDefaultTickets();
  }

  private seedDefaultTickets() {
    const ticket1: ZendeskTicketRecord = {
      ticket_id: 'ZENDESK-104',
      session_id: '+14155559823',
      status: 'open',
      escalation_reason: 'Policy Limit (Refund > $500)',
      conversation_summary: 'Customer Carlos Rivera requested an unauthorized refund of $650 for duplicate charges.',
      created_at: new Date(Date.now() - 1800000).toISOString(),
      updated_at: new Date(Date.now() - 1800000).toISOString(),
      messages: ['I was charged twice on my credit card. I demand a refund of $650!'],
      user_profile: { name: 'Carlos Rivera', phone: '+14155559823', tier: 'standard' }
    };
    this.tickets.set(ticket1.ticket_id, ticket1);
  }

  public async createTicket(session: SessionRecord, reason: string): Promise<string> {
    const ticketId = `ZENDESK-${this.ticketCounter++}`;
    const summary = this.generateSummary(session.transcript, reason);
    const nowIso = new Date().toISOString();

    const ticket: ZendeskTicketRecord = {
      ticket_id: ticketId,
      session_id: session.session_id,
      status: 'open',
      escalation_reason: reason,
      conversation_summary: summary,
      created_at: nowIso,
      updated_at: nowIso,
      messages: session.transcript.map(m => `[${m.role.toUpperCase()}] ${m.content}`),
      user_profile: { ...session.user_profile },
    };

    this.tickets.set(ticketId, ticket);
    logger.info('Mock Zendesk ticket created successfully', {
      ticketId,
      sessionId: session.session_id,
      reason,
    });
    return ticketId;
  }

  public async sendAgentMessage(ticketId: string, text: string): Promise<void> {
    const ticket = this.tickets.get(ticketId);
    if (!ticket) {
      throw new Error(`Ticket ${ticketId} does not exist`);
    }
    ticket.messages.push(`[USER] ${text}`);
    ticket.updated_at = new Date().toISOString();
    logger.info('Mock Zendesk ticket updated with user message', { ticketId });
  }

  public async closeTicket(ticketId: string): Promise<void> {
    const ticket = this.tickets.get(ticketId);
    if (!ticket) {
      throw new Error(`Ticket ${ticketId} does not exist`);
    }
    ticket.status = 'closed';
    ticket.updated_at = new Date().toISOString();
    logger.info('Mock Zendesk ticket closed successfully', { ticketId });
  }

  public getAllTickets(): ZendeskTicketRecord[] {
    return Array.from(this.tickets.values()).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }

  public getTicket(ticketId: string): ZendeskTicketRecord | undefined {
    return this.tickets.get(ticketId);
  }

  private generateSummary(transcript: Array<{ role: string; content: string }>, reason: string): string {
    const lastMsg = transcript.slice(-3).map(m => m.content).join('; ');
    return `Customer escalated due to: ${reason}. Recent context: "${lastMsg.slice(0, 150)}..."`;
  }
}

export const handoffClient = new MockZendeskHandoffClient();
