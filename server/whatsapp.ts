import crypto from 'crypto';

/**
 * Verify that the payload matches the X-Hub-Signature-256 header sent by Meta.
 * Meta's header format: sha256=<hex_digest>
 */
export function verifySignature(payload: string | Buffer, signatureHeader: string | undefined, appSecret: string): boolean {
  if (!signatureHeader) return false;
  const prefix = 'sha256=';
  if (!signatureHeader.startsWith(prefix)) return false;

  const hexDigest = signatureHeader.slice(prefix.length).trim();
  const hmac = crypto.createHmac('sha256', appSecret);
  hmac.update(typeof payload === 'string' ? Buffer.from(payload, 'utf-8') : payload);
  const expectedHex = hmac.digest('hex');

  try {
    return crypto.timingSafeEqual(Buffer.from(hexDigest, 'utf-8'), Buffer.from(expectedHex, 'utf-8'));
  } catch {
    return false;
  }
}

/**
 * Formats markdown text to WhatsApp markup (e.g. **bold** -> *bold*)
 */
export function whatsappFormatter(text: string): string {
  if (!text) return '';
  return text.replace(/\*\*(.*?)\*\*/g, '*$1*');
}
