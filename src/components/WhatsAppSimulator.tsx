import React, { useState } from 'react';
import { Send, ShieldCheck, Zap, AlertTriangle, UserCheck, Bot, FileText, RefreshCcw, Check, Sparkles } from 'lucide-react';
import { SimulationResult, SessionData } from '../types';

interface WhatsAppSimulatorProps {
  onInteractionComplete?: () => void;
}

export const WhatsAppSimulator: React.FC<WhatsAppSimulatorProps> = ({ onInteractionComplete }) => {
  const [phoneNumber, setPhoneNumber] = useState('+14155552671');
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant' | 'system'; text: string; time: string }>>([
    { role: 'assistant', text: 'Hi! Welcome to OmniRouter WhatsApp Support. How can we help you today?', time: '10:00 AM' }
  ]);
  const [lastResult, setLastResult] = useState<SimulationResult | null>(null);
  const [agentReplyText, setAgentReplyText] = useState('');
  const [agentLoading, setAgentLoading] = useState(false);

  const presets = [
    { label: '👋 General Hours', text: 'Hi, what are your business hours and location?' },
    { label: '📦 Track Order', text: 'Where is my order #89421?' },
    { label: '🛡️ PII Masking Test', text: 'My email is john.doe@acme.com and my card is 4532-1188-9922-3344. Phone: +1-415-555-0199.' },
    { label: '⚠️ Explicit Agent Handoff', text: 'I want to speak with a human agent representative right now.' },
    { label: '🚨 Refund > $500 (Policy)', text: 'I was overcharged $650.00 on my invoice and need a full refund.' },
    { label: '🤬 Negative Sentiment', text: 'This service is completely unacceptable, terrible and a scam!' },
    { label: '🔁 Loop Trigger (Repeat)', text: 'Can you help me with my account password reset?' },
    { label: '💥 System Failure Degradation', text: 'force error simulation check' },
  ];

  const handleSendMessage = async (customText?: string) => {
    const textToSend = customText !== undefined ? customText : messageText;
    if (!textToSend.trim() || loading) return;

    const timeStr = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { role: 'user', text: textToSend, time: timeStr }]);
    if (customText === undefined) setMessageText('');
    setLoading(true);

    try {
      const res = await fetch('/api/simulate/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: phoneNumber,
          message: textToSend,
        }),
      });
      const data: SimulationResult = await res.json();
      setLastResult(data);

      if (data.reply_text) {
        setMessages(prev => [
          ...prev,
          { role: 'assistant', text: data.reply_text, time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) }
        ]);
      } else if (data.state === 'HUMAN_HANDOFF') {
        setMessages(prev => [
          ...prev,
          { role: 'system', text: '🔒 Session in Silent Mode: Routed to Human Agent Desk.', time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) }
        ]);
      }

      if (onInteractionComplete) onInteractionComplete();
    } catch (e) {
      console.error('Failed to send simulator message', e);
    } finally {
      setLoading(false);
    }
  };

  const handleAgentAction = async (action: 'reply' | 'close') => {
    if (action === 'reply' && !agentReplyText.trim()) return;
    setAgentLoading(true);

    try {
      const res = await fetch('/api/simulate/agent-reply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: phoneNumber,
          agent_id: 'Agent-42',
          text: agentReplyText,
          action,
        }),
      });
      const data = await res.json();
      if (data.session) {
        const timeStr = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        if (action === 'reply') {
          setMessages(prev => [...prev, { role: 'assistant', text: `👤 [Agent]: ${agentReplyText}`, time: timeStr }]);
          setAgentReplyText('');
        } else {
          setMessages(prev => [
            ...prev,
            { role: 'assistant', text: 'The chat has been closed. How would you rate your experience? [1-5 ⭐]', time: timeStr }
          ]);
        }
        if (lastResult) {
          setLastResult({ ...lastResult, session: data.session, state: data.session.state });
        }
      }
      if (onInteractionComplete) onInteractionComplete();
    } catch (e) {
      console.error('Agent action error', e);
    } finally {
      setAgentLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      
      {/* Left Column: Preset Test Buttons & Interactive Phone Simulator (7 Cols) */}
      <div className="lg:col-span-7 flex flex-col gap-4">
        
        {/* Scenario Presets */}
        <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2.5">
            <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
              Quick Trigger Test Scenarios
            </span>
            <span className="text-[11px] text-zinc-400">Click any preset to simulate instantly</span>
          </div>
          
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {presets.map((p, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setMessageText(p.text);
                  handleSendMessage(p.text);
                }}
                disabled={loading}
                className="text-left p-2 rounded-lg bg-zinc-950/80 hover:bg-zinc-800 border border-zinc-800 hover:border-emerald-500/40 transition text-xs text-zinc-300 font-medium disabled:opacity-50"
              >
                <div className="truncate text-white font-semibold">{p.label}</div>
                <div className="text-[10px] text-zinc-500 truncate mt-0.5">{p.text}</div>
              </button>
            ))}
          </div>
        </div>

        {/* WhatsApp Mobile Mockup */}
        <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col h-[520px]">
          
          {/* WhatsApp Header Bar */}
          <div className="bg-[#075E54] text-white px-4 py-3 flex items-center justify-between shadow">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-[#128C7E] flex items-center justify-center font-bold text-sm text-white">
                OR
              </div>
              <div>
                <h4 className="text-sm font-bold leading-tight">OmniRouter Support</h4>
                <p className="text-[11px] text-emerald-100 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse" />
                  {lastResult?.state === 'HUMAN_HANDOFF' ? 'Human Specialist Connected' : 'AI Assistant Online'}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="bg-black/20 text-xs font-mono px-2.5 py-1 rounded border border-white/20 text-white focus:outline-none w-32"
                title="Simulated Sender WhatsApp ID"
              />
            </div>
          </div>

          {/* WhatsApp Chat Transcript Area */}
          <div className="flex-1 bg-[#0b141a] p-4 overflow-y-auto space-y-3 flex flex-col">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${
                  m.role === 'user'
                    ? 'items-end'
                    : m.role === 'system'
                    ? 'items-center'
                    : 'items-start'
                }`}
              >
                {m.role === 'system' ? (
                  <div className="px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] font-medium my-1">
                    {m.text}
                  </div>
                ) : (
                  <div
                    className={`max-w-[80%] rounded-xl px-3.5 py-2 text-xs relative shadow ${
                      m.role === 'user'
                        ? 'bg-[#005c4b] text-white rounded-tr-none'
                        : 'bg-[#202c33] text-zinc-100 rounded-tl-none border border-zinc-700/40'
                    }`}
                  >
                    <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
                    <div className="text-[9px] text-zinc-400 text-right mt-1 font-mono">
                      {m.time}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-2 text-xs text-zinc-400 bg-[#202c33] px-3 py-2 rounded-xl w-32">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-bounce" />
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-bounce [animation-delay:0.2s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-bounce [animation-delay:0.4s]" />
                <span>typing...</span>
              </div>
            )}
          </div>

          {/* WhatsApp Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="p-3 bg-[#202c33] border-t border-zinc-800 flex items-center gap-2"
          >
            <input
              type="text"
              placeholder="Type a WhatsApp message..."
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              className="flex-1 bg-[#2a3942] text-zinc-100 placeholder-zinc-400 text-xs px-3.5 py-2.5 rounded-lg border border-zinc-700/50 focus:outline-none focus:border-emerald-500"
            />
            <button
              type="submit"
              disabled={loading || !messageText.trim()}
              className="w-9 h-9 rounded-lg bg-[#00a884] hover:bg-[#029070] text-white flex items-center justify-center transition disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>

        </div>
      </div>

      {/* Right Column: Live Orchestrator & Human Desk Inspector (5 Cols) */}
      <div className="lg:col-span-5 flex flex-col gap-4">
        
        {/* Real-time Triage Telemetry Inspector */}
        <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-sky-400" />
              Triage & Masking Inspector
            </h3>
            {lastResult?.escalated && (
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                Escalated to Agent
              </span>
            )}
          </div>

          {lastResult ? (
            <div className="space-y-3 text-xs">
              
              {/* Zero-Trust PII Masked Log */}
              <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  Zero-Trust PII Masking Output
                </span>
                <p className="font-mono text-emerald-300 mt-1 bg-zinc-900/80 p-1.5 rounded border border-emerald-500/20 break-words">
                  {lastResult.masked_input}
                </p>
              </div>

              {/* Triage Decision Grid */}
              <div className="grid grid-cols-2 gap-2 font-mono">
                <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                  <span className="text-[10px] text-zinc-500 uppercase block">Detected Intent</span>
                  <span className="text-white font-bold">{lastResult.intent || 'General'}</span>
                </div>

                <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                  <span className="text-[10px] text-zinc-500 uppercase block">Session State</span>
                  <span className={`font-bold ${lastResult.state === 'HUMAN_HANDOFF' ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {lastResult.state}
                  </span>
                </div>

                <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                  <span className="text-[10px] text-zinc-500 uppercase block">Processing Latency</span>
                  <span className="text-sky-300 font-bold">{lastResult.latency_ms} ms</span>
                </div>

                <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                  <span className="text-[10px] text-zinc-500 uppercase block">LLM Engine</span>
                  <span className="text-purple-300 font-bold">{lastResult.llm_model || 'Rule Engine'}</span>
                </div>
              </div>

              {lastResult.ticket_id && (
                <div className="bg-amber-500/10 border border-amber-500/30 p-3 rounded-lg">
                  <span className="text-xs font-bold text-amber-300 block">
                    🎫 CCaaS Ticket Generated: {lastResult.ticket_id}
                  </span>
                  <p className="text-[11px] text-amber-200/80 mt-0.5">
                    Context payload dispatches session transcript, PII masked summary, and escalation reason to Zendesk.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="py-12 text-center text-zinc-500 text-xs">
              Send or trigger any test message to view live real-time orchestrator decisions, PII masking, and latency metrics.
            </div>
          )}
        </div>

        {/* Live Human Agent Desk (When session escalated) */}
        <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <UserCheck className="w-3.5 h-3.5 text-amber-400" />
              Human Agent Desk (CCaaS Gateway)
            </h3>
            <span className="text-[10px] font-mono text-zinc-400">
              POST /agent/message
            </span>
          </div>

          <p className="text-xs text-zinc-400 mb-3">
            Human agents receive escalated sessions, view context, and reply back to the user via WhatsApp Graph API.
          </p>

          <div className="space-y-2">
            <textarea
              rows={3}
              placeholder="Type human specialist response (Markdown supported: **bold** -> *bold*)..."
              value={agentReplyText}
              onChange={(e) => setAgentReplyText(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-amber-500/50 resize-none"
            />

            <div className="flex items-center gap-2">
              <button
                onClick={() => handleAgentAction('reply')}
                disabled={agentLoading || !agentReplyText.trim()}
                className="flex-1 py-2 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 rounded-lg text-xs font-semibold transition disabled:opacity-50"
              >
                {agentLoading ? 'Sending...' : 'Dispatch Agent Reply'}
              </button>

              <button
                onClick={() => handleAgentAction('close')}
                disabled={agentLoading}
                className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 rounded-lg text-xs font-semibold transition disabled:opacity-50"
              >
                Close & Trigger CSAT
              </button>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
};
