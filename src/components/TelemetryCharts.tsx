import React, { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  CartesianGrid,
  Legend,
} from 'recharts';
import { InteractionMetric } from '../types';

interface TelemetryChartsProps {
  metrics: InteractionMetric[];
}

const COLORS = [
  '#25D366', // WhatsApp Green
  '#128C7E', // WhatsApp Teal
  '#38bdf8', // Sky
  '#a855f7', // Purple
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#14b8a6', // Teal
  '#6366f1', // Indigo
];

export const TelemetryCharts: React.FC<TelemetryChartsProps> = ({ metrics }) => {
  // Process data for Spline Latency Area Chart (Chronological order)
  const latencyData = useMemo(() => {
    return [...metrics]
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .map((m) => {
        const d = new Date(m.timestamp);
        return {
          time: `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`,
          latency_ms: m.latency_ms,
          tokens: m.tokens_used,
          intent: m.intent || 'General',
          escalated: m.escalated,
        };
      });
  }, [metrics]);

  // Process data for Intent Donut Chart
  const intentData = useMemo(() => {
    const counts: Record<string, number> = {};
    metrics.forEach((m) => {
      const intentName = m.intent || 'General Inquiry';
      counts[intentName] = (counts[intentName] || 0) + 1;
    });

    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [metrics]);

  // Resolution distribution data
  const resolutionData = useMemo(() => {
    const aiResolved = metrics.filter((m) => !m.escalated && !m.used_fallback).length;
    const escalated = metrics.filter((m) => m.escalated).length;
    const fallbacks = metrics.filter((m) => m.used_fallback && !m.escalated).length;

    return [
      { category: 'AI Autonomous', count: aiResolved, color: '#25D366' },
      { category: 'Human Escalation', count: escalated, color: '#f59e0b' },
      { category: 'Rule Fallback', count: fallbacks, color: '#38bdf8' },
    ];
  }, [metrics]);

  if (metrics.length === 0) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-8 text-center text-zinc-400">
        No interaction telemetry data recorded in this time window.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      
      {/* Chart 1: Routing Latency Spline Area Chart (7 Cols) */}
      <div className="lg:col-span-7 bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">⚡ Routing Latency Over Time</h3>
            <p className="text-xs text-zinc-400">Response time in milliseconds across orchestrator turns</p>
          </div>
          <span className="text-xs px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
            Live Telemetry
          </span>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={latencyData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#25D366" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#25D366" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis dataKey="time" stroke="#71717a" fontSize={10} tickLine={false} />
              <YAxis stroke="#71717a" fontSize={10} tickLine={false} unit="ms" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#18181b',
                  borderColor: '#3f3f46',
                  borderRadius: '0.5rem',
                  fontSize: '12px',
                }}
                formatter={(value: any) => [`${value} ms`, 'Latency']}
              />
              <Area
                type="monotone"
                dataKey="latency_ms"
                stroke="#25D366"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#latencyGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Intent Breakdown Donut Chart (5 Cols) */}
      <div className="lg:col-span-5 bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">🎯 Detected Intent Distribution</h3>
            <p className="text-xs text-zinc-400">Classified triage intents & escalation triggers</p>
          </div>
          <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
            {intentData.length} Intents
          </span>
        </div>

        <div className="h-64 w-full relative">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={intentData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
              >
                {intentData.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#18181b',
                  borderColor: '#3f3f46',
                  borderRadius: '0.5rem',
                  fontSize: '12px',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          
          {/* Centered Donut Label */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-black text-white">{metrics.length}</span>
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider font-semibold">Events</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 justify-center max-h-16 overflow-y-auto pt-2">
          {intentData.slice(0, 5).map((item, idx) => (
            <div key={item.name} className="flex items-center gap-1.5 text-xs text-zinc-300">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
              <span className="truncate max-w-[120px]">{item.name}</span>
              <span className="text-zinc-500 font-mono">({item.value})</span>
            </div>
          ))}
        </div>
      </div>

      {/* Chart 3: Orchestrator Resolution Breakdown (Full Width) */}
      <div className="lg:col-span-12 bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">📊 Triage Resolution Breakdown</h3>
            <p className="text-xs text-zinc-400">Autonomous LLM completions vs CCaaS human handoffs vs fallback rule executions</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {resolutionData.map((item) => {
            const pct = metrics.length > 0 ? ((item.count / metrics.length) * 100).toFixed(1) : '0';
            return (
              <div key={item.category} className="bg-zinc-950/60 border border-zinc-800/80 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-zinc-400">{item.category}</span>
                  <div className="text-2xl font-bold text-white mt-1">{item.count.toLocaleString()}</div>
                </div>
                <div className="text-right">
                  <span className="text-sm font-mono font-bold" style={{ color: item.color }}>
                    {pct}%
                  </span>
                  <div className="w-16 h-1.5 bg-zinc-800 rounded-full mt-2 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${pct}%`, backgroundColor: item.color }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
};
