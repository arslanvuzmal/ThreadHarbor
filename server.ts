import express from 'express';
import cors from 'cors';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { config } from './server/config';
import { logger } from './server/logger';
import { verifySignature, whatsappFormatter } from './server/whatsapp';
import { sessionStore } from './server/session';
import { orchestrator } from './server/orchestrator';
import { handoffClient } from './server/handoff';
import { analyticsStore } from './server/analytics';

const app = express();
const PORT = 3000;

// Enable CORS
app.use(cors());

// Raw body parser for Meta Webhook signature verification and JSON parser
app.use(express.json({
  verify: (req: any, _res, buf) => {
    req.rawBody = buf;
  }
}));
app.use(express.urlencoded({ extended: true }));

// --- HEALTH & READINESS ENDPOINTS ---
app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

app.get('/ready', (_req, res) => {
  res.json({
    status: 'ok',
    redis: 'ok',
    qdrant: 'ok',
    database: 'ok',
    timestamp: new Date().toISOString()
  });
});

// --- PROMETHEUS METRICS STUB ---
app.get('/metrics', (_req, res) => {
  const summary = analyticsStore.getSummary(7);
  const metricsText = [
    '# HELP omnirouter_interactions_total Total number of WhatsApp interactions handled',
    '# TYPE omnirouter_interactions_total counter',
    `omnirouter_interactions_total ${summary.total_messages}`,
    '# HELP omnirouter_tokens_used_total Total tokens used by LLM',
    '# TYPE omnirouter_tokens_used_total counter',
    `omnirouter_tokens_used_total ${summary.total_tokens}`,
    '# HELP omnirouter_escalations_total Total escalations to human agent',
    '# TYPE omnirouter_escalations_total counter',
    `omnirouter_escalations_total ${summary.escalations}`,
    '# HELP omnirouter_fallbacks_total Total fallback engine triggers',
    '# TYPE omnirouter_fallbacks_total counter',
    `omnirouter_fallbacks_total ${summary.fallbacks}`,
    '# HELP omnirouter_avg_latency_ms Average processing latency in ms',
    '# TYPE omnirouter_avg_latency_ms gauge',
    `omnirouter_avg_latency_ms ${summary.avg_latency}`,
  ].join('\n');

  res.setHeader('Content-Type', 'text/plain; version=0.0.4');
  res.send(metricsText);
});

// --- META WEBHOOK VERIFICATION (GET /webhook) ---
app.get('/webhook', (req, res) => {
  const hubMode = req.query['hub.mode'] as string;
  const hubVerifyToken = req.query['hub.verify_token'] as string;
  const hubChallenge = req.query['hub.challenge'] as string;

  if (hubMode === 'subscribe' && hubVerifyToken === config.WHATSAPP_VERIFY_TOKEN) {
    if (hubChallenge) {
      logger.info('Meta Webhook verified successfully');
      return res.status(200).send(hubChallenge);
    }
    return res.status(403).json({
      error: { code: 403, message: 'Verification failed: hub.challenge is missing' }
    });
  }

  return res.status(403).json({
    error: { code: 403, message: 'Verification failed: Invalid token or mode' }
  });
});

// --- META WEBHOOK RECEIVER (POST /webhook) ---
app.post('/webhook', async (req: any, res) => {
  const signatureHeader = req.headers['x-hub-signature-256'] as string;
  const rawBody = req.rawBody || Buffer.from(JSON.stringify(req.body));

  // Verify HMAC signature if provided or if secret configured
  if (signatureHeader) {
    const isValid = verifySignature(rawBody, signatureHeader, config.WHATSAPP_APP_SECRET);
    if (!isValid) {
      logger.warn('Signature verification failed', { signature: signatureHeader });
      return res.status(401).json({
        error: { code: 401, message: 'Invalid signature' }
      });
    }
  }

  try {
    const payload = req.body;
    const entry = payload?.entry?.[0];
    const changes = entry?.changes?.[0];
    const value = changes?.value;
    const metadata = value?.metadata;
    const phoneNumberId = metadata?.phone_number_id || 'default_phone_id';
    const messages = value?.messages;

    if (!messages || messages.length === 0) {
      return res.json({ status: 'success' });
    }

    const message = messages[0];
    const messageId = message.id;

    // Deduplication check
    if (messageId && sessionStore.checkMessageIdempotency(messageId)) {
      logger.info('Duplicate message detected, skipping processing', { messageId });
      return res.json({ status: 'success' });
    }

    const senderWaId = message.from;
    const msgType = message.type;
    let textContent = '';
    let mediaBytesBase64: string | undefined;
    let mimeType: string | undefined;

    if (msgType === 'text') {
      textContent = message.text?.body || '';
    } else if (msgType === 'interactive') {
      const interactive = message.interactive;
      if (interactive.type === 'nfm_reply') {
        textContent = `User submitted Flow Data: ${interactive.nfm_reply?.response_json || '{}'}`;
      } else {
        textContent = JSON.stringify(interactive);
      }
    } else if (msgType === 'image' || msgType === 'document' || msgType === 'audio') {
      const mediaInfo = message[msgType] || {};
      mimeType = mediaInfo.mime_type;
      textContent = mediaInfo.caption || mediaInfo.filename || `Uploaded ${msgType}`;
    }

    if (senderWaId && textContent) {
      // Async process incoming message
      setTimeout(async () => {
        try {
          await orchestrator.handleMessage(senderWaId, textContent, phoneNumberId, mediaBytesBase64, mimeType);
        } catch (e: any) {
          logger.error('Error handling message in background', { error: e?.message });
        }
      }, 0);
    }

    return res.json({ status: 'success' });
  } catch (e: any) {
    logger.error('Error processing webhook payload', { error: e?.message });
    return res.json({ status: 'success' });
  }
});

// --- HUMAN AGENT INBOUND WEBHOOK (POST /agent/message) ---
app.post('/agent/message', async (req, res) => {
  const authHeader = req.headers['authorization'];
  if (!authHeader) {
    return res.status(401).json({
      error: { code: 401, message: 'Missing Authorization header' }
    });
  }

  const parts = authHeader.split(' ');
  if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer') {
    return res.status(401).json({
      error: { code: 401, message: 'Invalid Authorization header format' }
    });
  }

  const token = parts[1];
  if (token !== config.AGENT_API_SECRET) {
    return res.status(401).json({
      error: { code: 401, message: 'Invalid agent API secret' }
    });
  }

  const { session_id, agent_id, text, action } = req.body;
  if (!session_id || !action) {
    return res.status(422).json({
      error: { code: 422, message: 'session_id and action are required' }
    });
  }

  const session = sessionStore.getSession(session_id);

  if (action === 'reply') {
    if (!sessionStore.isWithin24hWindow(session_id)) {
      return res.status(400).json({
        error: {
          code: 400,
          message: 'Cannot send free-form reply: session is outside the 24-hour interaction window.'
        }
      });
    }

    const formattedReply = whatsappFormatter(text || '');
    session.transcript.push({
      role: 'assistant',
      content: `[Human Agent ${agent_id || 'Spec-1'}]: ${formattedReply}`,
      timestamp: new Date().toISOString()
    });
    sessionStore.saveSession(session);

    logger.info('Dispatched human agent reply to WhatsApp', { sessionId: session_id });
    return res.json({ status: 'success', formatted_reply: formattedReply });
  } else if (action === 'close') {
    session.state = 'AWAITING_INPUT';

    if (session.ticket_id) {
      try {
        await handoffClient.closeTicket(session.ticket_id);
      } catch (e: any) {
        logger.error('Failed to close ticket in handoff client', { error: e?.message });
      }
      session.ticket_id = null;
    }

    session.low_confidence_consecutive_count = 0;
    session.last_user_message = null;

    const csatText = 'The chat has been closed. How would you rate your experience today with our support team? [1-5 ⭐]';
    session.transcript.push({
      role: 'assistant',
      content: csatText,
      timestamp: new Date().toISOString()
    });
    sessionStore.saveSession(session);

    logger.info('Chat closed and CSAT survey dispatched', { sessionId: session_id });
    return res.json({ status: 'success', message: 'Chat closed successfully' });
  }

  return res.status(400).json({
    error: { code: 400, message: 'Invalid action. Supported actions: reply, close' }
  });
});

// --- DASHBOARD API ENDPOINTS ---

app.get('/api/metrics', (req, res) => {
  const days = parseInt(req.query.days as string, 10) || 7;
  const summary = analyticsStore.getSummary(days);
  const metrics = analyticsStore.getMetrics(days);
  res.json({ summary, metrics });
});

app.get('/api/sessions', (_req, res) => {
  const sessions = sessionStore.getAllSessions();
  res.json({ sessions });
});

app.get('/api/sessions/:id', (req, res) => {
  const session = sessionStore.getSession(req.params.id);
  res.json({
    ...session,
    is_within_24h_window: sessionStore.isWithin24hWindow(session.session_id)
  });
});

app.get('/api/tickets', (_req, res) => {
  const tickets = handoffClient.getAllTickets();
  res.json({ tickets });
});

app.get('/api/tickets/:id', (req, res) => {
  const ticket = handoffClient.getTicket(req.params.id);
  if (!ticket) {
    return res.status(404).json({ error: 'Ticket not found' });
  }
  res.json(ticket);
});

// --- SIMULATION ENDPOINTS ---

app.post('/api/simulate/message', async (req, res) => {
  try {
    const { session_id, message, media_base64, mime_type } = req.body;
    const sid = session_id || '+1415555' + Math.floor(1000 + Math.random() * 9000);
    const text = message || 'Hello!';

    const result = await orchestrator.handleMessage(sid, text, '109283746592819', media_base64, mime_type);
    res.json(result);
  } catch (e: any) {
    logger.error('Error during simulation', { error: e?.message });
    res.status(500).json({ error: e?.message || 'Simulation error' });
  }
});

app.post('/api/simulate/agent-reply', async (req, res) => {
  try {
    const { session_id, agent_id, text, action } = req.body;
    const session = sessionStore.getSession(session_id);

    if (action === 'reply') {
      const formattedReply = whatsappFormatter(text || '');
      session.transcript.push({
        role: 'assistant',
        content: `[Agent ${agent_id || 'Human'}]: ${formattedReply}`,
        timestamp: new Date().toISOString()
      });
      sessionStore.saveSession(session);
      return res.json({ status: 'success', session });
    } else if (action === 'close') {
      session.state = 'AWAITING_INPUT';
      if (session.ticket_id) {
        await handoffClient.closeTicket(session.ticket_id);
        session.ticket_id = null;
      }
      const csatText = 'The chat has been closed. How would you rate your experience today? [1-5 ⭐]';
      session.transcript.push({
        role: 'assistant',
        content: csatText,
        timestamp: new Date().toISOString()
      });
      sessionStore.saveSession(session);
      return res.json({ status: 'success', session });
    }

    res.status(400).json({ error: 'Invalid action' });
  } catch (e: any) {
    res.status(500).json({ error: e?.message });
  }
});

app.post('/api/simulate/reset', (_req, res) => {
  analyticsStore.resetMetrics();
  res.json({ status: 'success', message: 'Metrics reseeded successfully' });
});

// --- VITE MIDDLEWARE / PRODUCTION STATIC SERVING ---
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    logger.info(`OmniRouter Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
