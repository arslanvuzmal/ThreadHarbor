import { SessionRecord } from './session';
import { logger } from './logger';

export class SentimentAnalyzer {
  public analyze(text: string): number {
    const textLower = text.toLowerCase();
    const negativeKeywords = ['angry', 'unacceptable', 'scam', 'terrible', 'worst', 'horrible', 'furious', 'fraud'];
    if (negativeKeywords.some(kw => textLower.includes(kw))) {
      logger.debug('Negative sentiment detected via keyword match', { text });
      return -0.8;
    }
    return 0.0;
  }
}

export class EscalationTriggerEngine {
  private sentimentAnalyzer: SentimentAnalyzer;

  constructor() {
    this.sentimentAnalyzer = new SentimentAnalyzer();
  }

  /**
   * Pre-LLM Triggers:
   * 1. Explicit Intent: 'agent', 'human', 'representative', 'talk to someone'
   * 2. Loop Detection: User repeats the exact same message twice in a row
   * 3. Sentiment Analysis: Score < -0.5
   */
  public evaluatePreLLM(text: string, session: SessionRecord): { escalated: boolean; reason: string | null } {
    const textLower = text.toLowerCase();

    // 1. Explicit Request
    const explicitKeywords = ['agent', 'human', 'representative', 'talk to someone', 'speak to a person', 'support person'];
    if (explicitKeywords.some(kw => textLower.includes(kw))) {
      return { escalated: true, reason: 'Explicit Request' };
    }

    // 2. Loop Detection (repeated exact message)
    if (session.last_user_message && session.last_user_message.trim().toLowerCase() === text.trim().toLowerCase()) {
      return { escalated: true, reason: 'Loop Detected' };
    }

    // 3. Sentiment Check
    const sentimentScore = this.sentimentAnalyzer.analyze(text);
    if (sentimentScore < -0.5) {
      return { escalated: true, reason: 'Sentiment: Negative' };
    }

    return { escalated: false, reason: null };
  }

  /**
   * Post-LLM Triggers:
   * 1. Low Confidence: Response contains "i don't know" or "i'm not sure" (2 consecutive turns)
   * 2. Policy Limit: Tool call to initiate_refund with amount > 500
   */
  public evaluatePostLLM(
    llmResponseText: string,
    session: SessionRecord,
    toolCalls: Array<{ name: string; arguments?: Record<string, any> | string }> | null
  ): { escalated: boolean; reason: string | null } {
    const responseLower = llmResponseText.toLowerCase();
    const isLowConfidence = responseLower.includes("i don't know") || responseLower.includes("i'm not sure");

    if (isLowConfidence) {
      session.low_confidence_consecutive_count += 1;
      logger.info("Low confidence response turn count", { count: session.low_confidence_consecutive_count });
    } else {
      session.low_confidence_consecutive_count = 0;
    }

    if (session.low_confidence_consecutive_count >= 2) {
      return { escalated: true, reason: 'Loop Detected' };
    }

    if (toolCalls && toolCalls.length > 0) {
      for (const call of toolCalls) {
        if (call.name === 'initiate_refund') {
          let args: any = call.arguments || {};
          if (typeof args === 'string') {
            try {
              args = JSON.parse(args);
            } catch {
              args = {};
            }
          }
          const amount = parseFloat(args.amount);
          if (!isNaN(amount) && amount > 500) {
            return { escalated: true, reason: 'Policy Limit' };
          }
        }
      }
    }

    return { escalated: false, reason: null };
  }
}

export const triggerEngine = new EscalationTriggerEngine();
