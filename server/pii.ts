/**
 * Mask sensitive PII in the given text with placeholders.
 * Replaces:
 * - Phone numbers with [PHONE]
 * - Email addresses with [EMAIL]
 * - Credit card numbers (13-19 digits, optionally separated by spaces or dashes) with [CARD]
 */
export function maskPII(text: string): string {
  if (!text) return text;

  let result = text;

  // Mask credit card numbers: 13 to 19 digits, possibly separated by spaces or dashes
  const cardPattern = /\b\d(?:\s*-?\s*\d){12,18}\b/g;
  result = result.replace(cardPattern, "[CARD]");

  // Mask email addresses
  const emailPattern = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g;
  result = result.replace(emailPattern, "[EMAIL]");

  // Mask phone numbers: International with +
  const intlPattern = /\+\d{1,4}[-.\s]?\(?\d{1,4}?\)?[-.\s]?\d{1,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b|\+\d{7,15}\b/g;
  result = result.replace(intlPattern, "[PHONE]");

  // Mask standard US-style or local phone numbers
  const standardPhonePattern = /(?:\b|\()(?:\d[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g;
  result = result.replace(standardPhonePattern, "[PHONE]");

  return result;
}
