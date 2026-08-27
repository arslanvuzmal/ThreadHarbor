import React, { useState, useEffect } from 'react';
import { Headphones, Clock, User, CheckCircle, AlertCircle, RefreshCw, MessageSquare } from 'lucide-react';
import { ZendeskTicket, SessionData } from '../types';

export const TicketManager: React.FC = () => {
  const [tickets, setTickets] = useState<ZendeskTicket[]>([]);
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<ZendeskTicket | null>(null);
  const [selectedSession, setSelectedSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<'tickets' | 'sessions'>('tickets');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ticketsRes, sessionsRes] = await Promise.all([
        fetch('/api/tickets'),
        fetch('/api/sessions')
      ]);
      const ticketsData = await ticketsRes.json();
      const sessionsData = await sessionsRes.json();
      setTickets(ticketsData.tickets || []);
      setSessions(sessionsData.sessions || []);
    } catch (e) {
      console.error('Failed to load tickets/sessions', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      
      {/* Left Column: Tickets & Sessions List (5 Cols) */}
      <div className="lg:col-span-5 bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm flex flex-col h-[600px]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center bg-zinc-950 p-1 rounded-lg border border-zinc-800 text-xs">
            <button
              onClick={() => setTab('tickets')}
              className={`px-3 py-1 rounded-md font-semibold transition ${
                tab === 'tickets' ? 'bg-amber-500/20 text-amber-300' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              CCaaS Tickets ({tickets.length})
            </button>
            <button
              onClick={() => setTab('sessions')}
              className={`px-3 py-1 rounded-md font-semibold transition ${
                tab === 'sessions' ? 'bg-emerald-500/20 text-emerald-300' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Active Sessions ({sessions.length})
            </button>
          </div>

          <button
            onClick={fetchData}
            disabled={loading}
            className="p-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-400 hover:text-white"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Scrollable list */}
        <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
          {tab === 'tickets' ? (
            tickets.length === 0 ? (
              <div className="py-12 text-center text-zinc-500 text-xs">No CCaaS tickets open.</div>
            ) : (
              tickets.map((t) => (
                <div
                  key={t.ticket_id}
                  onClick={() => {
                    setSelectedTicket(t);
                    setSelectedSession(null);
                  }}
                  className={`p-3.5 rounded-xl border transition cursor-pointer ${
                    selectedTicket?.ticket_id === t.ticket_id
                      ? 'bg-amber-500/10 border-amber-500/50 shadow-sm'
                      : 'bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-mono font-bold text-xs text-amber-400">{t.ticket_id}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                        t.status === 'open'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      {t.status.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-zinc-200 truncate">{t.escalation_reason}</p>
                  <div className="flex items-center justify-between text-[11px] text-zinc-500 mt-2">
                    <span>{t.session_id}</span>
                    <span>{new Date(t.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>
              ))
            )
          ) : sessions.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 text-xs">No active sessions.</div>
          ) : (
            sessions.map((s) => (
              <div
                key={s.session_id}
                onClick={() => {
                  setSelectedSession(s);
                  setSelectedTicket(null);
                }}
                className={`p-3.5 rounded-xl border transition cursor-pointer ${
                  selectedSession?.session_id === s.session_id
                    ? 'bg-emerald-500/10 border-emerald-500/50 shadow-sm'
                    : 'bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-mono font-bold text-xs text-white">{s.session_id}</span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                      s.state === 'HUMAN_HANDOFF'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    }`}
                  >
                    {s.state}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 truncate">
                  {s.user_profile.name} ({s.user_profile.tier})
                </p>
                <div className="flex items-center justify-between text-[11px] text-zinc-500 mt-2">
                  <span>{s.transcript.length} turns</span>
                  <span className="text-emerald-400">24h Window: Active</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Column: Detailed Context Inspector (7 Cols) */}
      <div className="lg:col-span-7 bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm flex flex-col h-[600px] overflow-y-auto">
        {selectedTicket ? (
          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-amber-400 font-mono">{selectedTicket.ticket_id}</h3>
                <p className="text-zinc-400 text-xs">Escalated Handoff Context</p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                {selectedTicket.status.toUpperCase()}
              </span>
            </div>

            <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1.5">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Reason for Escalation</span>
              <p className="text-sm font-semibold text-white">{selectedTicket.escalation_reason}</p>
            </div>

            <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-1.5">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Automated LLM Summary</span>
              <p className="text-zinc-300 leading-relaxed">{selectedTicket.conversation_summary}</p>
            </div>

            <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold block mb-2">Transcript Logs</span>
              <div className="space-y-2 max-h-48 overflow-y-auto font-mono text-[11px]">
                {selectedTicket.messages.map((msg, idx) => (
                  <div key={idx} className="p-2 rounded bg-zinc-900 border border-zinc-800 text-zinc-200">
                    {msg}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : selectedSession ? (
          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white font-mono">{selectedSession.session_id}</h3>
                <p className="text-zinc-400 text-xs">Active WhatsApp Session State</p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                {selectedSession.state}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-500 uppercase block">Customer Name</span>
                <span className="font-bold text-white text-sm">{selectedSession.user_profile.name}</span>
              </div>
              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-500 uppercase block">Tier</span>
                <span className="font-bold text-emerald-400 text-sm uppercase">{selectedSession.user_profile.tier}</span>
              </div>
            </div>

            <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold block mb-2">Full Transcript Turns</span>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {selectedSession.transcript.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-lg border text-xs ${
                      msg.role === 'user'
                        ? 'bg-zinc-900 border-zinc-700 text-zinc-100'
                        : 'bg-emerald-950/40 border-emerald-800/40 text-emerald-200'
                    }`}
                  >
                    <span className="text-[10px] uppercase font-bold text-zinc-400 block mb-1">
                      {msg.role}
                    </span>
                    {msg.content}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-zinc-500 text-xs text-center p-6">
            <Headphones className="w-8 h-8 text-zinc-600 mb-2" />
            <p>Select any CCaaS Ticket or Active Session to view full transcripts and routing context payloads.</p>
          </div>
        )}
      </div>

    </div>
  );
};
