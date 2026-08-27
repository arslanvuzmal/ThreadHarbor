export interface FallbackResult {
  text: string;
  escalated: boolean;
}

export class FallbackEngine {
  /**
   * Rule-based fallback decision tree for graceful degradation when LLM services are offline or failing.
   */
  public process(userInput: string): FallbackResult {
    const textLower = userInput.toLowerCase();

    // 1. Hours query
    if (textLower.includes('hour') || textLower.includes('open') || textLower.includes('time')) {
      return {
        text: 'Our support hours are 9 AM - 5 PM EST.',
        escalated: false,
      };
    }

    // 2. Refund query
    if (textLower.includes('refund') || textLower.includes('return')) {
      return {
        text: 'Please visit our returns portal at https://returns.example.com or I can connect you to an agent.',
        escalated: false,
      };
    }

    // 3. Explicit Agent request
    if (textLower.includes('agent') || textLower.includes('human') || textLower.includes('specialist')) {
      return {
        text: "I'm connecting you to a human specialist. Please hold.",
        escalated: true,
      };
    }

    // 4. Default system failure fallback
    return {
      text: "I'm experiencing technical difficulties. Let me connect you to a human specialist.",
      escalated: true,
    };
  }
}

export const fallbackEngine = new FallbackEngine();
