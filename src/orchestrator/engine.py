import asyncio
import time
from typing import Any

from fastapi import BackgroundTasks

from src.analytics.db import AnalyticsRecorder
from src.bot.session import BotResponse, RedisSessionStore, SessionData
from src.handoff.client import BaseHandoffClient
from src.handoff.payload import build_payload
from src.intelligence.tracing import trace_llm_call
from src.orchestrator.fallback import FallbackEngine
from src.orchestrator.triggers import EscalationTriggerEngine
import json

from src.bot.models import BotResponse, Role, SessionState
from src.bot.session import SessionManager
from src.intelligence.context import ContextBuilder
from src.intelligence.llm_client import LLMClient
from src.intelligence.rag import RAGPipeline
from src.intelligence.tools import TOOL_DEFINITIONS, execute_tool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """The central message processing hub.

    Handles message routing, orchestrates state transitions, manages loop detection/sentiment/policy checks,
    and coordinates with external human handoff systems.
    """

    def __init__(
        self,
        handoff_client: BaseHandoffClient,
        trigger_engine: EscalationTriggerEngine | None = None,
        session_store: RedisSessionStore | None = None,
        analytics_recorder: AnalyticsRecorder | None = None,
    ) -> None:
        """Initializes the Orchestrator.

        Args:
            handoff_client: Client for the external ticketing system (e.g. MockZendeskClient).
            trigger_engine: Escalation trigger evaluator engine.
            session_store: Store for loading and saving session state.
            analytics_recorder: Database recorder for interaction metrics.
        """
        self.handoff_client = handoff_client
        self.trigger_engine = trigger_engine or EscalationTriggerEngine()
        self.session_store = session_store or RedisSessionStore()
        self.analytics_recorder = analytics_recorder or AnalyticsRecorder()
        # To avoid garbage collection of asynchronous background tasks as per RUF006 rule
        self._background_tasks: set[asyncio.Task[Any]] = set()

    async def get_or_create_session(self, session_id: str) -> SessionData:
        """Loads the session from store, or creates a new one if it does not exist.

        Args:
            session_id: Unique identifier for the user session (WhatsApp phone number or wa_id).

        Returns:
            The loaded or newly created SessionData object.
        """
        data_str = self.session_store.get_session(session_id)
        if data_str:
            try:
                return SessionData.model_validate_json(data_str)
            except Exception as e:
                logger.error("Failed to parse session from store, creating a fresh one", error=str(e))

        # Default new session initialization
        return SessionData(
            session_id=session_id,
            user_profile={"name": "Customer", "phone": session_id, "tier": "standard"},
        )

    async def save_session(self, session: SessionData) -> None:
        """Saves the current SessionData to the store.

        Args:
            session: SessionData instance to serialize and save.
        """
        self.session_store.save_session(session.session_id, session.model_dump_json())

    async def call_llm(self, text: str, _session: SessionData) -> tuple[str, list[dict[str, Any]] | None]:
        """Mock LLM call. Simulates the chatbot assistant's prompt execution and tool calls.

        Checks for specific test injection phrases to simulate tool triggers or low-confidence turns.

        Args:
            text: Input message from the user.
            _session: Current SessionData instance.

        Returns:
            A tuple of (llm_response_text: str, list_of_tool_calls: Optional[List[Dict[str, Any]]]).
        """
        text_lower = text.lower()

        # Simulated scenarios for testing:
        if "force low confidence" in text_lower:
            return "I'm not sure about that.", None

        if "force refund trigger" in text_lower:
            # Tool call with a restricted limit (> $500)
            return "Initiating refund.", [{"name": "initiate_refund", "arguments": {"amount": 600.0}}]

        if "refund" in text_lower and "500" in text_lower:
            return "Initiating refund.", [{"name": "initiate_refund", "arguments": {"amount": 600.0}}]

        if "don't know" in text_lower or "not sure" in text_lower:
            return "I don't know the answer to this question.", None

        if "force error" in text_lower:
            raise RuntimeError("Simulated internal service error (LLM/RAG failure)")

        # Standard AI response
        return f"Hi! I received your message: '{text}'. How can I help you today?", None

    async def handle_message(
        self,
        session_id: str,
        text: str,
        background_tasks: BackgroundTasks | None = None,
    ) -> BotResponse:
        """Processes an incoming message, performing state transitions, trigger evaluation, and LLM calls.

        Args:
            session_id: Unique session identifier (sender WhatsApp ID).
            text: Raw message content.
            background_tasks: Optional FastAPI BackgroundTasks instance to offload DB writes.

        Returns:
            BotResponse containing the text reply to send back to the user.
        """
        start_time = time.time()
        used_fallback = False
        escalated = False
        model_used: str | None = "gpt-4o-mini"
        tokens_used = 0
        intent: str | None = None

        session = await self.get_or_create_session(session_id)

        # 1. SILENT MODE BYPASS CHECK
        if session.state == "HUMAN_HANDOFF":
            logger.info("Session in HUMAN_HANDOFF. Forwarding message to agent.", session_id=session_id)
            session.transcript.append({"role": "user", "content": text})

            # Forward the user message to the CCaaS ticketing system
            if session.ticket_id:
                try:
                    await self.handoff_client.send_agent_message(session.ticket_id, text)
                except Exception as e:
                    logger.error("Failed to forward message to handoff client", error=str(e))

            await self.save_session(session)

            # Record metrics for handoff bypass interaction
            latency_ms = int((time.time() - start_time) * 1000)
            self._dispatch_metrics(
                session_id=session_id,
                latency_ms=latency_ms,
                used_fallback=False,
                escalated=False,
                intent="silent_bypass",
                llm_model=None,
                tokens_used=0,
                background_tasks=background_tasks,
            )

            # Silent mode: return an empty BotResponse as the human agent will reply later
            return BotResponse(text="")

        # Normal message flow: record the user input in the session transcript
        session.transcript.append({"role": "user", "content": text})

        # 2. PRE-PROCESSING TRIGGERS CHECK
        escalated_pre, reason_pre = self.trigger_engine.evaluate_pre_llm(text, session)
        if escalated_pre and reason_pre:
            logger.info("Pre-LLM Escalation triggered", session_id=session_id, reason=reason_pre)
            session.state = "HUMAN_HANDOFF"
            escalated = True
            intent = reason_pre

            # Generate context payload and open ticket in CCaaS
            payload = await build_payload(session, reason_pre)
            ticket_id = await self.handoff_client.create_ticket(session_id, payload)
            session.ticket_id = ticket_id

            # Save the handover message to transcript and return it
            response_text = "I'm connecting you to a human specialist. Please hold."
            session.transcript.append({"role": "assistant", "content": response_text})

            # Update tracking indicators
            session.last_user_message = text
            session.low_confidence_consecutive_count = 0

            await self.save_session(session)

            latency_ms = int((time.time() - start_time) * 1000)
            self._dispatch_metrics(
                session_id=session_id,
                latency_ms=latency_ms,
                used_fallback=False,
                escalated=escalated,
                intent=intent,
                llm_model=None,
                tokens_used=0,
                background_tasks=background_tasks,
            )

            return BotResponse(text=response_text)

        # 3. CALL LLM (Wrapped with Tracing and Graceful Degradation)
        try:
            async with trace_llm_call(session_id, text) as span:
                response_text, tool_calls = await self.call_llm(text, session)

                # Record trace details
                span.record_generation(
                    prompt=text,
                    completion=response_text,
                    model=model_used or "gpt-4o-mini",
                    prompt_tokens=15,
                    completion_tokens=25,
                )
                tokens_used = 40
        except Exception as e:
            logger.exception(
                "Normal processing loop failed; invoking Graceful Degradation FallbackEngine",
                error=str(e),
            )
            used_fallback = True
            model_used = None
            tokens_used = 0

            # Invoke FallbackEngine (decision tree fallback)
            fallback_engine = FallbackEngine()
            fallback_response, fallback_escalate = fallback_engine.process(text)
            response_text = fallback_response.text

            # Handle escalation requested by the fallback engine
            if fallback_escalate:
                escalated = True
                session.state = "HUMAN_HANDOFF"
                intent = "degraded_escalation"

                # Generate payload and open CCaaS ticket
                payload = await build_payload(session, "Technical Failure")
                ticket_id = await self.handoff_client.create_ticket(session_id, payload)
                session.ticket_id = ticket_id

                # Save the specialist transition message
                session.transcript.append({"role": "assistant", "content": response_text})
                session.last_user_message = text
                session.low_confidence_consecutive_count = 0
                await self.save_session(session)

                latency_ms = int((time.time() - start_time) * 1000)
                self._dispatch_metrics(
                    session_id=session_id,
                    latency_ms=latency_ms,
                    used_fallback=used_fallback,
                    escalated=escalated,
                    intent=intent,
                    llm_model=None,
                    tokens_used=0,
                    background_tasks=background_tasks,
                )

                return BotResponse(text=response_text)

            # Non-escalated fallback response
            intent = "degraded_fallback"
            session.transcript.append({"role": "assistant", "content": response_text})
            session.last_user_message = text
            await self.save_session(session)

            latency_ms = int((time.time() - start_time) * 1000)
            self._dispatch_metrics(
                session_id=session_id,
                latency_ms=latency_ms,
                used_fallback=used_fallback,
                escalated=False,
                intent=intent,
                llm_model=None,
                tokens_used=0,
                background_tasks=background_tasks,
            )

            return BotResponse(text=response_text)

        # 4. POST-PROCESSING TRIGGERS CHECK (Only if normal processing succeeded)
        escalated_post, reason_post = self.trigger_engine.evaluate_post_llm(response_text, session, tool_calls)
        if escalated_post and reason_post:
            logger.info("Post-LLM Escalation triggered", session_id=session_id, reason=reason_post)
            session.state = "HUMAN_HANDOFF"
            escalated = True
            intent = reason_post

            # Create ticket using built payload
            payload = await build_payload(session, reason_post)
            ticket_id = await self.handoff_client.create_ticket(session_id, payload)
            session.ticket_id = ticket_id

            # Override response text with the specialist transition message
            handover_text = "I'm connecting you to a human specialist. Please hold."
            session.transcript.append({"role": "assistant", "content": handover_text})

            session.last_user_message = text

            await self.save_session(session)

            latency_ms = int((time.time() - start_time) * 1000)
            self._dispatch_metrics(
                session_id=session_id,
                latency_ms=latency_ms,
                used_fallback=False,
                escalated=escalated,
                intent=intent,
                llm_model=model_used,
                tokens_used=tokens_used,
                background_tasks=background_tasks,
            )

            return BotResponse(text=handover_text)

        # Normal response: record the assistant's response and save state
        session.transcript.append({"role": "assistant", "content": response_text})
        session.last_user_message = text
        intent = "success_bot_chat"

        await self.save_session(session)

        # Track success metrics
        latency_ms = int((time.time() - start_time) * 1000)
        self._dispatch_metrics(
            session_id=session_id,
            latency_ms=latency_ms,
            used_fallback=False,
            escalated=False,
            intent=intent,
            llm_model=model_used,
            tokens_used=tokens_used,
            background_tasks=background_tasks,
        )

        return BotResponse(text=response_text)

    def _dispatch_metrics(
        self,
        session_id: str,
        latency_ms: int,
        used_fallback: bool,
        escalated: bool,
        intent: str | None,
        llm_model: str | None,
        tokens_used: int,
        background_tasks: BackgroundTasks | None,
    ) -> None:
        """Helper to record metrics asynchronously via FastAPI BackgroundTasks or asyncio tasks."""
        if background_tasks:
            background_tasks.add_task(
                self.analytics_recorder.record_metric,
                session_id=session_id,
                latency_ms=latency_ms,
                used_fallback=used_fallback,
                escalated=escalated,
                intent=intent,
                llm_model=llm_model,
                tokens_used=tokens_used,
            )
            logger.debug("Dispatched interaction metrics to FastAPI BackgroundTasks", session_id=session_id)
        else:
            # Fallback background asyncio task to prevent garbage collection (RUF006)
            task = asyncio.create_task(
                self.analytics_recorder.record_metric(
                    session_id=session_id,
                    latency_ms=latency_ms,
                    used_fallback=used_fallback,
                    escalated=escalated,
                    intent=intent,
                    llm_model=llm_model,
                    tokens_used=tokens_used,
                )
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            logger.debug("Dispatched interaction metrics to background asyncio task", session_id=session_id)
    """Manages state transitions, combining RAG context, context windows, and tool completions."""

    def __init__(
        self,
        session_manager: SessionManager,
        llm_client: LLMClient,
        rag_pipeline: RAGPipeline,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        """Initialize Orchestrator with dependencies."""
        self.session_manager = session_manager
        self.llm_client = llm_client
        self.rag_pipeline = rag_pipeline
        self.context_builder = context_builder or ContextBuilder()

    async def process_message(self, session_id: str, user_input: str) -> BotResponse:
        """Processes user input through RAG, Context formatting, and an async tool-completion loop.

        Args:
            session_id: The ID of the session.
            user_input: The raw user message string.

        Returns:
            A BotResponse representing the assistant's final response text.
        """
        try:
            # 1. Fetch current session
            session = await self.session_manager.get_or_create_session(session_id)

            # Handle handoff bypass
            if session.state == SessionState.HUMAN_HANDOFF:
                logger.info("Bypassing bot response, session in HUMAN_HANDOFF state", session_id=session_id)
                return BotResponse(
                    text="Thank you for reaching out. A human representative will assist you shortly.",
                    buttons=None,
                    should_escalate=False,
                )

            # 2. Save user message immediately and transition to PROCESSING
            await self.session_manager.add_message(session_id, Role.USER, user_input)
            session = await self.session_manager.get_or_create_session(session_id)

            # Transition state to PROCESSING and persist state immediately
            old_state = session.state
            session.state = SessionState.PROCESSING
            await self.session_manager.update_session(session)
            logger.info(
                "Session state transition",
                session_id=session_id,
                from_state=old_state.name,
                to_state=session.state.name,
            )

            # 3. Retrieve relevant context blocks using RAG pipeline
            rag_docs = await self.rag_pipeline.retrieve_context(user_input, top_k=3)
            if rag_docs:
                rag_context = "\n".join([doc.get("text", "") for doc in rag_docs])
            else:
                rag_context = "No knowledge base documents matching."

            # 4. Construct prompts templates utilizing the context builder
            messages = self.context_builder.build_messages(session.history, rag_context)

            # 5. Agentic loop with tool resolution
            llm_response = await self.llm_client.chat_completion(messages, tools=TOOL_DEFINITIONS)
            finish_reason = llm_response.get("finish_reason", "stop")
            llm_message = llm_response.get("message", {})

            loop_limit = 5
            loop_count = 0
            did_initiate_refund = False
            refund_amount = 0.0

            while finish_reason == "tool_calls" and loop_count < loop_limit:
                loop_count += 1
                tool_calls = llm_message.get("tool_calls", [])
                logger.info("LLM requested tool executions", tool_calls_count=len(tool_calls), session_id=session_id)

                messages.append(llm_message)

                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    func_details = tc.get("function", {})
                    func_name = func_details.get("name", "")
                    func_args_str = func_details.get("arguments", "{}")

                    # Parse JSON arguments safely
                    try:
                        func_args = json.loads(func_args_str)
                    except Exception:
                        func_args = {}

                    if func_name == "initiate_refund":
                        did_initiate_refund = True
                        try:
                            refund_amount = float(func_args.get("amount", 0.0))
                        except (ValueError, TypeError):
                            refund_amount = 0.0

                    try:
                        tool_result = execute_tool(func_name, func_args)
                    except Exception as e:
                        logger.error("Tool execution failed", tool=func_name, error=str(e))
                        tool_result = f"Error: Tool execution failed with error {e!s}"

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": func_name,
                            "content": tool_result,
                        }
                    )

                llm_response = await self.llm_client.chat_completion(messages, tools=TOOL_DEFINITIONS)
                finish_reason = llm_response.get("finish_reason", "stop")
                llm_message = llm_response.get("message", {})

            final_text = llm_message.get("content") or ""

            # 6. Evaluate Escalation policies
            should_escalate = False
            if "[ESCALATE]" in final_text or (did_initiate_refund and refund_amount > 500.0):
                should_escalate = True
                session.state = SessionState.ESCALATED
                logger.info(
                    "Session escalated to human handoff",
                    session_id=session_id,
                    refund_trigger=did_initiate_refund,
                    refund_amount=refund_amount,
                )
                final_text = final_text.replace("[ESCALATE]", "").strip()
            else:
                session.state = SessionState.AWAITING_INPUT

            # Persist bot reply and final state details
            await self.session_manager.add_message(session_id, Role.BOT, final_text)

            session = await self.session_manager.get_or_create_session(session_id)
            session.state = SessionState.ESCALATED if should_escalate else SessionState.AWAITING_INPUT
            await self.session_manager.update_session(session)

            logger.info(
                "Session state transition",
                session_id=session_id,
                from_state="PROCESSING",
                to_state=session.state.name,
            )

            return BotResponse(
                text=final_text,
                buttons=None,
                should_escalate=should_escalate,
            )

        except Exception as e:
            logger.exception("An unhandled exception occurred in the Orchestrator loop", session_id=session_id, error=str(e))  # noqa: E501
            # Graceful fallback response
            fallback_text = (
                "I'm having trouble connecting to my knowledge base. "
                "Let me get a human representative to assist you."
            )
            return BotResponse(
                text=fallback_text,
                buttons=None,
                should_escalate=True,
            )

    async def handle_agent_reply(self, session_id: str, agent_message: str) -> BotResponse:
        """Process a reply sent by a human agent back to the user.

        Transitions state based on agent action or keeps HUMAN_HANDOFF active.

        Args:
            session_id: The ID of the session.
            agent_message: The message sent by the agent.

        Returns:
            A BotResponse containing the agent's reply.
        """
        # Fetch current state
        session = await self.session_manager.get_or_create_session(session_id)

        # Determine next state
        old_state = session.state
        if "close" in agent_message.lower() or "resolve" in agent_message.lower():
            session.state = SessionState.AWAITING_INPUT
        else:
            session.state = SessionState.HUMAN_HANDOFF

        logger.info(
            "Agent message transition",
            session_id=session_id,
            from_state=old_state.name,
            to_state=session.state.name,
        )

        # Save session state changes
        await self.session_manager.update_session(session)

        # Add the agent message to history
        await self.session_manager.add_message(session_id, Role.SYSTEM, f"Agent: {agent_message}")

        return BotResponse(
            text=agent_message,
            buttons=None,
            should_escalate=False,
        )
