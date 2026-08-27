import React from 'react';
import { Terminal, Shield, Code, Check } from 'lucide-react';

export const ApiDocs: React.FC = () => {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      
      {/* Overview */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
        <h2 className="text-base font-bold text-white mb-2 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-sky-400" />
          OmniRouter API & Webhook Specifications
        </h2>
        <p className="text-xs text-zinc-400 leading-relaxed">
          OmniRouter exposes production-ready endpoints for Meta WhatsApp Cloud API webhooks, human agent CCaaS systems, Prometheus monitoring, and health probes.
        </p>
      </div>

      {/* Endpoint 1: Meta Webhook GET /webhook */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded font-mono font-bold text-xs bg-emerald-500/20 text-emerald-400">
              GET
            </span>
            <span className="font-mono text-sm font-semibold text-white">/webhook</span>
          </div>
          <span className="text-xs text-zinc-400">Meta Webhook Verification</span>
        </div>
        <p className="text-xs text-zinc-400 mb-3">
          Handles Meta developer subscription verification challenge using <code className="text-zinc-200 font-mono">hub.verify_token</code>.
        </p>
        <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 font-mono text-xs text-zinc-300 overflow-x-auto">
          curl -X GET "https://your-domain.com/webhook?hub.mode=subscribe&hub.verify_token=omni_verify_token_secure_2025&hub.challenge=1158201244"
        </div>
      </div>

      {/* Endpoint 2: Meta Webhook POST /webhook */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded font-mono font-bold text-xs bg-sky-500/20 text-sky-400">
              POST
            </span>
            <span className="font-mono text-sm font-semibold text-white">/webhook</span>
          </div>
          <span className="text-xs text-zinc-400">Incoming WhatsApp Message Webhook</span>
        </div>
        <p className="text-xs text-zinc-400 mb-3">
          Receives WhatsApp Cloud API notifications, verifies HMAC-SHA256 signature in <code className="text-zinc-200 font-mono">X-Hub-Signature-256</code>, masks PII, applies escalation triggers, and executes autonomous AI response or CCaaS handoff.
        </p>
        <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 font-mono text-xs text-zinc-300 overflow-x-auto">
{`curl -X POST https://your-domain.com/webhook \\
  -H "Content-Type: application/json" \\
  -H "X-Hub-Signature-256: sha256=your_hmac_hex" \\
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messaging_product": "whatsapp",
          "metadata": { "phone_number_id": "109283746592819" },
          "messages": [{
            "from": "+14155552671",
            "id": "wamid.HBgLMTQxNTU1NTI2NzEVAgASGB",
            "timestamp": "1719239841",
            "type": "text",
            "text": { "body": "Where is my order #89421?" }
          }]
        }
      }]
    }]
  }'`}
        </div>
      </div>

      {/* Endpoint 3: Human Agent Webhook POST /agent/message */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded font-mono font-bold text-xs bg-amber-500/20 text-amber-400">
              POST
            </span>
            <span className="font-mono text-sm font-semibold text-white">/agent/message</span>
          </div>
          <span className="text-xs text-zinc-400">CCaaS Human Agent Reply & Close</span>
        </div>
        <p className="text-xs text-zinc-400 mb-3">
          Allows human agents to send replies back to the customer on WhatsApp (with markdown conversion) or close the conversation and initiate the CSAT survey.
        </p>
        <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 font-mono text-xs text-zinc-300 overflow-x-auto">
{`curl -X POST https://your-domain.com/agent/message \\
  -H "Authorization: Bearer default_agent_secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "session_id": "+14155552671",
    "agent_id": "Agent-07",
    "text": "Hello! I have reviewed your duplicate invoice and processed the refund.",
    "action": "reply"
  }'`}
        </div>
      </div>

      {/* Health & Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-2 font-mono text-xs text-white mb-2">
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">GET</span>
            <span>/health & /ready</span>
          </div>
          <p className="text-xs text-zinc-400">
            Kubernetes liveness and readiness probes checking Redis, Qdrant, and Database connectivity.
          </p>
        </div>

        <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-2 font-mono text-xs text-white mb-2">
            <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 font-bold">GET</span>
            <span>/metrics</span>
          </div>
          <p className="text-xs text-zinc-400">
            Prometheus text telemetry exporter tracking interaction counters, token volume, escalations, and average latency.
          </p>
        </div>
      </div>

    </div>
  );
};
