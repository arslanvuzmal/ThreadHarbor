# Production Deployment Guide & Secret Management

This guide explains how to deploy the WhatsApp Support Bot in production environments, manage secrets securely, configure CI/CD, and perform pre-production validation.

---

## 🔑 Required Environment Variables

Ensure these variables are configured in your hosting environment (e.g., Render, Railway, AWS ECS) or your `.env.prod` file:

| Variable | Description | Example / Recommended Value |
|---|---|---|
| `WHATSAPP_VERIFY_TOKEN` | Secret string to verify WhatsApp webhooks | `your_custom_token_here` |
| `WHATSAPP_APP_SECRET` | App secret from Meta Developer console | `a7b6...4f9a` |
| `WHATSAPP_ACCESS_TOKEN` | Permanent/System User WhatsApp access token | `EAAB...` |
| `REDIS_URL` | Redis server connection string | `redis://redis:6379/0` (or cloud instance) |
| `QDRANT_URL` | Qdrant Vector database endpoint | `http://qdrant:6333` (or cloud endpoint) |
| `DATABASE_URL` | Analytics persistence database | `sqlite+aiosqlite:///./analytics.db` or PostgreSQL |
| `AGENT_API_SECRET` | Secret token to secure agent router endpoint | `secure_token_abc123` |
| `LOG_LEVEL` | Application logger verbosity level | `INFO` or `WARNING` |
| `HANDOFF_PROVIDER` | Ticket manager/CCaaS integrations provider | `mock` (or `zendesk` / `freshdesk`) |
| `LANGFUSE_PUBLIC_KEY` | Public key for LLM tracing and observability | `pk-lf-...` |
| `LANGFUSE_SECRET_KEY` | Secret key for LLM tracing and observability | `sk-lf-...` |
| `LANGFUSE_HOST` | Endpoint URL of the Langfuse service | `https://cloud.langfuse.com` |
| `MAX_MEDIA_SIZE_MB` | Maximum allowed attachment size in MB | `5` |

---

## 🔒 GitHub Actions Secrets Setup

For automated CI/CD and deployment, configure the following **Repository Secrets** in GitHub under **Settings > Secrets and variables > Actions**:

1. `GITHUB_TOKEN`: Automatically provided by GitHub. Used to authorize push/pull from GitHub Container Registry (GHCR).
2. `CODECOV_TOKEN`: Used to upload unit/integration test coverage reports to Codecov.
3. `PRODUCTION_SECRET`: Encrypted configuration or SSH keys required for production deployment commands.

---

## 🚀 Deployment Commands

### 1. Local Development Deployment
Build and start all services locally inside Docker containers using:
```bash
docker compose up --build
```
This starts:
- **FastAPI Web App** on `http://localhost:8000`
- **Redis Cache** on `http://localhost:6379`
- **Qdrant Vector DB** on `http://localhost:6333`
- **Postgres DB** on `http://localhost:5432`

### 2. Cloud Infrastructure Deployment (Multi-Stage Compose)
For cloud platforms supporting Docker Compose (e.g. AWS ECS with Compose, VM servers, etc.):
```bash
# Create the external production network if not already present
docker network create prod_network

# Start the services with production configurations
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d
```

### 3. Database & Knowledge Base Seeding
On your first deploy, run the database and vector seeding script inside the container to pre-populate support RAG indices:
```bash
docker compose exec app sh /app/infra/scripts/seed.sh
```

---

## 🛡️ Pre-Production Validation Checklist

Before public rollout, verify the following checklist items:

- [ ] **Webhook Validation**: Send a mock payload with validation signature to verify signature verification does not reject legitimate payloads.
- [ ] **Dependency Health**: Check the `/ready` endpoint of the live server (`https://yourdomain.com/ready`). It must return `200 OK` with all components (`redis`, `qdrant`, `database`) listed as `"ok"`.
- [ ] **Observability**: Verify that interactions on the server initiate traces inside your Langfuse dashboard.
- [ ] **Security**: Confirm that all debug tools (FastAPI `docs_url` and `redoc_url`) are disabled by setting `LOG_LEVEL=INFO` (or higher) in production settings.
- [ ] **Resource Isolation**: Validate that the container runs with the `appuser` non-root user (no root privileges inside container).
