import React, { useState, useMemo } from 'react';
import { Search, Filter, AlertTriangle, CheckCircle, ShieldAlert, Cpu, Hash, Clock } from 'lucide-react';
import { InteractionMetric } from '../types';

interface RoutingLedgerProps {
  metrics: InteractionMetric[];
  onSelectSession?: (sessionId: string) => void;
}

export const RoutingLedger: React.FC<RoutingLedgerProps> = ({ metrics, onSelectSession }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterEscalated, setFilterEscalated] = useState<'all' | 'escalated' | 'autonomous'>('all');

  const filteredMetrics = useMemo(() => {
    return metrics.filter((m) => {
      const matchSearch =
        m.session_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (m.intent && m.intent.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (m.llm_model && m.llm_model.toLowerCase().includes(searchTerm.toLowerCase()));

      if (!matchSearch) return false;

      if (filterEscalated === 'escalated') return m.escalated;
      if (filterEscalated === 'autonomous') return !m.escalated;
      return true;
    });
  }, [metrics, searchTerm, filterEscalated]);

  return (
    <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
      
      {/* Table Header & Filters */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
        <div>
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            📋 Live Routing Ledger
            <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 font-mono font-normal">
              {filteredMetrics.length} Records
            </span>
          </h3>
          <p className="text-xs text-zinc-400">Complete immutable record of all incoming WhatsApp interactions and routing decisions</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search session ID or intent..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-zinc-950 border border-zinc-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50 w-52"
            />
          </div>

          {/* Filter Pill */}
          <div className="flex items-center bg-zinc-950 p-1 rounded-lg border border-zinc-800 text-xs">
            <button
              onClick={() => setFilterEscalated('all')}
              className={`px-2.5 py-1 rounded font-medium transition ${
                filterEscalated === 'all' ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilterEscalated('escalated')}
              className={`px-2.5 py-1 rounded font-medium transition ${
                filterEscalated === 'escalated' ? 'bg-amber-500/20 text-amber-300' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Escalated
            </button>
            <button
              onClick={() => setFilterEscalated('autonomous')}
              className={`px-2.5 py-1 rounded font-medium transition ${
                filterEscalated === 'autonomous' ? 'bg-emerald-500/20 text-emerald-300' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              AI Handled
            </button>
          </div>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto rounded-lg border border-zinc-800/80 max-h-[420px] overflow-y-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-zinc-950/80 text-zinc-400 sticky top-0 uppercase tracking-wider font-semibold border-b border-zinc-800 z-10">
            <tr>
              <th className="py-3 px-4">Timestamp</th>
              <th className="py-3 px-4">Session / Sender ID</th>
              <th className="py-3 px-4">Detected Intent</th>
              <th className="py-3 px-4">Engine / Model</th>
              <th className="py-3 px-4 text-right">Latency</th>
              <th className="py-3 px-4 text-center">Human Handoff</th>
              <th className="py-3 px-4 text-center">Fallback</th>
              <th className="py-3 px-4 text-right">Tokens</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50 bg-zinc-900/30">
            {filteredMetrics.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-zinc-500">
                  No matching telemetry records found.
                </td>
              </tr>
            ) : (
              filteredMetrics.map((item) => {
                const date = new Date(item.timestamp);
                const formattedTime = `${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;

                return (
                  <tr
                    key={item.id}
                    onClick={() => onSelectSession && onSelectSession(item.session_id)}
                    className="hover:bg-zinc-800/40 transition cursor-pointer group"
                  >
                    <td className="py-2.5 px-4 font-mono text-zinc-400 whitespace-nowrap">
                      {formattedTime}
                    </td>

                    <td className="py-2.5 px-4 font-mono font-medium text-zinc-200 whitespace-nowrap flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400/80" />
                      {item.session_id}
                    </td>

                    <td className="py-2.5 px-4 font-medium text-zinc-300 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded bg-zinc-800/80 text-zinc-200 border border-zinc-700/50 font-mono text-[11px]">
                        {item.intent || 'general_chat'}
                      </span>
                    </td>

                    <td className="py-2.5 px-4 text-zinc-400 whitespace-nowrap">
                      {item.llm_model ? (
                        <span className="flex items-center gap-1 font-mono text-[11px] text-purple-300">
                          <Cpu className="w-3 h-3" />
                          {item.llm_model}
                        </span>
                      ) : (
                        <span className="text-zinc-500 text-[11px]">Rule Engine</span>
                      )}
                    </td>

                    <td className="py-2.5 px-4 font-mono text-right text-zinc-300 whitespace-nowrap">
                      <span className={`${item.latency_ms > 500 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {item.latency_ms} ms
                      </span>
                    </td>

                    <td className="py-2.5 px-4 text-center whitespace-nowrap">
                      {item.escalated ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          <AlertTriangle className="w-3 h-3" />
                          Escalated
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          <CheckCircle className="w-3 h-3" />
                          Autonomous
                        </span>
                      )}
                    </td>

                    <td className="py-2.5 px-4 text-center whitespace-nowrap">
                      {item.used_fallback ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/30">
                          <ShieldAlert className="w-2.5 h-2.5" />
                          Fallback
                        </span>
                      ) : (
                        <span className="text-zinc-600 font-mono text-xs">-</span>
                      )}
                    </td>

                    <td className="py-2.5 px-4 font-mono text-right text-zinc-400 whitespace-nowrap">
                      {item.tokens_used > 0 ? item.tokens_used : '-'}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
};
