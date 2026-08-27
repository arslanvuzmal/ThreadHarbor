import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { KpiCards } from './components/KpiCards';
import { TelemetryCharts } from './components/TelemetryCharts';
import { RoutingLedger } from './components/RoutingLedger';
import { WhatsAppSimulator } from './components/WhatsAppSimulator';
import { TicketManager } from './components/TicketManager';
import { ApiDocs } from './components/ApiDocs';
import { KpiSummary, InteractionMetric, SessionData } from './types';
import { X, CheckCircle, ShieldCheck, Clock, User } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'simulator' | 'tickets' | 'docs'>('dashboard');
  const [days, setDays] = useState<number>(7);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  
  const [summary, setSummary] = useState<KpiSummary>({
    total_messages: 0,
    total_tokens: 0,
    avg_latency: 0,
    escalations: 0,
    escalation_rate: 0,
    fallbacks: 0,
    fallback_rate: 0,
  });

  const [metrics, setMetrics] = useState<InteractionMetric[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [inspectingSession, setInspectingSession] = useState<SessionData | null>(null);

  const fetchMetrics = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch(`/api/metrics?days=${days}`);
      if (res.ok) {
        const data = await res.json();
        setSummary(data.summary);
        setMetrics(data.metrics);
      }
    } catch (e) {
      console.error('Failed to fetch telemetry metrics', e);
    } finally {
      setIsRefreshing(false);
    }
  }, [days]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // 5s Auto-refresh polling (matches Streamlit dashboard behavior)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchMetrics();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchMetrics]);

  const handleReset = async () => {
    try {
      await fetch('/api/simulate/reset', { method: 'POST' });
      fetchMetrics();
    } catch (e) {
      console.error('Failed to reset metrics', e);
    }
  };

  const inspectSession = async (sessionId: string) => {
    setSelectedSessionId(sessionId);
    try {
      const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
      if (res.ok) {
        const data = await res.json();
        setInspectingSession(data);
      }
    } catch (e) {
      console.error('Failed to fetch session', e);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col selection:bg-emerald-500/30 selection:text-emerald-200">
      
      {/* Top App Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        autoRefresh={autoRefresh}
        setAutoRefresh={setAutoRefresh}
        days={days}
        setDays={setDays}
        onRefresh={fetchMetrics}
        onReset={handleReset}
        isRefreshing={isRefreshing}
      />

      {/* Main Content Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-6 space-y-6">
        
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* KPI Cards Row */}
            <KpiCards summary={summary} />

            {/* Interactive Telemetry & Spline Charts */}
            <TelemetryCharts metrics={metrics} />

            {/* Live Routing Ledger */}
            <RoutingLedger metrics={metrics} onSelectSession={inspectSession} />
          </div>
        )}

        {activeTab === 'simulator' && (
          <WhatsAppSimulator onInteractionComplete={fetchMetrics} />
        )}

        {activeTab === 'tickets' && (
          <TicketManager />
        )}

        {activeTab === 'docs' && (
          <ApiDocs />
        )}

      </main>

      {/* Session Inspector Modal */}
      {selectedSessionId && inspectingSession && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            
            {/* Modal Header */}
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-950/60">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-emerald-400 text-sm">{inspectingSession.session_id}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    inspectingSession.state === 'HUMAN_HANDOFF'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  }`}>
                    {inspectingSession.state}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-0.5">{inspectingSession.user_profile.name} • {inspectingSession.user_profile.tier} tier</p>
              </div>

              <button
                onClick={() => {
                  setSelectedSessionId(null);
                  setInspectingSession(null);
                }}
                className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 flex-1 overflow-y-auto space-y-4 text-xs">
              
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                  <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Ticket ID</span>
                  <span className="font-mono text-white">{inspectingSession.ticket_id || 'None (Autonomous)'}</span>
                </div>

                <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                  <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Meta 24h Window</span>
                  <span className="text-emerald-400 font-semibold">Active & Compliant</span>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-2">Session Transcript</h4>
                <div className="space-y-2 bg-zinc-950 p-3 rounded-lg border border-zinc-800 max-h-72 overflow-y-auto">
                  {inspectingSession.transcript.length === 0 ? (
                    <div className="text-zinc-500 py-4 text-center">No transcript history.</div>
                  ) : (
                    inspectingSession.transcript.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`p-2.5 rounded-lg border ${
                          msg.role === 'user'
                            ? 'bg-zinc-900 border-zinc-800 text-zinc-200'
                            : 'bg-emerald-950/30 border-emerald-900/40 text-emerald-200'
                        }`}
                      >
                        <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 block mb-1">
                          {msg.role}
                        </span>
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

            </div>

            {/* Modal Footer */}
            <div className="p-3 border-t border-zinc-800 bg-zinc-950/80 text-right">
              <button
                onClick={() => {
                  setSelectedSessionId(null);
                  setInspectingSession(null);
                }}
                className="px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-semibold text-xs transition"
              >
                Close Inspector
              </button>
            </div>

          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-zinc-900 py-4 text-center text-xs text-zinc-500">
        OmniRouter • Highly Scalable WhatsApp Orchestrator & Support Engine • Node.js Runtime
      </footer>

    </div>
  );
}

export default App;
