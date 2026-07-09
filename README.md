# 🤖 WhatsApp Support Bot Architecture & Scaffolding

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0%2B-009688?logo=fastapi)
![OpenAI](https://img.shields.io/badge/OpenAI-1.50.0%2B-412991?logo=openai)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-EF3950?logo=qdrant)
![Langfuse](https://img.shields.io/badge/Langfuse-LLM%20Tracing-yellow)

## 🚀 Vision & Problem Solving

Customer support on WhatsApp can be overwhelming without the right automation. This project provides a **highly scalable, robust, and intelligent WhatsApp Support Bot** foundation. 

### How it Solves the Problem:
- **Intelligent Routing**: Uses LLM-based intent recognition to route queries accurately.
- **Human-in-the-Loop**: Seamless handoff from AI to human agents when complex issues arise.
- **Privacy First**: Built-in PII (Personally Identifiable Information) masking to ensure data privacy before processing.
- **Deep Analytics**: Tracks interactions, user satisfaction, and agent performance using SQLite and Prometheus metrics.

> **Note:** **Phase 01** (WhatsApp webhook scaffolding and support bot foundation) is fully complete. **Phase 02 & Phase 03** are pending, and I will be developing them!

---

## 📈 Trending Keywords & Tech Stack
`#WhatsAppBusinessAPI` `#AI` `#LLM` `#RAG` `#VectorDB` `#FastAPI` `#OpenAI` `#Qdrant` `#Langfuse` `#Prometheus` `#Redis` `#AsyncIO` `#Python3.11` `#CustomerSupport` `#Chatbot` `#HumanHandoff`

---

## 🏗 Architecture & Pipeline

The system follows a modular, highly scalable asynchronous architecture:

1. **Webhook Reception**: Webhooks from WhatsApp Business API are received securely via **FastAPI** (`src/api/routes/webhook.py`).
2. **Security & Validation**: Every incoming request payload signature is validated (`src/utils/whatsapp_signature.py`).
3. **Orchestration**: The core routing engine (`src/orchestrator/engine.py`) takes the message, manages conversational flow, and checks configured triggers/fallbacks.
4. **Intelligence & Processing**: 
   - Sensitive data (PII) is masked dynamically (`src/utils/pii_masker.py`).
   - Queries are analyzed using OpenAI LLMs and **Qdrant** vector search (`src/intelligence/`).
   - Every reasoning step is traced using **Langfuse**.
5. **Human Handoff**: If the AI cannot resolve the issue confidently, it gracefully triggers the handoff mechanism (`src/handoff/client.py`).
6. **Analytics & Metrics**: Data is saved to an Async SQLite Database (`src/analytics/db.py`) and infrastructure metrics are exposed via **Prometheus**.

---

## 📂 File Arrangements & Structure

```text
whatsapp-support-bot/
├── pyproject.toml         # Dependencies and project metadata
├── README.md              # Project documentation
├── src/
│   ├── analytics/         # Database models and SQLite async setup
│   ├── api/               # FastAPI setup, dependencies, routes (webhooks)
│   ├── bot/               # Session management with Redis
│   ├── handoff/           # Logic for seamless AI-to-human transition
│   ├── intelligence/      # LLM processing, RAG, and Langfuse tracing
│   ├── orchestrator/      # Core engine, fallbacks, and triggers
│   └── utils/             # Helpers: PII masking, config, loggers, formatters
└── tests/                 # Comprehensive test suite (pytest-asyncio, etc.)
```

---

## ⚙️ Requirements & Setup

### Prerequisites
- Python >= 3.11
- Redis Server
- Qdrant Vector Database
- WhatsApp Business API Account
- OpenAI API Key
- Langfuse API Keys (for LLM observability)

### Installation
```bash
# Clone the repository
git clone https://github.com/avuzmal/whatsapp-support-bot.git
cd whatsapp-support-bot

# Install dependencies
pip install -e .

# Run the API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🛣 Roadmap

- [x] **Phase 1**: Webhook scaffolding, FastAPI foundation, architecture setup.
- [ ] **Phase 2**: Full RAG pipeline integration, advanced LLM reasoning. *(In Progress)*
- [ ] **Phase 3**: Dashboard integration, advanced analytics, real-time agent console. *(Upcoming)*