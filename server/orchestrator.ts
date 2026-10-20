import { sessionStore, SessionRecord } from './session';
import { triggerEngine } from './triggers';
import { fallbackEngine } from './fallback';
import { handoffClient } from './handoff';
import { analyticsStore } from './analytics';
import { maskPII } from './pii';
import { logger } from './logger';

export interface OrchestrationResult {
  reply_text: string;
  masked_input: string;
  state: string;
  escalated: boolean;
  used_fallback: boolean;
  intent: string;
  latency_ms: number;
  llm_model: string | null;
  tokens_used: number;
  ticket_id: string | null;
  session: SessionRecord;
}

export class Orchestrator {
  public async handleMessage(
    sessionId: string,
    rawText: string,
    phoneNumberId?: string,
    mediaBytesBase64?: string,
    mimeType?: string
  ): Promise<OrchestrationResult> {
    const startTime = Date.now();
    let usedFallback = false;
    let escalated = false;
    let modelUsed: string | null = "simulated";
    let tokensUsed = 0;
    let intent = "success_bot_chat";

    const session = sessionStore.getSession(sessionId);
    if (phoneNumberId) {
      session.phone_number_id = phoneNumberId;
    }
    session.last_interaction_timestamp = Date.now() / 1000;

    const maskedText = maskPII(rawText);
    logger.info("Received message", { sender: sessionId, body: maskedText });

    // 1. SILENT MODE BYPASS CHECK
    if (session.state === "HUMAN_HANDOFF") {
      logger.info("Session in HUMAN_HANDOFF. Forwarding message to agent.", { sessionId });
      session.transcript.push({
        role: "user",
        content: rawText,
        timestamp: new Date().toISOString()
      });

      if (session.ticket_id) {
        try {
          await handoffClient.sendAgentMessage(session.ticket_id, rawText);
        } catch (e: any) {
          logger.error("Failed to forward message to handoff client", { error: e?.message });
        }
      }

      sessionStore.saveSession(session);
      const latencyMs = Date.now() - startTime;

      analyticsStore.recordMetric({
        session_id: sessionId,
        latency_ms: latencyMs,
        used_fallback: false,
        escalated: false,
        intent: "silent_bypass",
        llm_model: null,
        tokens_used: 0,
      });

      return {
        reply_text: "",
        masked_input: maskedText,
        state: session.state,
        escalated: false,
        used_fallback: false,
        intent: "silent_bypass",
        latency_ms: latencyMs,
        llm_model: null,
        tokens_used: 0,
        ticket_id: session.ticket_id,
        session
      };
    }

    // Normal message flow: record user message
    session.transcript.push({
      role: "user",
      content: rawText,
      timestamp: new Date().toISOString()
    });

    // 2. PRE-PROCESSING TRIGGERS CHECK
    const preCheck = triggerEngine.evaluatePreLLM(rawText, session);
    if (preCheck.escalated && preCheck.reason) {
      logger.info("Pre-LLM Escalation triggered", { sessionId, reason: preCheck.reason });
      session.state = "HUMAN_HANDOFF";
      escalated = true;
      intent = preCheck.reason;

      const ticketId = await handoffClient.createTicket(session, preCheck.reason);
      session.ticket_id = ticketId;

      const responseText = "I'm connecting you to a human specialist. Please hold.";
      session.transcript.push({
        role: "assistant",
        content: responseText,
        timestamp: new Date().toISOString()
      });

      session.last_user_message = rawText;
      session.low_confidence_consecutive_count = 0;
      sessionStore.saveSession(session);

      const latencyMs = Date.now() - startTime;
      analyticsStore.recordMetric({
        session_id: sessionId,
        latency_ms: latencyMs,
        used_fallback: false,
        escalated: true,
        intent,
        llm_model: null,
        tokens_used: 0,
      });

      return {
        reply_text: responseText,
        masked_input: maskedText,
        state: session.state,
        escalated: true,
        used_fallback: false,
        intent,
        latency_ms: latencyMs,
        llm_model: null,
        tokens_used: 0,
        ticket_id: ticketId,
        session
      };
    }

    // 3. CALL LLM (With Simulated AI & Graceful Degradation Fallback)
    let responseText = "";
    let toolCalls: Array<{ name: string; arguments?: any }> | null = null;

    try {
      // The model step gets the masked text (it used to receive the raw message; masking only
      // covered the logs). Triggers and the human agent still see the original.
      const llmResult = await this.callLLM(maskedText, mediaBytesBase64, mimeType);
      responseText = llmResult.text;
      toolCalls = llmResult.toolCalls;
      modelUsed = llmResult.model;
      tokensUsed = llmResult.tokens;
    } catch (e: any) {
      logger.error("LLM processing loop failed; invoking Graceful Degradation FallbackEngine", { error: e?.message });
      usedFallback = true;
      modelUsed = null;
      tokensUsed = 0;

      const fallbackResult = fallbackEngine.process(rawText);
      responseText = fallbackResult.text;

      if (fallbackResult.escalated) {
        escalated = true;
        session.state = "HUMAN_HANDOFF";
        intent = "degraded_escalation";

        const ticketId = await handoffClient.createTicket(session, "Technical Failure");
        session.ticket_id = ticketId;

        session.transcript.push({
          role: "assistant",
          content: responseText,
          timestamp: new Date().toISOString()
        });
        session.last_user_message = rawText;
        session.low_confidence_consecutive_count = 0;
        sessionStore.saveSession(session);

        const latencyMs = Date.now() - startTime;
        analyticsStore.recordMetric({
          session_id: sessionId,
          latency_ms: latencyMs,
          used_fallback: true,
          escalated: true,
          intent,
          llm_model: null,
          tokens_used: 0,
        });

        return {
          reply_text: responseText,
          masked_input: maskedText,
          state: session.state,
          escalated: true,
          used_fallback: true,
          intent,
          latency_ms: latencyMs,
          llm_model: null,
          tokens_used: 0,
          ticket_id: ticketId,
          session
        };
      }

      intent = "degraded_fallback";
      session.transcript.push({
        role: "assistant",
        content: responseText,
        timestamp: new Date().toISOString()
      });
      session.last_user_message = rawText;
      sessionStore.saveSession(session);

      const latencyMs = Date.now() - startTime;
      analyticsStore.recordMetric({
        session_id: sessionId,
        latency_ms: latencyMs,
        used_fallback: true,
        escalated: false,
        intent,
        llm_model: null,
        tokens_used: 0,
      });

      return {
        reply_text: responseText,
        masked_input: maskedText,
        state: session.state,
        escalated: false,
        used_fallback: true,
        intent,
        latency_ms: latencyMs,
        llm_model: null,
        tokens_used: 0,
        ticket_id: null,
        session
      };
    }

    // 4. POST-PROCESSING TRIGGERS CHECK
    const postCheck = triggerEngine.evaluatePostLLM(responseText, session, toolCalls);
    if (postCheck.escalated && postCheck.reason) {
      logger.info("Post-LLM Escalation triggered", { sessionId, reason: postCheck.reason });
      session.state = "HUMAN_HANDOFF";
      escalated = true;
      intent = postCheck.reason;

      const ticketId = await handoffClient.createTicket(session, postCheck.reason);
      session.ticket_id = ticketId;

      const handoverText = "I'm connecting you to a human specialist. Please hold.";
      session.transcript.push({
        role: "assistant",
        content: handoverText,
        timestamp: new Date().toISOString()
      });
      session.last_user_message = rawText;
      sessionStore.saveSession(session);

      const latencyMs = Date.now() - startTime;
      analyticsStore.recordMetric({
        session_id: sessionId,
        latency_ms: latencyMs,
        used_fallback: false,
        escalated: true,
        intent,
        llm_model: modelUsed,
        tokens_used: tokensUsed,
      });

      return {
        reply_text: handoverText,
        masked_input: maskedText,
        state: session.state,
        escalated: true,
        used_fallback: false,
        intent,
        latency_ms: latencyMs,
        llm_model: modelUsed,
        tokens_used: tokensUsed,
        ticket_id: ticketId,
        session
      };
    }

    // Normal response
    session.transcript.push({
      role: "assistant",
      content: responseText,
      timestamp: new Date().toISOString()
    });
    session.last_user_message = rawText;
    intent = "success_bot_chat";
    sessionStore.saveSession(session);

    const latencyMs = Date.now() - startTime;
    analyticsStore.recordMetric({
      session_id: sessionId,
      latency_ms: latencyMs,
      used_fallback: false,
      escalated: false,
      intent,
      llm_model: modelUsed,
      tokens_used: tokensUsed,
    });

    return {
      reply_text: responseText,
      masked_input: maskedText,
      state: session.state,
      escalated: false,
      used_fallback: false,
      intent,
      latency_ms: latencyMs,
      llm_model: modelUsed,
      tokens_used: tokensUsed,
      ticket_id: null,
      session
    };
  }

  private async callLLM(
    text: string,
    mediaBytesBase64?: string,
    mimeType?: string
  ): Promise<{ text: string; toolCalls: Array<{ name: string; arguments?: any }> | null; model: string; tokens: number }> {
    const textLower = text.toLowerCase();
    // No model is called: replies come from the rules below. Reported as "simulated", 0 tokens.
    const model = "simulated";
    const tokens = 0;

    if (textLower.includes("force error")) {
      throw new Error("Simulated internal service error (LLM/RAG failure)");
    }

    if (mediaBytesBase64 && mimeType?.startsWith("image/")) {
      return {
        text: "Image received. In this demo the model step is simulated, so the image is not analysed.",
        toolCalls: null,
        model,
        tokens
      };
    }

    if (mediaBytesBase64 && mimeType === "application/pdf") {
      return {
        text: `PDF received. In this demo the model step is simulated, so the document is not read.`,
        toolCalls: null,
        model,
        tokens
      };
    }

    if (textLower.includes("force low confidence") || textLower.includes("don't know") || textLower.includes("not sure")) {
      return {
        text: "I don't know the exact answer to this specific inquiry.",
        toolCalls: null,
        model,
        tokens
      };
    }

    // A refund request becomes an initiate_refund tool call for the amount in the message; the
    // policy trigger then decides (over 500 escalates). It used to look for the strings "500",
    // "600" or "1000", so the "$650.00" preset never reached the policy.
    const amountMatch = text.match(/\$?\s?(\d+(?:[.,]\d{1,2})?)/);
    const amount = amountMatch ? parseFloat(amountMatch[1].replace(",", ".")) : NaN;
    if (textLower.includes("force refund trigger") || (textLower.includes("refund") && !isNaN(amount))) {
      return {
        text: "Initiating refund review with supervisor authorization.",
        toolCalls: [{ name: "initiate_refund", arguments: { amount: textLower.includes("force refund trigger") ? 650.0 : amount } }],
        model,
        tokens
      };
    }

    if (textLower.includes("order") || textLower.includes("track") || textLower.includes("shipping")) {
      return {
        text: "Your order #89421 is currently in transit with express carrier. Estimated delivery is tomorrow by 4:00 PM.",
        toolCalls: null,
        model,
        tokens
      };
    }

    if (textLower.includes("hour") || textLower.includes("open") || textLower.includes("location")) {
      return {
        text: "Our customer support team is available Monday through Friday from 9 AM to 5 PM EST. How can I assist you further?",
        toolCalls: null,
        model,
        tokens
      };
    }

    return {
      text: `Hello! I received your inquiry: "${text}". How can I best assist you today with our services?`,
      toolCalls: null,
      model,
      tokens
    };
  }
}

export const orchestrator = new Orchestrator();
