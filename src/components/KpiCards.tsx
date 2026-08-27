import React from 'react';
import { Zap, Clock, Brain, Users, ShieldAlert } from 'lucide-react';
import { KpiSummary } from '../types';

interface KpiCardsProps {
  summary: KpiSummary;
}

export const KpiCards: React.FC<KpiCardsProps> = ({ summary }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      
      {/* KPI 1: Total Interactions */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 hover:border-emerald-500/40 transition-all group shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Total Interactions</span>
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
            <Zap className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-white tracking-tight">
            {summary.total_messages.toLocaleString()}
          </span>
          <span className="text-xs text-emerald-400 font-medium">100% routed</span>
        </div>
        <p className="text-xs text-zinc-500 mt-1">Processed across WhatsApp webhooks</p>
      </div>

      {/* KPI 2: Avg Routing Latency */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 hover:border-emerald-500/40 transition-all group shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Avg Routing Latency</span>
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 group-hover:scale-105 transition-transform">
            <Clock className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-white tracking-tight">
            {summary.avg_latency.toLocaleString()}
            <span className="text-lg font-normal text-zinc-400 ml-1">ms</span>
          </span>
          <span className="text-xs text-sky-400 font-medium">Sub-second</span>
        </div>
        <p className="text-xs text-zinc-500 mt-1">Triage, masking & LLM response time</p>
      </div>

      {/* KPI 3: Total LLM Tokens */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 hover:border-emerald-500/40 transition-all group shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Total LLM Tokens</span>
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 group-hover:scale-105 transition-transform">
            <Brain className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-white tracking-tight">
            {summary.total_tokens.toLocaleString()}
          </span>
          <span className="text-xs text-purple-400 font-medium">GPT-4o / Mini</span>
        </div>
        <p className="text-xs text-zinc-500 mt-1">Prompt & completion inference volume</p>
      </div>

      {/* KPI 4: Human Handoff Rate */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 hover:border-amber-500/40 transition-all group shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Human Handoff Rate</span>
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 group-hover:scale-105 transition-transform">
            <Users className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-white tracking-tight">
            {summary.escalation_rate}%
          </span>
          <span className={`text-xs font-medium ${summary.escalations > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
            {summary.escalations} escalated sessions
          </span>
        </div>
        <p className="text-xs text-zinc-500 mt-1">Triggered by intent, sentiment or policy</p>
      </div>

    </div>
  );
};
