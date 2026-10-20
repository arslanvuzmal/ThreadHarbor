<div align="center">
  <img src="https://img.shields.io/badge/OmniRouter-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" alt="OmniRouter Support Bot" />
  <h1>OmniRouter</h1>
  <p>
    <b>Highly Scalable, Context-Aware, Human-in-the-Loop WhatsApp Orchestrator</b>
  </p>
  
  [![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0+-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
  [![OpenAI](https://img.shields.io/badge/OpenAI-Powered-412991.svg?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
  [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
  [![Langfuse](https://img.shields.io/badge/Langfuse-Traced-yellow.svg?style=flat-square)](https://langfuse.com)
  [![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-EF3950.svg?style=flat-square)](https://qdrant.tech)
</div>

---

## 🌟 Executive Summary

Customer support scaling on WhatsApp can quickly become unmanageable without robust automation. **OmniRouter** (repository: ThreadHarbor) triages WhatsApp messages, masks card numbers, emails and phone numbers, and hands conversations to a human agent when a customer asks for one, when sentiment or a loop says so, or when a policy limit is hit.

It is written as an asynchronous FastAPI service (Python) with a matching Express server and React dashboard (TypeScript) for the demo.

---

## What runs today

- **The reply step is simulated.** No model is called for replies: a set of rules returns fixed answers,
  reported as model `simulated` with 0 tokens. The one real model call is the optional handoff summary
  (OpenAI, only when `OPENAI_API_KEY` is set); its input is masked first.
- **Masking** covers cards (13–19 digits), emails and phone numbers. Names are not masked. The human
  agent's ticket transcript keeps the original text, because the agent needs it.
- **Handoff** goes to a mock helpdesk client (`HANDOFF_PROVIDER=mock`) unless one is configured.

## Run the demo (no keys)

```bash
npm install
npx tsx server.ts          # http://localhost:3000
```

Open the **WhatsApp Simulator** tab and press the presets: business hours, the PII masking test, a refund
over $500 (escalated by the policy limit and turned into a ticket), then reply as the agent. The
**CCaaS Tickets** and **Analytics** tabs show what happened in this session only. Set
`SEED_SAMPLE_METRICS=true` to start with generated example history instead; the dashboard then says it
is sample data.

---

## 🚀 Key Features

| Feature | Description | Stack |
|:---|:---|:---|
| 🧠 **Triage** | Rule-based triggers for handoff requests, negative sentiment, loops and policy limits. The reply step is simulated (see below). | `Python` `TypeScript` |
| 📚 **RAG Pipeline** | Semantic search across company knowledge bases. | `Qdrant` `Embeddings` |
| 🛡️ **PII masking** | Card numbers, emails and phone numbers are replaced before the reply step, in handoff summaries and in logs. | `Regex` |
| 🤝 **Human Handoff** | Context-aware escalation to live human agents. | `Redis` `Orchestrator` |
| 📊 **Deep Analytics** | Complete traceability, conversation logs, and monitoring. | `Prometheus` `SQLite` |
| 🐳 **Docker Native** | Out-of-the-box containerization for instant deployment. | `Docker Compose` |

---

## 🏗️ Architecture & Flow Diagram

The application leverages a heavily modular design. Webhooks are consumed safely, contextualized against previous state in Redis, analyzed for intent, masked, processed, and responded to.

```mermaid
graph TD
    A[WhatsApp API] -->|Webhook Request| B(FastAPI Gateway)
    B -->|Signature Validation| C{Security Check}
    C -- Valid --> D[Orchestrator Engine]
    C -- Invalid --> Z[Drop Request]
    D --> E[Session State / Redis]
    D --> F[PII Masking Layer]
    F --> G{Is Human Handoff?}
    G -- Yes --> H[Live Agent Queue]
    G -- No --> I[RAG / Qdrant Knowledge Retrieval]
    I --> J[OpenAI LLM Generation]
    J --> K[Langfuse Tracing]
    K --> L[Format Response & Dispatch]
    L --> A
    D --> M[Prometheus Metrics & Async DB]
```

---

## 📂 Codebase Structure

The codebase adheres strictly to Domain-Driven Design (DDD), ensuring modular isolation:

```text
whatsapp-orchestrator/
├── pyproject.toml         # Python Dependencies (uv/pip)
├── Dockerfile             # Container definition for the API
├── docker-compose.yml     # Local multi-service orchestration
├── docs/                  # Extended documentation (DEPLOYMENT.md)
├── scripts/               # Utility scripts (e.g., seed_knowledge_base.py)
├── src/
│   ├── analytics/         # SQLite async DB, telemetry mapping
│   ├── api/               # FastAPI setup, route declarations
│   ├── bot/               # Redis Session management
│   ├── handoff/           # CCaaS integrations and ticketing logic
│   ├── intelligence/      # LLM processing, semantic search, Langfuse tracking
│   ├── orchestrator/      # Triage engine, failure fallbacks, safety triggers
│   └── utils/             # Helpers: PII masking, cryptographic validation, logging
└── tests/                 # Unit & Integration Testing Suite (Pytest)
```

---

## ⚙️ Getting Started (Local Development)

### Prerequisites
- Python 3.11+
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Accounts: WhatsApp Business API, OpenAI, Qdrant, Langfuse

### 1. Installation

Clone the repository and install dependencies:
```bash
git clone https://github.com/avuzmal/whatsapp-orchestrator.git
cd whatsapp-orchestrator
pip install -e .[dev]
```

### 2. Environment Setup
Copy the `.env.example` to `.env` (or configure manually) with the required values such as `WHATSAPP_VERIFY_TOKEN`, `OPENAI_API_KEY`, and database URLs.

### 3. Spin Up Infrastructure
Easily spin up the entire stack using Docker Compose:
```bash
docker compose up -d --build
```
This will launch:
* FastAPI Server (`localhost:8000`)
* Redis (`localhost:6379`)
* Qdrant (`localhost:6333`)
* PostgreSQL (if configured)

### 4. Seeding Knowledge
Populate the RAG system with default information:
```bash
python scripts/seed_knowledge_base.py
```

---

## 🧪 Testing & Quality Assurance

We maintain a rigorous standard of code quality through a comprehensive test suite.
Run tests locally using `pytest`:

```bash
# Execute unit and integration tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src
```
*Current coverage validates core fallbacks, orchestrator degradation gracefully, PII masking, payload validation, and docker health endpoints.*

---

## 🚀 Deployment

We provide an infrastructure-agnostic deployment protocol. 
For production deployment, see our comprehensive **[Production Deployment Guide](./docs/DEPLOYMENT.md)**.

Highlights include:
- `infra/docker-compose.prod.yml` for multi-stage cloud deploys.
- `.github/workflows/ci.yml` for Automated CI/CD.
- Container-native resource isolation without running as root.

---

## 🛣️ Roadmap

- [x] **Phase 1**: Webhook scaffolding, robust core architecture, and fundamental pipelines.
- [x] **Phase 2**: Full RAG pipeline deployment and advanced LLM chain reasoning.
- [x] **Phase 3**: Custom Dashboard integrations and comprehensive analytics UI.

> *Note: This project is maintained independently. All phases are fully complete.*