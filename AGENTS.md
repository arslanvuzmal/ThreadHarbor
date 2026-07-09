# WhatsApp Support Bot Architecture & Phase 02 Specifications

Strictly follow this architecture for Phase 02: State Management and Core Orchestrator.

## 1. Project Dependencies
- Update `pyproject.toml` to include `fakeredis>=2.26.0` in the `dev` optional-dependencies.

## 2. Data Models (`src/bot/models.py`)
Define strict Pydantic models with enums:
- `Role`: Enum (`USER`, `BOT`, `SYSTEM`).
- `Message`: `role: Role`, `content: str`, `timestamp: datetime`.
- `SessionState`: Enum (`IDLE`, `AWAITING_INPUT`, `PROCESSING`, `ESCALATED`, `HUMAN_HANDOFF`).
- `SessionData`: `session_id: str`, `state: SessionState`, `history: list[Message]`, `last_interaction_time: datetime`, `metadata: dict`.
- `BotResponse`: `text: str`, `buttons: list[dict] | None` (for WhatsApp interactive), `should_escalate: bool`.

## 3. Redis Session Manager (`src/bot/session.py`)
Use `redis.asyncio` for non-blocking operations.
- Create `SessionManager` class.
- `async def get_or_create_session(session_id: str) -> SessionData`: Fetches from Redis. If not found, creates a new one with `IDLE` state.
- `async def update_session(session_data: SessionData)`: Saves back to Redis.
- `async def add_message(session_id: str, role: Role, content: str)`: Appends to history, updates `last_interaction_time`, and saves.
- `async def is_within_24h_window(session_id: str) -> bool`: WhatsApp only allows free-form messages within 24 hours of the user's last message. Compare `last_interaction_time` with `datetime.now(timezone.utc)`.
- Set a Redis TTL of 48 hours on the session keys to auto-expire dead sessions. Prefix session keys (e.g., `wbot:session:{session_id}`).

## 4. The Orchestrator / State Machine (`src/orchestrator/engine.py`)
Create the `Orchestrator` class.
- `async def process_message(session_id: str, user_input: str) -> BotResponse`
- Flow:
  1. Fetch session.
  2. Add user input to session history.
  3. Transition state to `PROCESSING`.
  4. Keyword checks: Check `user_input.lower()`.
     - If it contains "agent", "human", or "refund", set `should_escalate = True` and transition to `ESCALATED`.
     - Otherwise, generate a dummy response: "I am processing your request: [user_input]. (AI will be added in Phase 3)". Transition to `AWAITING_INPUT`.
  5. Save session.
  6. Return `BotResponse`.
- `async def handle_agent_reply(session_id: str, agent_message: str) -> BotResponse`: Transition state back to `HUMAN_HANDOFF` or `AWAITING_INPUT` depending on if the human closes the chat.

## 5. WhatsApp Message Formatter (`src/utils/whatsapp_formatter.py`)
Create a utility to convert our internal `BotResponse` into WhatsApp Cloud API JSON.
- `def format_text_message(recipient_wa_id: str, text: str) -> dict`
- `def format_interactive_buttons(recipient_wa_id: str, text: str, buttons: list[dict]) -> dict` (WhatsApp allows up to 3 quick reply buttons).
- Ensure all text is truncated to WhatsApp's limits (4096 chars for text, 20 chars for button text) to prevent API errors.

## 6. Update Webhook (`src/api/routes/webhook.py`)
- After verifying signature and parsing the message, extract `session_id` (the WhatsApp `from` wa_id as the session_id).
- Call `Orchestrator.process_message(session_id, user_input)`.
- Use FastAPI `BackgroundTasks` to run an async function: `send_bot_reply(session_id, bot_response, recipient_wa_id, phone_number_id)`.
- Return 200 OK to Meta immediately.

## 7. Tests
- `tests/test_session.py`: Test session creation, message appending, TTL, 24-hour window.
- `tests/test_orchestrator.py`: Mock `SessionManager`. Test "I need an agent" triggers `should_escalate = True` and changes state to `ESCALATED`. Test normal flow.
- `tests/test_webhook.py`: Update existing tests, mock Orchestrator and SessionManager, verify immediate 200.
