export const config = {
  WHATSAPP_VERIFY_TOKEN: process.env.WHATSAPP_VERIFY_TOKEN || "omni_verify_token_secure_2025",
  WHATSAPP_APP_SECRET: process.env.WHATSAPP_APP_SECRET || "omni_app_secret_1234567890abcdef",
  WHATSAPP_ACCESS_TOKEN: process.env.WHATSAPP_ACCESS_TOKEN || "EAABsample_token_mock",
  AGENT_API_SECRET: process.env.AGENT_API_SECRET || "default_agent_secret",
  REDIS_URL: process.env.REDIS_URL || "redis://localhost:6379/0",
  QDRANT_URL: process.env.QDRANT_URL || "http://localhost:6333",
  LOG_LEVEL: process.env.LOG_LEVEL || "INFO",
  HANDOFF_PROVIDER: process.env.HANDOFF_PROVIDER || "mock",
  MAX_MEDIA_SIZE_MB: 5,
};
