# WhatsApp Support Bot Architecture & Phase 03 Specifications

## 1. Project Dependencies
Update `pyproject.toml` dependencies with:
- `openai>=1.50.0`
- `qdrant-client>=1.11.0`
- `tiktoken>=0.7.0`

## 2. LLM & Embedding Clients (`src/intelligence/llm_client.py`)
Use the official `openai` SDK (async version). Do NOT use LangChain or LlamaIndex.
- Create an `LLMClient` class.
- Initialize with `AsyncOpenAI` using the `OPENAI_API_KEY` from configuration.
- Model defaults: `gpt-4o-mini` for chat, `text-embedding-3-small` for embeddings.
- Methods:
  - `async def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> dict`: Returns the raw choice/message object.
  - `async def get_embedding(text: str) -> list[float]`: Returns the embedding vector.

## 3. RAG Pipeline (`src/intelligence/rag.py`)
Use `qdrant-client` (async version) for the Vector DB.
- Create a `RAGPipeline` class.
- Initialize `AsyncQdrantClient` using configuration parameters. Default connection is `http://localhost:6333` with collection name `support_knowledge`.
- Methods:
  - `async def ingest_documents(documents: list[dict])`: Accepts list of `{"id": str, "text": str, "metadata": dict}`. Chunks text if length is > 500 chars. Generates embeddings and upserts to Qdrant.
  - `async def retrieve_context(query: str, top_k: int = 3) -> list[dict]`: Computes query embeddings, queries Qdrant, and returns matching top_k text blocks.
- Provide a helper seeding script `scripts/seed_knowledge_base.py` that loads 5 dummy FAQ documents into Qdrant for immediate testing.

## 4. Tool Definitions & Execution (`src/intelligence/tools.py`)
Expose actions standard OpenAI function calling schema.
- Create list `TOOL_DEFINITIONS` containing schema specifications for:
  1. `check_order_status`: Accepts `order_id: str`. Returns "Shipped" as a simulated response.
  2. `initiate_refund`: Accepts `order_id: str`, `reason: str`. Returns a success message.
- Implement an `execute_tool(tool_name: str, arguments: dict) -> str` function routing parameters with pattern matching. Adds logs for all triggers.

## 5. Context Window Management (`src/intelligence/context.py`)
Ensure conversational safety within the token context window.
- Create `ContextBuilder` class.
- Method `def build_messages(session_history: list[Message], rag_context: str) -> list[dict]`:
  - Begins with a System Prompt: "You are a helpful WhatsApp support agent. Use the provided context to answer questions. If you don't know, say you will connect them to a human. Be concise."
  - Appends the retrieved `rag_context` as a system instruction message.
  - Formats history mapping user/bot role pairs into "user"/"assistant".
  - Counts tokens with `tiktoken` (cl100k_base). If overall sum exceeds 3000 tokens, dynamically ejects oldest conversation turns to enforce the size budget.

## 6. Refactor Core Orchestrator (`src/orchestrator/engine.py`)
Replaces the static mock keyword matching with the agentic pipeline:
1. Fetch session state history, append incoming USER message.
2. Query `RAGPipeline.retrieve_context(...)` based on the input text.
3. Build prompt template via `ContextBuilder.build_messages(...)`.
4. Trigger chat completions with standard `LLMClient.chat_completion(...)` passing tools definition.
5. Loop execution logic:
   - If finish reason evaluates to `"tool_calls"`, fetch call details, execute utilizing `execute_tool`, format and append tool payload results, and trigger final model evaluation again to form the final textual answer.
   - If finish reason stops directly, capture the main message response.
6. Handoff escalation assessment: Transition to `ESCALATED` and set `should_escalate = True` if:
   - The final model text contains the string `[ESCALATE]`, OR
   - The executed tool corresponds to `initiate_refund` where refund properties include amount > $500 (simulated).
7. Persist updated histories, save conversation details, and return formatted `BotResponse`.
8. Implement robust error boundaries catching exceptions to gracefully fallback without crashing the queue thread.

## 7. App Configuration Updates (`src/utils/config.py`)
Add the following fields:
- `OPENAI_API_KEY`: str
- `QDRANT_URL`: str = "http://localhost:6333"
- `QDRANT_API_KEY`: str | None = None
- `LLM_CHAT_MODEL`: str = "gpt-4o-mini"
- `LLM_EMBEDDING_MODEL`: str = "text-embedding-3-small"
